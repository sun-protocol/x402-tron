"""
EvmClientSigner - EVM client signer implementation
"""

import json
import logging
from typing import Any, Optional

from x402_tron.abi import EIP712_DOMAIN_TYPE, ERC20_ABI, PAYMENT_PERMIT_PRIMARY_TYPE
from x402_tron.config import NetworkConfig
from x402_tron.exceptions import InsufficientAllowanceError, SignatureCreationError
from x402_tron.signers.client.base import ClientSigner

logger = logging.getLogger(__name__)


class EvmClientSigner(ClientSigner):
    """EVM client signer implementation"""

    def __init__(self, private_key: str, network: str | None = None) -> None:
        if not private_key.startswith("0x"):
            private_key = "0x" + private_key
        self._private_key = private_key
        self._network = network
        self._address = self._derive_address(private_key)
        self._async_web3_clients: dict[str, Any] = {}
        logger.info(f"EvmClientSigner initialized: address={self._address}, network={network}")

    @classmethod
    def from_private_key(cls, private_key: str, network: str | None = None) -> "EvmClientSigner":
        """Create signer from private key.

        Args:
            private_key: EVM private key (hex string)
            network: Optional EVM network identifier

        Returns:
            EvmClientSigner instance
        """
        return cls(private_key, network)

    @staticmethod
    def _derive_address(private_key: str) -> str:
        """Derive EVM address from private key"""
        try:
            from eth_account import Account

            account = Account.from_key(private_key)
            return account.address
        except ImportError:
            # Fallback (should not happen if eth_account is installed)
            return f"0x{private_key[-40:]}"

    def get_address(self) -> str:
        return self._address

    def _ensure_async_web3_client(self, network: str | None = None) -> Any:
        """Lazy initialize async web3 client for the given network.

        Args:
            network: Network identifier. Falls back to self._network if None.

        Returns:
            web3.AsyncWeb3 instance or None
        """
        net = network or self._network
        if not net:
            return None
        if net not in self._async_web3_clients:
            try:
                from web3 import AsyncHTTPProvider, AsyncWeb3

                # Simple logic: if network starts with http/ws, use it as provider
                provider_uri = None
                if net.startswith("http") or net.startswith("ws"):
                    provider_uri = net

                if provider_uri:
                    self._async_web3_clients[net] = AsyncWeb3(AsyncHTTPProvider(provider_uri))
                else:
                    # Fallback to default provider (env var)
                    # Use clean session for async
                    self._async_web3_clients[net] = AsyncWeb3(AsyncHTTPProvider())
            except ImportError:
                return None
        return self._async_web3_clients[net]

    async def sign_message(self, message: bytes) -> str:
        """Sign raw message using ECDSA (EIP-191)"""
        try:
            from eth_account import Account
            from eth_account.messages import encode_defunct

            signable = encode_defunct(primitive=message)
            signed = Account.sign_message(signable, private_key=self._private_key)
            return signed.signature.hex()
        except ImportError:
            raise SignatureCreationError("eth_account is required for signing")

    async def sign_typed_data(
        self,
        domain: dict[str, Any],
        types: dict[str, Any],
        message: dict[str, Any],
    ) -> str:
        """Sign EIP-712 typed data.

        TODO: Update interface to accept primary_type explicitly.
        """
        try:
            from eth_account import Account
            from eth_account.messages import encode_typed_data

            # Determine primary type from types dict (should be the last/main type)
            # For PaymentPermit, the main type is "PaymentPermitDetails"
            primary_type = (
                PAYMENT_PERMIT_PRIMARY_TYPE
                if PAYMENT_PERMIT_PRIMARY_TYPE in types
                else list(types.keys())[-1]
            )

            # Construct full types including EIP712Domain
            full_types = {
                "EIP712Domain": EIP712_DOMAIN_TYPE,
                **types,
            }

            full_data = {
                "types": full_types,
                "domain": domain,
                "primaryType": primary_type,
                "message": message,
            }

            encoded = encode_typed_data(full_message=full_data)
            signed = Account.sign_message(encoded, private_key=self._private_key)
            return signed.signature.hex()

        except ImportError:
            raise SignatureCreationError("eth_account is required for signing")

    async def check_balance(
        self,
        token: str,
        network: str,
    ) -> int:
        """Check ERC20 token balance"""
        w3 = self._ensure_async_web3_client(network)
        if not w3:
            logger.warning("Web3 client not available, returning 0 balance")
            return 0

        try:
            contract = w3.eth.contract(address=token, abi=ERC20_ABI)
            balance = await contract.functions.balanceOf(self._address).call()
            return balance
        except Exception as e:
            logger.error(f"Failed to check balance: {e}")
            return 0

    async def check_allowance(
        self,
        token: str,
        amount: int,
        network: str,
    ) -> int:
        """Check ERC20 allowance"""
        spender = self._get_spender_address(network)
        if not spender:
            return 0

        w3 = self._ensure_async_web3_client(network)
        if not w3:
            logger.warning("Web3 client not available, returning 0 allowance")
            return 0

        try:
            contract = w3.eth.contract(address=token, abi=ERC20_ABI)
            allowance = await contract.functions.allowance(self._address, spender).call()
            return allowance
        except Exception as e:
            logger.error(f"Failed to check allowance: {e}")
            return 0

    async def ensure_allowance(
        self,
        token: str,
        amount: int,
        network: str,
        mode: str = "auto",
    ) -> bool:
        """Ensure allowance"""
        if mode == "skip":
            return True

        current = await self.check_allowance(token, amount, network)
        if current >= amount:
            return True

        if mode == "interactive":
            raise NotImplementedError("Interactive approval not implemented")

        w3 = self._ensure_async_web3_client(network)
        if not w3:
            raise InsufficientAllowanceError("Web3 client required for approval")

        try:
            spender = self._get_spender_address(network)
            max_uint256 = 2**256 - 1
            contract = w3.eth.contract(address=token, abi=ERC20_ABI)

            nonce = await w3.eth.get_transaction_count(self._address)
            chain_id = await w3.eth.chain_id

            # Basic transaction build - might need gas estimation/price
            tx = await contract.functions.approve(spender, max_uint256).build_transaction({
                'from': self._address,
                'nonce': nonce,
                'chainId': chain_id,
            })

            signed_tx = w3.eth.account.sign_transaction(tx, private_key=self._private_key)
            tx_hash = await w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            receipt = await w3.eth.wait_for_transaction_receipt(tx_hash)

            return receipt.status == 1

        except Exception as e:
            raise InsufficientAllowanceError(f"Approval failed: {e}")

    def _get_spender_address(self, network: str) -> str:
        """Get payment permit contract address (spender)"""
        return NetworkConfig.get_payment_permit_address(network)
