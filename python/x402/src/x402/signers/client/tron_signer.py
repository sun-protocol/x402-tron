"""
TronClientSigner - TRON client signer implementation
"""

import json
import logging
from typing import Any

from x402.abi import ERC20_ABI, PAYMENT_PERMIT_PRIMARY_TYPE, EIP712_DOMAIN_TYPE
from x402.config import NetworkConfig
from x402.signers.client.base import ClientSigner

logger = logging.getLogger(__name__)


class TronClientSigner(ClientSigner):
    """TRON client signer implementation"""

    def __init__(self, private_key: str, network: str | None = None) -> None:
        clean_key = private_key[2:] if private_key.startswith("0x") else private_key
        self._private_key = clean_key
        self._address = self._derive_address(clean_key)
        self._network = network
        self._tron_client: Any = None
        logger.info(f"TronClientSigner initialized: address={self._address}, network={network}")

    @classmethod
    def from_private_key(cls, private_key: str, network: str | None = None) -> "TronClientSigner":
        """Create signer from private key.

        Args:
            private_key: TRON private key (hex string)
            network: Optional TRON network (mainnet/shasta/nile) for lazy client initialization

        Returns:
            TronClientSigner instance
        """
        return cls(private_key, network)

    def _ensure_tron_client(self) -> Any:
        """Lazy initialize tron_client.

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
        """Sign EIP-712 typed data.
        
        Note: The primaryType is determined from the types dict.
        For PaymentPermit contract, it should be "PaymentPermitDetails".
        """
        # Determine primary type from types dict (should be the last/main type)
        # For PaymentPermit, the main type is "PaymentPermitDetails"
        primary_type = PAYMENT_PERMIT_PRIMARY_TYPE if PAYMENT_PERMIT_PRIMARY_TYPE in types else list(types.keys())[-1]
        logger.info(f"Signing EIP-712 typed data: domain={domain.get('name')}, primaryType={primary_type}")
        try:
            from eth_account import Account
            from eth_account.messages import encode_typed_data

            # Note: PaymentPermit contract uses EIP712Domain WITHOUT version field
            # Contract: keccak256("EIP712Domain(string name,uint256 chainId,address verifyingContract)")
            full_types = {
                "EIP712Domain": EIP712_DOMAIN_TYPE,
                **types,
            }

            typed_data = {
                "types": full_types,
                "primaryType": primary_type,
                "domain": domain,
                "message": message,
            }

            # Log domain and message in same format as TypeScript client
            import json as json_module
            # Convert bytes to hex for logging
            message_for_log = dict(message)
            if 'meta' in message_for_log and 'paymentId' in message_for_log['meta']:
                pid = message_for_log['meta']['paymentId']
                if isinstance(pid, bytes):
                    message_for_log['meta'] = dict(message_for_log['meta'])
                    message_for_log['meta']['paymentId'] = '0x' + pid.hex()
            
            logger.info(f"[SIGN] Domain: {json_module.dumps(domain)}")
            logger.info(f"[SIGN] Message: {json_module.dumps(message_for_log)}")

            signable = encode_typed_data(full_message=typed_data)
            # Convert hex private key to bytes for eth_account
            private_key_bytes = bytes.fromhex(self._private_key)
            signed_message = Account.sign_message(signable, private_key_bytes)
            
            signature = signed_message.signature.hex()
            logger.info(f"[SIGN] Signature: 0x{signature}")
            return signature
        except ImportError:
            logger.warning("eth_account not available, using fallback signing")
            data_str = json.dumps({"domain": domain, "types": types, "message": message})
            return await self.sign_message(data_str.encode())

    async def check_allowance(
        self,
        token: str,
        amount: int,
        network: str,
    ) -> int:
        """Check token allowance on TRON"""
        spender = self._get_spender_address(network)
        logger.info(f"Checking allowance: token={token}, owner={self._address}, spender={spender}, network={network}")
        if not spender or spender == "T0000000000000000000000000000000":
            logger.warning(f"Invalid spender address for network {network}, skipping allowance check")
            return 0
        
        client = self._ensure_tron_client()
        if client is None:
            logger.warning("Tron client not available, returning 0 allowance")
            return 0

        try:
            contract = client.get_contract(token)
            contract.abi = ERC20_ABI
            allowance = contract.functions.allowance(
                self._address,
                spender,
            )
            allowance_int = int(allowance)
            logger.info(f"Current allowance: {allowance_int}")
            return allowance_int
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
        """Ensure sufficient allowance"""
        logger.info(f"Ensuring allowance: token={token}, amount={amount}, network={network}, mode={mode}")
        if mode == "skip":
            logger.info("Skipping allowance check (mode=skip)")
            return True

        current = await self.check_allowance(token, amount, network)
        if current >= amount:
            logger.info(f"Sufficient allowance already exists: {current} >= {amount}")
            return True

        if mode == "interactive":
            raise NotImplementedError("Interactive approval not implemented")

        logger.info(f"Insufficient allowance ({current} < {amount}), requesting approval...")
        client = self._ensure_tron_client()
        if client is None:
            raise RuntimeError("tronpy client required for approval")

        try:
            from tronpy.keys import PrivateKey
            spender = self._get_spender_address(network)
            logger.info(f"Approving spender={spender} for amount={amount}")
            contract = client.get_contract(token)
            contract.abi = ERC20_ABI
            txn = (
                contract.functions.approve(
                    spender,
                    amount,
                )
                .with_owner(self._address)
                .fee_limit(100_000_000)
                .build()
                .sign(PrivateKey(bytes.fromhex(self._private_key)))
            )
            logger.info("Broadcasting approval transaction...")
            result = txn.broadcast().wait()
            # Check receipt.result for success (TRON returns "SUCCESS" in receipt)
            receipt = result.get("receipt", {})
            receipt_result = receipt.get("result", "")
            success = receipt_result == "SUCCESS"
            if success:
                logger.info(f"Approval successful: txid={result.get('id')}")
            else:
                logger.warning(f"Approval failed: {result}")
            return success
        except Exception as e:
            logger.error(f"Approval transaction failed: {e}")
            return False

    def _get_spender_address(self, network: str) -> str:
        """Get payment permit contract address (spender)"""
        return NetworkConfig.get_payment_permit_address(network)
