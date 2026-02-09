"""
EvmFacilitatorSigner - EVM facilitator signer implementation
"""

import asyncio
import time
from typing import Any

from x402_tron.abi import EIP712_DOMAIN_TYPE, PAYMENT_PERMIT_PRIMARY_TYPE
from x402_tron.signers.facilitator.base import FacilitatorSigner


class EvmFacilitatorSigner(FacilitatorSigner):
    """EVM facilitator signer implementation"""

    def __init__(self, private_key: str, network: str | None = None) -> None:
        if not private_key.startswith("0x"):
            private_key = "0x" + private_key
        self._private_key = private_key
        self._network = network
        self._address = self._derive_address(private_key)
        self._async_web3_clients: dict[str, Any] = {}

    @classmethod
    def from_private_key(
        cls, private_key: str, network: str | None = None
    ) -> "EvmFacilitatorSigner":
        """Create signer from private key"""
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
        """
        net = network or self._network
        if not net:
            return None
        if net not in self._async_web3_clients:
            try:
                from web3 import AsyncHTTPProvider, AsyncWeb3

                provider_uri = None
                if net.startswith("http") or net.startswith("ws"):
                    provider_uri = net

                if provider_uri:
                    self._async_web3_clients[net] = AsyncWeb3(AsyncHTTPProvider(provider_uri))
                else:
                    self._async_web3_clients[net] = AsyncWeb3(AsyncHTTPProvider())
            except ImportError:
                return None
        return self._async_web3_clients[net]

    async def verify_typed_data(
        self,
        address: str,
        domain: dict[str, Any],
        types: dict[str, Any],
        message: dict[str, Any],
        signature: str,
    ) -> bool:
        """Verify EIP-712 signature"""
        try:
            from eth_account import Account
            from eth_account.messages import encode_typed_data

            # Note: PaymentPermit contract uses EIP712Domain WITHOUT version field
            # Contract:
            # keccak256("EIP712Domain(string name,uint256 chainId,address verifyingContract)")
            full_types = {
                "EIP712Domain": EIP712_DOMAIN_TYPE,
                **types,
            }

            # Determine primary type from types dict (should be the last/main type)
            # For PaymentPermit, the main type is "PaymentPermitDetails"
            primary_type = (
                PAYMENT_PERMIT_PRIMARY_TYPE
                if PAYMENT_PERMIT_PRIMARY_TYPE in types
                else list(types.keys())[-1]
            )

            # Convert paymentId from hex string to bytes for eth_account compatibility
            message_copy = dict(message)
            if "meta" in message_copy and "paymentId" in message_copy["meta"]:
                payment_id = message_copy["meta"]["paymentId"]
                if isinstance(payment_id, str) and payment_id.startswith("0x"):
                    message_copy["meta"] = dict(message_copy["meta"])
                    message_copy["meta"]["paymentId"] = bytes.fromhex(payment_id[2:])

            typed_data = {
                "types": full_types,
                "primaryType": primary_type,
                "domain": domain,
                "message": message_copy,
            }

            signable = encode_typed_data(full_message=typed_data)

            sig_bytes = bytes.fromhex(signature[2:] if signature.startswith("0x") else signature)
            recovered = Account.recover_message(signable, signature=sig_bytes)

            return recovered.lower() == address.lower()
        except Exception:
            return False

    async def write_contract(
        self,
        contract_address: str,
        abi: str,
        method: str,
        args: list[Any],
        network: str | None = None,
    ) -> str | None:
        """Execute contract transaction on EVM (async)."""
        w3 = self._ensure_async_web3_client(network)
        if w3 is None:
            return None

        try:
            import json
            abi_list = json.loads(abi) if isinstance(abi, str) else abi
            contract = w3.eth.contract(address=contract_address, abi=abi_list)

            func = getattr(contract.functions, method)

            # Estimate gas
            # gas_estimate = await func(*args).estimate_gas({'from': self._address})

            # Build transaction
            nonce = await w3.eth.get_transaction_count(self._address)
            chain_id = await w3.eth.chain_id

            tx = await func(*args).build_transaction({
                'from': self._address,
                'nonce': nonce,
                'chainId': chain_id,
                # 'gas': gas_estimate
            })

            signed_tx = w3.eth.account.sign_transaction(tx, private_key=self._private_key)
            tx_hash = await w3.eth.send_raw_transaction(signed_tx.rawTransaction)

            return tx_hash.hex()
        except Exception:
            return None

    async def wait_for_transaction_receipt(
        self,
        tx_hash: str,
        timeout: int = 120,
        network: str | None = None,
    ) -> dict[str, Any]:
        """Wait for EVM transaction confirmation"""
        w3 = self._ensure_async_web3_client(network)
        if w3 is None:
            raise RuntimeError("AsyncWeb3 client required")

        try:
            receipt = await w3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout)
            return {
                "hash": tx_hash,
                "blockNumber": str(receipt["blockNumber"]),
                "status": "confirmed" if receipt["status"] == 1 else "failed",
                "receipt": receipt
            }
        except Exception as e:
            raise TimeoutError(f"Transaction {tx_hash} failed or timed out: {e}")
