"""
GasFree utility functions for address calculation, TIP-712 hashing, and HTTP API interaction.
"""

import hashlib
import logging
from typing import Any, Dict, Optional

import httpx

from x402_tron.utils.address import evm_address_to_tron, tron_address_to_evm

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

GASFREE_API_BASE_URL = "https://api.gasfree.io/v1"


class GasFreeAPIClient:
    """Official GasFree HTTP API client implementation"""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    async def get_nonce(self, user: str, _token: str, _chain_id: int) -> int:
        """Get the current recommended nonce for a user account
        Official endpoint: GET /api/v1/address/{accountAddress}
        """
        async with httpx.AsyncClient() as client:
            url = f"{self.base_url}/api/v1/address/{user}"
            try:
                response = await client.get(url)
                response.raise_for_status()
                result = response.json()
                if result.get("code") != 200:
                    raise RuntimeError(f"API error: {result.get('message') or result.get('reason')}")
                
                data = result.get("data", {})
                return int(data.get("nonce", 0))
            except Exception as e:
                logger.warning(f"Failed to get nonce from GasFree API: {e}. Defaulting to 0.")
                return 0

    async def submit(self, domain: Dict[str, Any], message: Dict[str, Any], signature: str) -> str:
        """Submit a signed GasFree transaction to the official relayer
        Official endpoint: POST /api/v1/gasfree/submit
        """
        async with httpx.AsyncClient() as client:
            url = f"{self.base_url}/api/v1/gasfree/submit"
            
            # 官方 API 提交格式要求（基于文档 3.3 章节）
            # 注意：sig 参数不带 0x 前缀
            sig = signature[2:] if signature.startswith("0x") else signature
            payload = {
                "token": message["token"],
                "serviceProvider": message["serviceProvider"],
                "user": message["user"],
                "receiver": message["receiver"],
                "value": message["value"],
                "maxFee": message["maxFee"],
                "deadline": message["deadline"],
                "version": message["version"],
                "nonce": message["nonce"],
                "sig": sig,
            }
            
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                result = response.json()
                if result.get("code") != 200:
                    raise RuntimeError(f"API error: {result.get('message') or result.get('reason')}")
                
                data = result.get("data", {})
                return data.get("id") # 返回 traceId
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


class GasFreeTronAddressCalculator:
    """Helper for calculating GasFree CREATE2 addresses"""

    @staticmethod
    def keccak256(data: bytes) -> bytes:
        """Keccak256 hash"""
        try:
            from eth_hash.auto import keccak

            return keccak(data)
        except ImportError:
            # Fallback for environments without eth-hash
            try:
                import sha3

                return sha3.keccak_256(data).digest()
            except ImportError:
                raise RuntimeError("Keccak256 implementation (eth-hash or pysha3) required")

    @classmethod
    def calculate_salt(cls, address: str) -> str:
        """Calculate salt from address (0x + address padded to 32 bytes)"""
        evm_addr = tron_address_to_evm(address)
        addr_hex = evm_addr[2:].lower()
        return "0x" + addr_hex.rjust(64, "0")

    @classmethod
    def get_initialize_selector(cls) -> str:
        """Get initialize(address) selector: 0xfe4b84df"""
        return "0xfe4b84df"

    @classmethod
    def calculate_bytecode_hash(cls, address: str, beacon: str, creation_code: str) -> str:
        """Calculate bytecode hash for CREATE2"""
        salt = cls.calculate_salt(address)
        initialize_data = cls.get_initialize_selector() + salt[2:]

        beacon_evm = tron_address_to_evm(beacon)
        beacon_hex = beacon_evm[2:].lower().rjust(64, "0")

        data_bytes = bytes.fromhex(initialize_data[2:])
        data_len = len(data_bytes)

        offset_hex = hex(64).split("x")[1].rjust(64, "0")
        length_hex = hex(data_len).split("x")[1].rjust(64, "0")
        data_hex = initialize_data[2:].ljust((data_len + 31) // 32 * 64, "0")

        encoded_args = beacon_hex + offset_hex + length_hex + data_hex

        code_hex = creation_code[2:] if creation_code.startswith("0x") else creation_code
        full_bytecode = bytes.fromhex(code_hex) + bytes.fromhex(encoded_args)

        return "0x" + cls.keccak256(full_bytecode).hex()

    @classmethod
    def calculate_gasfree_address(
        cls,
        user_address: str,
        gasfree_controller: str,
        beacon: str,
        creation_code: str,
    ) -> str:
        """Calculate CREATE2 GasFree address"""
        salt_hex = cls.calculate_salt(user_address)
        bytecode_hash_hex = cls.calculate_bytecode_hash(user_address, beacon, creation_code)

        prefix = bytes.fromhex("41")  # TRON use 0x41 for CREATE2 prefix
        controller_evm = tron_address_to_evm(gasfree_controller)
        controller_bytes = bytes.fromhex(controller_evm[2:])
        salt_bytes = bytes.fromhex(salt_hex[2:])
        bytecode_hash_bytes = bytes.fromhex(bytecode_hash_hex[2:])

        create2_input = prefix + controller_bytes + salt_bytes + bytecode_hash_bytes
        address_hash = cls.keccak256(create2_input)

        evm_addr = "0x" + address_hash[12:].hex()
        return evm_address_to_tron(evm_addr)
