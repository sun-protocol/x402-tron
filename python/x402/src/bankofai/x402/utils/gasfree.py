"""
GasFree utility functions for TIP-712 hashing and HTTP API interaction.
"""

import asyncio
import base64
import hmac
import json
import logging
import time
from typing import Any, Dict, Optional

import httpx

from bankofai.x402.abi import GASFREE_PRIMARY_TYPE
from bankofai.x402.utils.address import tron_address_to_evm

logger = logging.getLogger(__name__)

# GasFree EIP-712 Domain Definition
GASFREE_DOMAIN_TYPE = [
    {"name": "name", "type": "string"},
    {"name": "version", "type": "string"},
    {"name": "chainId", "type": "uint256"},
    {"name": "verifyingContract", "type": "address"},
]

# GasFree TIP-712 Message Types
GASFREE_TYPES = {
    "EIP712Domain": GASFREE_DOMAIN_TYPE,
    GASFREE_PRIMARY_TYPE: [
        {"name": "token", "type": "address"},
        {"name": "serviceProvider", "type": "address"},
        {"name": "user", "type": "address"},
        {"name": "receiver", "type": "address"},
        {"name": "value", "type": "uint256"},
        {"name": "maxFee", "type": "uint256"},
        {"name": "deadline", "type": "uint256"},
        {"name": "version", "type": "uint256"},
        {"name": "nonce", "type": "uint256"},
    ],
}

GASFREE_API_BASE_URL = "https://open.gasfree.io/tron"


