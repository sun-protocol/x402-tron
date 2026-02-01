"""
Service Managers

Manages lifecycle of Facilitator and Server services with async health checks.
"""

import asyncio
import sys
from typing import Optional

import httpx

from .proxy import BaseProxy, ProcessConfig
from .discovery import ComponentInfo


class ServiceManager:
    """Base service manager with health check support"""

    def __init__(self, component: ComponentInfo, env: Optional[dict[str, str]] = None):
        self.component = component
        self._env = env or {}
        self._proxy: Optional[BaseProxy] = None
        self._healthy = False

    @property
    def is_running(self) -> bool:
        return self._proxy is not None and self._proxy.is_running

    @property
    def is_healthy(self) -> bool:
        return self._healthy

    @property
    def base_url(self) -> str:
        if self._proxy:
            return self._proxy.base_url
        return f"http://localhost:{self.component.port}"

    def _build_env(self) -> dict[str, str]:
        """Build environment variables for the service"""
        env = {}

        # Load from .env file if exists
        if self.component.env_file and self.component.env_file.exists():
            from dotenv import dotenv_values

            env.update(dotenv_values(self.component.env_file))

        # Override with provided env
        env.update(self._env)

        return env

    def _build_command(self) -> list[str]:
        """Build command to start the service"""
        if self.component.main_file:
            return [sys.executable, str(self.component.main_file)]
        return []

    async def start(self, skip_if_running: bool = True) -> bool:
        """
        Start the service.
        
        Args:
            skip_if_running: If True, skip starting if service is already healthy
        
        Returns:
            True if service is running and healthy
        """
        # Check if service is already running
        if skip_if_running:
            if await self._check_health():
                self._healthy = True
                print(f"✓ {self.component.name} already running at {self.base_url}")
                return True
        
        if self.is_running:
            return True

        command = self._build_command()
        if not command:
            print(f"No command found for {self.component.name}")
            return False

        print(f"Starting {self.component.name} at {self.base_url}...")
        
        config = ProcessConfig(
            name=self.component.name,
            working_dir=self.component.path,
            command=command,
            env=self._build_env(),
            port=self.component.port,
            host="localhost",
            startup_timeout=30.0,
        )

        self._proxy = BaseProxy(config)
        success = await self._proxy.start_process()

        if success:
            self._healthy = await self._check_health()

        return success and self._healthy

    async def stop(self) -> bool:
        """Stop the service (only if started by this manager)"""
        if self._proxy:
            result = await self._proxy.stop_process()
            self._healthy = False
            return result
        # If no proxy, service was already running - don't stop it
        return True

    async def _check_health(self) -> bool:
        """Check service health"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/")
                return response.status_code == 200
        except Exception:
            return False

    async def wait_healthy(self, timeout: float = 30.0) -> bool:
        """Wait for service to become healthy"""
        deadline = asyncio.get_event_loop().time() + timeout

        while asyncio.get_event_loop().time() < deadline:
            if await self._check_health():
                self._healthy = True
                return True
            await asyncio.sleep(0.5)

        return False


class FacilitatorManager(ServiceManager):
    """Manager for Facilitator service"""

    async def get_supported(self) -> dict:
        """Get supported capabilities from facilitator"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}/supported")
                if response.status_code == 200:
                    return response.json()
        except Exception:
            pass
        return {}

    async def verify_payment(self, payload: dict, requirements: dict) -> dict:
        """Verify payment via facilitator API"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/verify",
                json={
                    "paymentPayload": payload,
                    "paymentRequirements": requirements,
                },
            )
            return response.json()

    async def settle_payment(self, payload: dict, requirements: dict) -> dict:
        """Settle payment via facilitator API"""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/settle",
                json={
                    "paymentPayload": payload,
                    "paymentRequirements": requirements,
                },
            )
            return response.json()

    async def get_fee_quote(self, requirements: dict) -> dict:
        """Get fee quote from facilitator"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{self.base_url}/fee/quote",
                json={"accept": requirements},
            )
            return response.json()


class ServerManager(ServiceManager):
    """Manager for Server service"""

    async def get_protected_resource(
        self,
        path: str = "/protected",
        payment_header: Optional[str] = None,
    ) -> tuple[int, dict]:
        """
        Request protected resource.

        Args:
            path: Resource path
            payment_header: PAYMENT-SIGNATURE header value

        Returns:
            Tuple of (status_code, response_data)
        """
        headers = {}
        if payment_header:
            headers["PAYMENT-SIGNATURE"] = payment_header

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}{path}",
                headers=headers,
            )

            try:
                data = response.json()
            except Exception:
                data = {"content": response.content}

            return response.status_code, data

    async def get_payment_requirements(
        self, path: str = "/protected"
    ) -> Optional[dict]:
        """
        Get payment requirements from 402 response.

        Returns:
            Payment requirements dict or None
        """
        status, data = await self.get_protected_resource(path)

        if status == 402 and "accepts" in data:
            return data["accepts"][0] if data["accepts"] else None

        return None


class ServiceOrchestrator:
    """
    Orchestrates multiple services for e2e testing.

    Usage:
        orchestrator = ServiceOrchestrator()
        await orchestrator.start_all(facilitators, servers)
        # ... run tests ...
        await orchestrator.stop_all()
    """

    def __init__(self):
        self._facilitators: list[FacilitatorManager] = []
        self._servers: list[ServerManager] = []

    @property
    def facilitators(self) -> list[FacilitatorManager]:
        return self._facilitators

    @property
    def servers(self) -> list[ServerManager]:
        return self._servers

    async def start_facilitators(
        self,
        components: list[ComponentInfo],
        env: Optional[dict[str, str]] = None,
    ) -> list[FacilitatorManager]:
        """Start facilitator services in parallel"""
        managers = [FacilitatorManager(c, env) for c in components]

        # Start all in parallel
        results = await asyncio.gather(
            *[m.start() for m in managers],
            return_exceptions=True,
        )

        # Filter successful starts
        self._facilitators = [m for m, r in zip(managers, results) if r is True]

        return self._facilitators

    async def start_servers(
        self,
        components: list[ComponentInfo],
        env: Optional[dict[str, str]] = None,
    ) -> list[ServerManager]:
        """Start server services in parallel"""
        managers = [ServerManager(c, env) for c in components]

        results = await asyncio.gather(
            *[m.start() for m in managers],
            return_exceptions=True,
        )

        self._servers = [m for m, r in zip(managers, results) if r is True]

        return self._servers

    async def stop_all(self):
        """Stop all services"""
        all_managers = self._facilitators + self._servers

        await asyncio.gather(
            *[m.stop() for m in all_managers],
            return_exceptions=True,
        )

        self._facilitators = []
        self._servers = []

    async def health_check_all(self) -> dict[str, bool]:
        """Check health of all services"""
        results = {}

        for m in self._facilitators:
            results[f"facilitator:{m.component.name}"] = await m._check_health()

        for m in self._servers:
            results[f"server:{m.component.name}"] = await m._check_health()

        return results
