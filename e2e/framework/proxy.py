"""
Base Proxy for Process Management

Provides unified interface for starting/stopping subprocess:
- startProcess(): Start subprocess
- stopProcess(): Stop subprocess
- runOneShotProcess(): One-shot execution
- getRunCommand(): Parse run.sh command
"""

import asyncio
import os
import signal
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ProcessConfig:
    """Process configuration"""

    name: str
    working_dir: Path
    command: list[str]
    env: dict[str, str] = field(default_factory=dict)
    port: int = 0
    host: str = "localhost"
    startup_timeout: float = 30.0
    health_endpoint: str = "/"


class BaseProxy:
    """
    Base proxy for managing subprocess lifecycle.

    Usage:
        proxy = BaseProxy(config)
        await proxy.start_process()
        # ... use service ...
        await proxy.stop_process()
    """

    def __init__(self, config: ProcessConfig):
        self.config = config
        self._process: Optional[subprocess.Popen] = None
        self._started = False
        self._log_task: Optional[asyncio.Task] = None

    @property
    def is_running(self) -> bool:
        """Check if process is running"""
        if self._process is None:
            return False
        return self._process.poll() is None

    @property
    def base_url(self) -> str:
        """Get service base URL"""
        return f"http://{self.config.host}:{self.config.port}"

    async def start_process(self) -> bool:
        """
        Start the subprocess.

        Returns:
            True if started successfully
        """
        if self.is_running:
            return True

        env = os.environ.copy()
        env.update(self.config.env)

        try:
            self._process = subprocess.Popen(
                self.config.command,
                cwd=self.config.working_dir,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1,
                universal_newlines=True,
                preexec_fn=os.setsid if sys.platform != "win32" else None,
            )

            # Start log streaming task
            self._log_task = asyncio.create_task(self._stream_logs())

            # Wait for service to be ready
            if self.config.port > 0:
                ready = await self._wait_for_ready()
                if not ready:
                    await self.stop_process()
                    return False

            self._started = True
            return True

        except Exception as e:
            print(f"Failed to start {self.config.name}: {e}")
            return False

    async def stop_process(self) -> bool:
        """
        Stop the subprocess.

        Returns:
            True if stopped successfully
        """
        if self._process is None:
            return True

        # Cancel log streaming task
        if self._log_task:
            self._log_task.cancel()
            try:
                await self._log_task
            except asyncio.CancelledError:
                pass

        try:
            if sys.platform != "win32":
                os.killpg(os.getpgid(self._process.pid), signal.SIGTERM)
            else:
                self._process.terminate()

            # Wait for graceful shutdown
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                if sys.platform != "win32":
                    os.killpg(os.getpgid(self._process.pid), signal.SIGKILL)
                else:
                    self._process.kill()
                self._process.wait()

            self._process = None
            self._started = False
            return True

        except Exception as e:
            print(f"Failed to stop {self.config.name}: {e}")
            return False

    async def run_one_shot_process(
        self,
        command: list[str],
        timeout: float = 60.0,
    ) -> tuple[int, str, str]:
        """
        Run a one-shot command.

        Args:
            command: Command to execute
            timeout: Execution timeout

        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        env = os.environ.copy()
        env.update(self.config.env)

        try:
            proc = await asyncio.create_subprocess_exec(
                *command,
                cwd=self.config.working_dir,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout,
            )

            return (
                proc.returncode or 0,
                stdout.decode() if stdout else "",
                stderr.decode() if stderr else "",
            )

        except asyncio.TimeoutError:
            proc.kill()
            return (-1, "", "Process timed out")
        except Exception as e:
            return (-1, "", str(e))

    async def _wait_for_ready(self) -> bool:
        """Wait for service to be ready"""
        import httpx

        url = f"{self.base_url}{self.config.health_endpoint}"
        deadline = asyncio.get_event_loop().time() + self.config.startup_timeout

        async with httpx.AsyncClient(timeout=5.0) as client:
            while asyncio.get_event_loop().time() < deadline:
                try:
                    response = await client.get(url)
                    if response.status_code == 200:
                        return True
                except Exception:
                    pass
                await asyncio.sleep(0.5)

        return False

    async def _stream_logs(self):
        """Stream logs from the process to stdout"""
        if not self._process or not self._process.stdout:
            return

        try:
            while self.is_running:
                line = await asyncio.get_event_loop().run_in_executor(
                    None, self._process.stdout.readline
                )
                if line:
                    print(f"[{self.config.name}] {line.rstrip()}")
                else:
                    break
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[{self.config.name}] Log streaming error: {e}")

    @staticmethod
    def get_run_command(script_path: Path) -> list[str]:
        """
        Parse run.sh/start.sh to get the actual command.

        Args:
            script_path: Path to shell script

        Returns:
            List of command arguments
        """
        if not script_path.exists():
            return []

        content = script_path.read_text()

        # Find the main command (usually python or uvicorn)
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("#") or not line:
                continue
            if "python" in line or "uvicorn" in line:
                # Parse the command
                parts = line.split()
                return parts

        return []


class PythonServiceProxy(BaseProxy):
    """Proxy for Python-based services"""

    @classmethod
    def from_directory(
        cls,
        name: str,
        directory: Path,
        port: int,
        env: Optional[dict[str, str]] = None,
    ) -> "PythonServiceProxy":
        """
        Create proxy from service directory.

        Args:
            name: Service name
            directory: Service directory containing main.py
            port: Service port
            env: Additional environment variables
        """
        main_py = directory / "main.py"
        if not main_py.exists():
            raise FileNotFoundError(f"main.py not found in {directory}")

        config = ProcessConfig(
            name=name,
            working_dir=directory,
            command=[sys.executable, str(main_py)],
            env=env or {},
            port=port,
            host="localhost",
        )

        return cls(config)