class GasFreeAPIClient:
    """Official GasFree HTTP API client implementation with HMAC authentication"""

    def __init__(
        self, base_url: str, api_key: Optional[str] = None, api_secret: Optional[str] = None
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.api_secret = api_secret

    def _generate_signature(self, method: str, path: str, timestamp: int) -> str:
        """Generate HMAC-SHA256 signature for API authentication"""
        if not self.api_secret:
            return ""

        msg = f"{method.upper()}{path}{timestamp}"

        signature_bytes = hmac.new(
            self.api_secret.encode("utf-8"), msg.encode("utf-8"), digestmod="sha256"
        ).digest()
        return base64.b64encode(signature_bytes).decode("utf-8")

    def _get_headers(self, method: str, path: str) -> Dict[str, str]:
        """Generate headers with authentication"""
        headers = {"Content-Type": "application/json"}
        if not self.api_key or not self.api_secret:
            return headers

        # Ensure path includes the network prefix if it's not already there
        # but the logic in get_address_info/submit already provides the relative path from base_url.
        # However, for signature, the Provider expects the FULL path including /nile or /tron
        full_path = path
        base_url_parts = self.base_url.split("/")
        # If base_url is https://open-test.gasfree.io/nile, the prefix is /nile
        prefix = ""
        if len(base_url_parts) > 3:
            prefix = "/" + "/".join(base_url_parts[3:])
            if not full_path.startswith(prefix):
                full_path = prefix + path

        timestamp = int(time.time())
        signature = self._generate_signature(method, full_path, timestamp)

        headers.update(
            {"Timestamp": str(timestamp), "Authorization": f"ApiKey {self.api_key}:{signature}"}
        )
        return headers

    async def get_providers(self) -> list[Dict[str, Any]]:
        """Get all supported service providers from configuration"""
        path = "/api/v1/config/provider/all"
        async with httpx.AsyncClient() as client:
            url = f"{self.base_url}{path}"
            try:
                headers = self._get_headers("GET", path)
                response = await client.get(url, headers=headers)
                if response.status_code != 200:
                    logger.error(f"GasFree API error {response.status_code}: {response.text}")
                    response.raise_for_status()
                result = response.json()
                if result.get("code") != 200:
                    raise RuntimeError(
                        f"API business error: {result.get('message') or result.get('reason')}"
                    )
                data = result.get("data", {})
                return data.get("providers", [])
            except Exception as e:
                logger.error(f"Failed to get providers from GasFree API: {e}")
                raise

    async def get_nonce(self, user: str, token: str, chain_id: int) -> int:
        """Get the recommended nonce for a user account"""
        data = await self.get_address_info(user)
        return int(data.get("nonce", 0))

    async def get_address_info(self, user: str) -> Dict[str, Any]:
        """Get account info (activation, balance, nonce) for a user"""
        path = f"/api/v1/address/{user}"
        async with httpx.AsyncClient() as client:
            url = f"{self.base_url}{path}"
            try:
                headers = self._get_headers("GET", path)
                response = await client.get(url, headers=headers)
                if response.status_code != 200:
                    logger.error(f"GasFree API error {response.status_code}: {response.text}")
                    response.raise_for_status()
                result = response.json()
                if result.get("code") != 200:
                    message = result.get("message") or result.get("reason")
                    raise RuntimeError(f"API business error: {message} - Body: {response.text}")
                return result.get("data", {})
            except Exception as e:
                if isinstance(e, httpx.HTTPStatusError):
                    logger.error(f"HTTP Status Error Body: {e.response.text}")
                logger.error(f"Failed to get address info from GasFree API: {e}")
                raise

    async def get_status(self, trace_id: str) -> Dict[str, Any]:
        """Get status of a submitted GasFree transaction"""
        path = f"/api/v1/gasfree/{trace_id}"
        async with httpx.AsyncClient() as client:
            url = f"{self.base_url}{path}"
            try:
                headers = self._get_headers("GET", path)
                response = await client.get(url, headers=headers)
                if response.status_code != 200:
                    logger.error(f"GasFree API error {response.status_code}: {response.text}")
                    response.raise_for_status()
                result = response.json()
                if result.get("code") != 200:
                    raise RuntimeError(
                        f"API business error: {result.get('message') or result.get('reason')}"
                    )
                data = result.get("data", {})
                logger.info(f"GasFree Status Response for {trace_id}: {json.dumps(data)}")
                return data
            except Exception as e:
                logger.error(f"Failed to get GasFree transaction status: {e}")
                raise

    async def wait_for_success(
        self, trace_id: str, timeout: int = 180, poll_interval: int = 5
    ) -> Dict[str, Any]:
        """Wait for a GasFree transaction to reach a terminal state or acceptable timeout state"""
        start_time = time.time()
        logger.info(f"Start polling for GasFree transaction {trace_id} (timeout={timeout}s)...")

        status_data = {}
        while time.time() - start_time < timeout:
            status_data = await self.get_status(trace_id)
            state = (status_data.get("state") or "").upper()
            txn_state = (status_data.get("txnState") or "").upper()

            logger.info(f"GasFree transaction {trace_id}: state={state}, txnState={txn_state}")

            # 1. Immediate return for final states
            if state == "SUCCEED":
                return status_data
            if state == "FAILED" or txn_state == "ON_CHAIN_FAILED":
                raise RuntimeError(
                    f"GasFree transaction failed. Reason: {status_data.get('reason')}"
                )

            await asyncio.sleep(poll_interval)

        # 2. Timeout reached - check for "acceptable" states
        final_state = (status_data.get("state") or "").upper()
        final_txn_state = (status_data.get("txnState") or "").upper()

        if final_state == "CONFIRMING" and final_txn_state == "ON_CHAIN":
            logger.info(
                f"GasFree transaction {trace_id} reached CONFIRMING/ON_CHAIN at timeout. Success."
            )
            return status_data

        msg = (
            f"GasFree transaction {trace_id} failed or timed out. "
            f"State: {final_state}, TxnState: {final_txn_state}"
        )
        raise TimeoutError(msg)

    async def submit(self, domain: Dict[str, Any], message: Dict[str, Any], signature: str) -> str:
        """Submit a signed GasFree transaction to the official relayer"""
        path = "/api/v1/gasfree/submit"
        async with httpx.AsyncClient() as client:
            url = f"{self.base_url}{path}"
            sig = signature[2:] if signature.startswith("0x") else signature
            payload = {
                "token": message["token"],
                "serviceProvider": message["serviceProvider"],
                "user": message["user"],
                "receiver": message["receiver"],
                "value": str(message["value"]),
                "maxFee": str(message["maxFee"]),
                "deadline": int(message["deadline"]),
                "version": int(message["version"]),
                "nonce": int(message["nonce"]),
                "sig": sig,
                "requestId": f"x402-{int(time.time())}-{sig[:8]}",
            }

            try:
                headers = self._get_headers("POST", path)
                response = await client.post(url, json=payload, headers=headers)
                if response.status_code != 200:
                    logger.error(f"GasFree API error {response.status_code}: {response.text}")
                    response.raise_for_status()
                result = response.json()
                if result.get("code") != 200:
                    message = result.get("message") or result.get("reason")
                    raise RuntimeError(f"API business error: {message} - Body: {response.text}")
                data = result.get("data", {})
                return data.get("id")  # Returns traceId
            except Exception as e:
                if isinstance(e, httpx.HTTPStatusError):
                    logger.error(f"HTTP Status Error Body: {e.response.text}")
                logger.error(f"Failed to submit GasFree transaction: {e}")
                raise


def get_gasfree_domain(chain_id: int, verifying_contract: str) -> Dict[str, Any]:
    """Get GasFree TIP-712 domain"""
    return {
        "name": "GasFreeController",
        "version": "V1.0.0",
        "chainId": chain_id,
        "verifyingContract": tron_address_to_evm(verifying_contract),
    }
