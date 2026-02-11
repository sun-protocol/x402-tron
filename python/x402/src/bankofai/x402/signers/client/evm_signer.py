"""
EvmClientSigner - EVM client signer implementation
"""

import logging
from typing import Any

from bankofai.x402.abi import ERC20_ABI, PAYMENT_PERMIT_PRIMARY_TYPE
from bankofai.x402.config import NetworkConfig
from bankofai.x402.exceptions import InsufficientAllowanceError, SignatureCreationError
from bankofai.x402.signers.client.base import ClientSigner
from bankofai.x402.signers.utils import _eip712_domain_type_from_keys, resolve_provider_uri

logger = logging.getLogger(__name__)


class EvmClientSigner(ClientSigner):
    """EVM client signer implementation using web3.py"""

    def __init__(self, private_key: str, network: str | None = None) -> None:
        if not private_key.startswith("0x"):
            private_key = "0x" + private_key
        self._private_key = private_key
        self._network = network
        self._address = self._derive_address(private_key)
        self._async_web3_clients: dict[str, Any] = {}
        logger.debug(
            "EvmClientSigner initialized", extra={"address": self._address, "network": network}
        )

    @classmethod
    def from_private_key(cls, private_key: str, network: str | None = None) -> "EvmClientSigner":
        """Create signer from private key."""
        return cls(private_key, network)

    @staticmethod
    def _derive_address(private_key: str) -> str:
        """Derive EVM address from private key"""
        from eth_account import Account

        return Account.from_key(private_key).address

    def get_address(self) -> str:
        return self._address

    def _ensure_async_web3_client(self, network: str | None = None) -> Any:
        """Lazy initialize async web3 client for the given network."""
        net = network or self._network
        if not net:
            return None

        if net not in self._async_web3_clients:
            from web3 import AsyncHTTPProvider, AsyncWeb3
            from web3.middleware import ExtraDataToPOAMiddleware

            provider_uri = resolve_provider_uri(net)
            w3 = AsyncWeb3(AsyncHTTPProvider(provider_uri))
            w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
            self._async_web3_clients[net] = w3

        return self._async_web3_clients[net]

    async def sign_message(self, message: bytes) -> str:
        """Sign raw message using ECDSA (EIP-191)"""
        try:
            from eth_account import Account
            from eth_account.messages import encode_defunct

            signable = encode_defunct(primitive=message)
            signed = Account.sign_message(signable, private_key=self._private_key)
            return signed.signature.hex()
        except Exception as e:
            raise SignatureCreationError(f"Failed to sign message: {e}")

    async def sign_typed_data(
        self,
        domain: dict[str, Any],
        types: dict[str, Any],
        message: dict[str, Any],
    ) -> str:
        """Sign EIP-712 typed data."""
        try:
            from eth_account import Account
            from eth_account.messages import encode_typed_data

            # TODO: Refactor ClientSigner interface to accept primary_type explicitly
            primary_type = (
                PAYMENT_PERMIT_PRIMARY_TYPE
                if PAYMENT_PERMIT_PRIMARY_TYPE in types
                else list(types.keys())[-1]
            )

            # Build EIP712Domain type dynamically from domain keys
            # so it works for both exact_permit (no version) and exact (with version)
            domain_type = _eip712_domain_type_from_keys(domain)

            full_data = {
                "types": {"EIP712Domain": domain_type, **types},
                "domain": domain,
                "primaryType": primary_type,
                "message": message,
            }

            encoded = encode_typed_data(full_message=full_data)
            signed = Account.sign_message(encoded, private_key=self._private_key)
            return signed.signature.hex()
        except Exception as e:
            raise SignatureCreationError(f"Failed to sign typed data: {e}")

    async def check_balance(self, token: str, network: str) -> int:
        """Check ERC20 token balance"""
        w3 = self._ensure_async_web3_client(network)
        if not w3:
            return 0

        try:
            contract = w3.eth.contract(address=token, abi=ERC20_ABI)
            return await contract.functions.balanceOf(self._address).call()
        except Exception as e:
            logger.error(
                "Failed to check ERC20 balance",
                extra={"token": token, "network": network, "error": str(e)},
            )
            return 0

    async def check_allowance(self, token: str, amount: int, network: str) -> int:
        """Check ERC20 allowance"""
        spender = self._get_spender_address(network)
        w3 = self._ensure_async_web3_client(network)
        if not spender or not w3:
            return 0

        try:
            contract = w3.eth.contract(address=token, abi=ERC20_ABI)
            return await contract.functions.allowance(self._address, spender).call()
        except Exception as e:
            logger.error(
                "Failed to check ERC20 allowance",
                extra={"token": token, "spender": spender, "network": network, "error": str(e)},
            )
            return 0

    async def ensure_allowance(
        self,
        token: str,
        amount: int,
        network: str,
        mode: str = "auto",
    ) -> bool:
        """Ensure allowance is sufficient for the spender"""
        if mode == "skip":
            return True

        current = await self.check_allowance(token, amount, network)
        if current >= amount:
            return True

        if mode == "interactive":
            raise InsufficientAllowanceError("Interactive approval required")

        w3 = self._ensure_async_web3_client(network)
        if not w3:
            raise InsufficientAllowanceError("Web3 provider not configured")

        try:
            spender = self._get_spender_address(network)
            contract = w3.eth.contract(address=token, abi=ERC20_ABI)

            tx = await contract.functions.approve(spender, 2**256 - 1).build_transaction(
                {
                    "from": self._address,
                    "nonce": await w3.eth.get_transaction_count(self._address),
                    "chainId": await w3.eth.chain_id,
                }
            )

            signed_tx = w3.eth.account.sign_transaction(tx, private_key=self._private_key)
            tx_hash = await w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            receipt = await w3.eth.wait_for_transaction_receipt(tx_hash)

            success = receipt.status == 1
            if success:
                logger.info(
                    "ERC20 approval successful",
                    extra={"token": token, "tx_hash": tx_hash.hex()},
                )
            return success
        except Exception as e:
            raise InsufficientAllowanceError(f"ERC20 approval transaction failed: {e}")

    def _get_spender_address(self, network: str) -> str:
        return NetworkConfig.get_payment_permit_address(network)
