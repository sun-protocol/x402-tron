"""
NativeExactTronFacilitatorMechanism - native_exact facilitator mechanism for TRON.

Verifies TransferWithAuthorization signatures and settles by calling
transferWithAuthorization on the token contract.
"""

import logging
import time
from typing import TYPE_CHECKING, Any

from x402_tron.address import TronAddressConverter
from x402_tron.config import NetworkConfig
from x402_tron.mechanisms.facilitator.base import FacilitatorMechanism
from x402_tron.mechanisms.native_exact.types import (
    SCHEME_NATIVE_EXACT,
    TRANSFER_AUTH_EIP712_TYPES,
    TransferAuthorization,
    build_eip712_domain,
    build_eip712_message,
    get_transfer_with_authorization_abi_json,
)
from x402_tron.tokens import TokenRegistry
from x402_tron.types import (
    FeeInfo,
    FeeQuoteResponse,
    PaymentPayload,
    PaymentRequirements,
    SettleResponse,
    VerifyResponse,
)

if TYPE_CHECKING:
    from x402_tron.signers.facilitator import FacilitatorSigner

logger = logging.getLogger(__name__)

class NativeExactTronFacilitatorMechanism(FacilitatorMechanism):
    """TransferWithAuthorization facilitator mechanism for TRON.

    Note: native_exact only supports a single transfer per authorization,
    so the facilitator cannot collect fees from the payment itself.
    fee_quote always returns feeAmount=0.
    """

    def __init__(
        self,
        signer: "FacilitatorSigner",
        allowed_tokens: set[str] | None = None,
    ) -> None:
        self._signer = signer
        self._converter = TronAddressConverter()
        self._allowed_tokens: set[str] | None = (
            {self._converter.normalize(t) for t in allowed_tokens}
            if allowed_tokens is not None
            else None
        )

    def scheme(self) -> str:
        return SCHEME_NATIVE_EXACT

    # ------------------------------------------------------------------
    # fee_quote
    # ------------------------------------------------------------------

    async def fee_quote(
        self,
        accept: PaymentRequirements,
        context: dict[str, Any] | None = None,
    ) -> FeeQuoteResponse | None:
        return FeeQuoteResponse(
            fee=FeeInfo(feeTo=self._signer.get_address(), feeAmount="0"),
            pricing="flat",
            scheme=accept.scheme,
            network=accept.network,
            asset=accept.asset,
            expiresAt=int(time.time()) + 300,
        )

    # ------------------------------------------------------------------
    # verify
    # ------------------------------------------------------------------

    async def verify(
        self,
        payload: PaymentPayload,
        requirements: PaymentRequirements,
    ) -> VerifyResponse:
        auth = self._extract_authorization(payload)
        if auth is None:
            return VerifyResponse(isValid=False, invalidReason="missing_transfer_authorization")

        # Basic field validation
        error = self._validate_authorization(auth, requirements)
        if error:
            return VerifyResponse(isValid=False, invalidReason=error)

        # Verify EIP-712 signature
        is_valid = await self._verify_signature(auth, payload.payload.signature, requirements)
        if not is_valid:
            return VerifyResponse(isValid=False, invalidReason="invalid_signature")

        return VerifyResponse(isValid=True)

    # ------------------------------------------------------------------
    # settle
    # ------------------------------------------------------------------

    async def settle(
        self,
        payload: PaymentPayload,
        requirements: PaymentRequirements,
    ) -> SettleResponse:
        # Verify first
        verify_result = await self.verify(payload, requirements)
        if not verify_result.is_valid:
            return SettleResponse(
                success=False,
                errorReason=verify_result.invalid_reason,
                network=requirements.network,
            )

        auth = self._extract_authorization(payload)
        signature = payload.payload.signature

        # Split signature into v, r, s
        sig_bytes = bytes.fromhex(signature[2:] if signature.startswith("0x") else signature)
        if len(sig_bytes) != 65:
            return SettleResponse(
                success=False,
                errorReason="invalid_signature_length",
                network=requirements.network,
            )
        r = sig_bytes[:32]
        s = sig_bytes[32:64]
        v = sig_bytes[64]
        # Normalize v value (some signers return 0/1 instead of 27/28)
        if v < 27:
            v += 27

        nonce_bytes = bytes.fromhex(
            auth.nonce[2:] if auth.nonce.startswith("0x") else auth.nonce
        )

        converter = self._converter
        token_address = requirements.asset

        args = [
            converter.normalize(auth.from_address),
            converter.normalize(auth.to),
            int(auth.value),
            int(auth.valid_after),
            int(auth.valid_before),
            nonce_bytes,
            v,
            r,
            s,
        ]

        logger.info(
            "[NATIVE-EXACT] Calling transferWithAuthorization on token=%s",
            token_address,
        )

        tx_hash = await self._signer.write_contract(
            contract_address=token_address,
            abi=get_transfer_with_authorization_abi_json(),
            method="transferWithAuthorization",
            args=args,
            network=requirements.network,
        )

        if tx_hash is None:
            return SettleResponse(
                success=False,
                errorReason="transaction_failed",
                network=requirements.network,
            )

        receipt = await self._signer.wait_for_transaction_receipt(
            tx_hash, network=requirements.network
        )
        tx_status = receipt.get("status", "").lower() if isinstance(receipt.get("status"), str) else receipt.get("status")
        if tx_status == "failed" or tx_status == "0" or tx_status == 0:
            return SettleResponse(
                success=False,
                errorReason="transaction_failed_on_chain",
                transaction=tx_hash,
                network=requirements.network,
            )

        return SettleResponse(
            success=True,
            transaction=tx_hash,
            network=requirements.network,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_authorization(self, payload: PaymentPayload) -> TransferAuthorization | None:
        """Extract transfer authorization from payload extensions."""
        ext = payload.extensions or {}
        auth_data = ext.get("transferAuthorization")
        if auth_data is None:
            return None
        try:
            return TransferAuthorization(**auth_data)
        except Exception:
            return None

    def _validate_authorization(
        self,
        auth: TransferAuthorization,
        requirements: PaymentRequirements,
    ) -> str | None:
        norm = self._converter.normalize

        # Token whitelist
        if self._allowed_tokens is not None:
            if norm(requirements.asset) not in self._allowed_tokens:
                return "token_not_allowed"

        # Amount check
        if int(auth.value) < int(requirements.amount):
            return "amount_mismatch"

        # Recipient check
        if norm(auth.to) != norm(requirements.pay_to):
            return "payto_mismatch"

        # Time window
        now = int(time.time())
        if int(auth.valid_before) < now:
            return "expired"
        if int(auth.valid_after) > now:
            return "not_yet_valid"

        return None

    async def _verify_signature(
        self,
        auth: TransferAuthorization,
        signature: str,
        requirements: PaymentRequirements,
    ) -> bool:
        converter = self._converter
        token_address = requirements.asset
        chain_id = NetworkConfig.get_chain_id(requirements.network)

        token_info = TokenRegistry.find_by_address(requirements.network, token_address)
        token_name = token_info.name if token_info else "Unknown Token"
        token_version = token_info.version if token_info else "1"

        domain = build_eip712_domain(
            token_name, token_version, chain_id,
            converter.to_evm_format(token_address),
        )
        message = build_eip712_message(auth, converter.to_evm_format)

        return await self._signer.verify_typed_data(
            address=auth.from_address,
            domain=domain,
            types=TRANSFER_AUTH_EIP712_TYPES,
            message=message,
            signature=signature,
        )
