"""
GasFree utility functions for address calculation, TIP-712 hashing, and HTTP API interaction.
"""

import hmac
import logging
import time
from typing import Any, Dict, Optional

import httpx

from x402_tron.utils.address import tron_address_to_evm

logger = logging.getLogger(__name__)

# GasFree TIP-712 Types
GASFREE_PERMIT_TRANSFER_TYPES = {
    "PermitTransfer": [
        {"name": "token", "type": "address"},
        {"name": "serviceProvider", "type": "address"},
        {"name": "user", "type": "address"},
        {"name": "receiver", "type": "address"},
        {"name": "value", "type": "uint256"},
        {"name": "maxFee", "type": "uint256"},
        {"name": "deadline", "type": "uint256"},
        {"name": "version", "type": "uint256"},
        {"name": "nonce", "type": "uint256"},
    ]
}

GASFREE_API_BASE_URL = "https://open.gasfree.io/tron"


class GasFreeAPIClient:
    """Official GasFree HTTP API client implementation"""

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

        # String to sign: {method}{path}{timestamp}
        msg = f"{method.upper()}{path}{timestamp}"
        import base64

        signature_bytes = hmac.new(
            self.api_secret.encode("utf-8"), msg.encode("utf-8"), digestmod="sha256"
        ).digest()
        return base64.b64encode(signature_bytes).decode("utf-8")

    def _get_headers(self, method: str, path: str) -> Dict[str, str]:
        """Generate headers with authentication"""
        headers = {"Content-Type": "application/json"}
        if not self.api_key or not self.api_secret:
            return headers

        timestamp = int(time.time())
        signature = self._generate_signature(method, path, timestamp)

        headers.update(
            {"Timestamp": str(timestamp), "Authorization": f"ApiKey {self.api_key}:{signature}"}
        )
        return headers

    async def get_nonce(self, user: str, token: str, chain_id: int) -> int:
        """Get the current recommended nonce for a user account
        Official endpoint: GET /api/v1/address/{accountAddress}
        """
        data = await self.get_address_info(user)
        return int(data.get("nonce", 0))

    async def get_address_info(self, user: str) -> Dict[str, Any]:
        """Get account info (activation, balance, nonce) for a user
        Official endpoint: GET /api/v1/address/{accountAddress}
        """
        path = f"/api/v1/address/{user}"
        async with httpx.AsyncClient() as client:
            url = f"{self.base_url}{path}"
            try:
                headers = self._get_headers("GET", path)
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                result = response.json()
                if result.get("code") != 200:
                    raise RuntimeError(
                        f"API error: {result.get('message') or result.get('reason')}"
                    )

                return result.get("data", {})
            except Exception as e:
                logger.error(f"Failed to get address info from GasFree API: {e}")
                raise

    async def submit(self, domain: Dict[str, Any], message: Dict[str, Any], signature: str) -> str:
        """Submit a signed GasFree transaction to the official relayer
        Official endpoint: POST /api/v1/gasfree/submit
        """
        path = "/api/v1/gasfree/submit"
        async with httpx.AsyncClient() as client:
            url = f"{self.base_url}{path}"

            # 官方 API 提交格式要求（基于文档 3.3 章节）
            # 注意：sig 参数不带 0x 前缀
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
                response.raise_for_status()
                result = response.json()
                if result.get("code") != 200:
                    raise RuntimeError(
                        f"API error: {result.get('message') or result.get('reason')}"
                    )

                data = result.get("data", {})
                return data.get("id")  # 返回 traceId
            except Exception as e:
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
