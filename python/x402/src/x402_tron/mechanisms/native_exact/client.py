"""
NativeExactTronClientMechanism - native_exact client mechanism for TRON.

Signs TransferWithAuthorization EIP-712 typed data directly on the token contract.
No PaymentPermit contract or approve/allowance needed.
"""

import logging
from typing import TYPE_CHECKING, Any

from x402_tron.address import TronAddressConverter
from x402_tron.config import NetworkConfig
from x402_tron.mechanisms.client.base import ClientMechanism
from x402_tron.mechanisms.native_exact.types import (
    SCHEME_NATIVE_EXACT,
    TRANSFER_AUTH_EIP712_TYPES,
    TransferAuthorization,
    build_eip712_domain,
    build_eip712_message,
    create_nonce,
    create_validity_window,
)
from x402_tron.tokens import TokenRegistry
from x402_tron.types import (
    PaymentPayload,
    PaymentPayloadData,
    PaymentRequirements,
    ResourceInfo,
)

if TYPE_CHECKING:
    from x402_tron.signers.client import ClientSigner

logger = logging.getLogger(__name__)


class NativeExactTronClientMechanism(ClientMechanism):
    """TransferWithAuthorization client mechanism for TRON."""

    def __init__(self, signer: "ClientSigner") -> None:
        self._signer = signer
        self._converter = TronAddressConverter()

    def scheme(self) -> str:
        return SCHEME_NATIVE_EXACT

    def get_signer(self) -> "ClientSigner":
        return self._signer

    async def create_payment_payload(
        self,
        requirements: PaymentRequirements,
        resource: str,
        extensions: dict[str, Any] | None = None,
    ) -> PaymentPayload:
        """Create native_exact payment payload."""
        converter = self._converter
        from_addr = self._signer.get_address()
        to_addr = requirements.pay_to
        value = requirements.amount
        token_address = requirements.asset

        # Look up token metadata for EIP-712 domain
        token_info = TokenRegistry.find_by_address(requirements.network, token_address)
        token_name = token_info.name if token_info else "Unknown Token"
        token_version = token_info.version if token_info else "1"

        # Create validity window and nonce
        valid_after, valid_before = create_validity_window()
        nonce = create_nonce()

        authorization = TransferAuthorization(
            **{
                "from": from_addr,
                "to": to_addr,
                "value": value,
                "validAfter": str(valid_after),
                "validBefore": str(valid_before),
                "nonce": nonce,
            }
        )

        # Build EIP-712 domain and message from authorization
        chain_id = NetworkConfig.get_chain_id(requirements.network)
        domain = build_eip712_domain(
            token_name, token_version, chain_id,
            converter.to_evm_format(token_address),
        )
        message = build_eip712_message(authorization, converter.to_evm_format)

        logger.info(
            "[NATIVE-EXACT] Signing TransferWithAuthorization: "
            "from=%s, to=%s, value=%s, token=%s",
            from_addr, to_addr, value, token_address,
        )

        signature = await self._signer.sign_typed_data(
            domain=domain,
            types=TRANSFER_AUTH_EIP712_TYPES,
            message=message,
        )

        return PaymentPayload(
            x402Version=2,
            resource=ResourceInfo(url=resource),
            accepted=requirements,
            payload=PaymentPayloadData(
                signature=signature,
            ),
            extensions={
                "transferAuthorization": authorization.model_dump(by_alias=True),
            },
        )
