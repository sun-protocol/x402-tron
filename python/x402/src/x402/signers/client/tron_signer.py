"""
TronClientSigner - TRON client signer implementation
"""

import json
from typing import Any

from x402.signers.client.base import ClientSigner


class TronClientSigner(ClientSigner):
    """TRON client signer implementation"""

    def __init__(self, private_key: str, network: str | None = None) -> None:
        clean_key = private_key[2:] if private_key.startswith("0x") else private_key
        self._private_key = clean_key
        self._address = self._derive_address(clean_key)
        self._network = network
        self._tron_client: Any = None

    @classmethod
    def from_private_key(cls, private_key: str, network: str | None = None) -> "TronClientSigner":
        """
        Create signer from private key.

        Args:
            private_key: TRON private key (hex string)
            network: Optional TRON network (mainnet/shasta/nile) for lazy client initialization

        Returns:
            TronClientSigner instance
        """
        return cls(private_key, network)

    def _ensure_tron_client(self) -> Any:
        """
        Lazy initialization of tron_client.
        
        Returns:
            tronpy.Tron instance or None
        """
        if self._tron_client is None and self._network:
            try:
                from tronpy import Tron
                self._tron_client = Tron(network=self._network)
            except ImportError:
                pass
        return self._tron_client

    @staticmethod
    def _derive_address(private_key: str) -> str:
        """Derive TRON address from private key"""
        try:
            from tronpy.keys import PrivateKey
            pk = PrivateKey(bytes.fromhex(private_key))
            return pk.public_key.to_base58check_address()
        except ImportError:
            return f"T{private_key[:33]}"

    def get_address(self) -> str:
        return self._address

    async def sign_message(self, message: bytes) -> str:
        """Sign raw message using ECDSA"""
        try:
            from tronpy.keys import PrivateKey
            pk = PrivateKey(bytes.fromhex(self._private_key))
            signature = pk.sign_msg(message)
            return signature.hex()
        except ImportError:
            raise RuntimeError("tronpy is required for signing")

    async def sign_typed_data(
        self,
        domain: dict[str, Any],
        types: dict[str, Any],
        message: dict[str, Any],
    ) -> str:
        """Sign EIP-712 typed data"""
        try:
            from eth_account import Account
            from eth_account.messages import encode_typed_data

            full_types = {
                "EIP712Domain": [
                    {"name": "name", "type": "string"},
                    {"name": "version", "type": "string"},
                ],
                **types,
            }

            typed_data = {
                "types": full_types,
                "primaryType": "PaymentPermit",
                "domain": domain,
                "message": message,
            }

            signable = encode_typed_data(full_data=typed_data)
            signed = Account.sign_message(signable, self._private_key)
            return signed.signature.hex()
        except ImportError:
            data_str = json.dumps({"domain": domain, "types": types, "message": message})
            return await self.sign_message(data_str.encode())

    async def check_allowance(
        self,
        token: str,
        amount: int,
        network: str,
    ) -> int:
        """Check token allowance on TRON"""
        client = self._ensure_tron_client()
        if client is None:
            return 0

        try:
            contract = client.get_contract(token)
            allowance = contract.functions.allowance(
                self._address,
                self._get_spender_address(network),
            )
            return int(allowance)
        except Exception:
            return 0

    async def ensure_allowance(
        self,
        token: str,
        amount: int,
        network: str,
        mode: str = "auto",
    ) -> bool:
        """Ensure sufficient allowance"""
        if mode == "skip":
            return True

        current = await self.check_allowance(token, amount, network)
        if current >= amount:
            return True

        if mode == "interactive":
            raise NotImplementedError("Interactive approval not implemented")

        client = self._ensure_tron_client()
        if client is None:
            raise RuntimeError("tronpy client required for approval")

        try:
            contract = client.get_contract(token)
            txn = (
                contract.functions.approve(
                    self._get_spender_address(network),
                    amount,
                )
                .with_owner(self._address)
                .fee_limit(100_000_000)
                .build()
                .sign(self._private_key)
            )
            result = txn.broadcast().wait()
            return result.get("result", False)
        except Exception:
            return False

    def _get_spender_address(self, network: str) -> str:
        """Get payment permit contract address (spender)"""
        addresses = {
            "tron:mainnet": "T...",
            "tron:shasta": "T...",
            "tron:nile": "T...",
        }
        return addresses.get(network, "T0000000000000000000000000000000")
