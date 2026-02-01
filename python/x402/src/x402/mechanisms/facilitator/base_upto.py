"""
BaseUptoFacilitatorMechanism - Base class for "upto" payment scheme facilitator mechanisms.

Extracts common logic from EVM and TRON implementations.
"""

import logging
import time
from abc import abstractmethod
from typing import Any, TYPE_CHECKING

from x402.abi import PAYMENT_PERMIT_ABI, MERCHANT_ABI, get_abi_json, get_payment_permit_eip712_types
from x402.address import AddressConverter
from x402.config import NetworkConfig
from x402.exceptions import PermitValidationError
from x402.mechanisms.facilitator.base import FacilitatorMechanism
from x402.types import (
    PaymentPayload,
    PaymentRequirements,
    VerifyResponse,
    SettleResponse,
    FeeQuoteResponse,
    FeeInfo,
    KIND_MAP,
    PAYMENT_AND_DELIVERY,
)
from x402.utils import convert_permit_to_eip712_message, payment_id_to_bytes

if TYPE_CHECKING:
    from x402.signers.facilitator import FacilitatorSigner


# Configuration constants
DEFAULT_BASE_FEE = 1_000_000
FEE_QUOTE_EXPIRY_SECONDS = 300


class BaseUptoFacilitatorMechanism(FacilitatorMechanism):
    """Base class for upto payment scheme facilitator mechanisms.
    
    Subclasses only need to implement _get_address_converter() method.
    """

    def __init__(
        self,
        signer: "FacilitatorSigner",
        fee_to: str | None = None,
        base_fee: int = DEFAULT_BASE_FEE,
    ) -> None:
        self._signer = signer
        self._fee_to = fee_to or signer.get_address()
        self._base_fee = base_fee
        self._address_converter = self._get_address_converter()
        self._logger = logging.getLogger(self.__class__.__name__)
        self._logger.info(f"Initialized: fee_to={self._fee_to}, base_fee={base_fee}")

    @abstractmethod
    def _get_address_converter(self) -> AddressConverter:
        """Get address converter, implemented by subclasses"""
        pass

    def scheme(self) -> str:
        return "exact"

    async def fee_quote(
        self,
        accept: PaymentRequirements,
        context: dict[str, Any] | None = None,
    ) -> FeeQuoteResponse:
        """Calculate fee quote based on gas estimation"""
        fee_amount = str(self._base_fee)
        self._logger.info(
            f"Fee quote requested: network={accept.network}, "
            f"amount={accept.amount}, fee={fee_amount}"
        )

        return FeeQuoteResponse(
            fee=FeeInfo(
                feeTo=self._fee_to,
                feeAmount=fee_amount,
            ),
            pricing="per_accept",
            network=accept.network,
            expiresAt=int(time.time()) + FEE_QUOTE_EXPIRY_SECONDS,
        )

    async def verify(
        self,
        payload: PaymentPayload,
        requirements: PaymentRequirements,
    ) -> VerifyResponse:
        """Verify payment signature"""
        permit = payload.payload.payment_permit
        self._logger.info(
            f"Verifying payment: paymentId={permit.meta.payment_id}, "
            f"buyer={permit.buyer}, amount={permit.payment.max_pay_amount}"
        )

        # Validate permit matches requirements
        validation_error = self._validate_permit(permit, requirements)
        if validation_error:
            self._logger.warning(f"Validation failed: {validation_error}")
            return VerifyResponse(isValid=False, invalidReason=validation_error)

        # Verify EIP-712 signature
        self._logger.info("Verifying EIP-712 signature...")
        is_valid = await self._verify_signature(
            permit,
            payload.payload.signature,
            requirements.network,
        )

        if not is_valid:
            self._logger.warning("Invalid signature")
            return VerifyResponse(isValid=False, invalidReason="invalid_signature")

        self._logger.info("Payment verification successful")
        return VerifyResponse(isValid=True)

    async def settle(
        self,
        payload: PaymentPayload,
        requirements: PaymentRequirements,
    ) -> SettleResponse:
        """Execute payment settlement"""
        permit = payload.payload.payment_permit
        self._logger.info(
            f"Starting settlement: paymentId={permit.meta.payment_id}, "
            f"kind={permit.meta.kind}, network={requirements.network}"
        )

        # Verify first
        verify_result = await self.verify(payload, requirements)
        if not verify_result.is_valid:
            self._logger.error(
                f"Settlement failed: verification failed - {verify_result.invalid_reason}"
            )
            return SettleResponse(
                success=False,
                errorReason=verify_result.invalid_reason,
                network=requirements.network,
            )

        signature = payload.payload.signature

        # Choose settlement method based on delivery mode
        if permit.meta.kind == PAYMENT_AND_DELIVERY:
            self._logger.info("Settling with delivery via merchant contract...")
            tx_hash = await self._settle_with_delivery(permit, signature, requirements)
        else:
            self._logger.info("Settling payment only via PaymentPermit contract...")
            tx_hash = await self._settle_payment_only(permit, signature, requirements)

        if tx_hash is None:
            self._logger.error("Settlement transaction failed: no transaction hash returned")
            return SettleResponse(
                success=False,
                errorReason="transaction_failed",
                network=requirements.network,
            )

        self._logger.info(f"Transaction broadcast successful: txHash={tx_hash}")
        self._logger.info("Waiting for transaction receipt...")
        receipt = await self._signer.wait_for_transaction_receipt(tx_hash)
        self._logger.info(f"Transaction confirmed: {receipt}")

        # Validate transaction status
        tx_status = receipt.get('status', '').lower()
        if tx_status == 'failed' or tx_status == '0' or tx_status == 0:
            self._logger.error(
                f"Transaction failed on-chain: txHash={tx_hash}, receipt={receipt}"
            )
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

    def _validate_permit(self, permit: Any, requirements: PaymentRequirements) -> str | None:
        """Validate permit matches requirements, returns error reason or None"""
        if int(permit.payment.max_pay_amount) < int(requirements.amount):
            self._logger.warning(
                f"Amount mismatch: {permit.payment.max_pay_amount} < {requirements.amount}"
            )
            return "amount_mismatch"

        # Address comparison (case-insensitive)
        if permit.payment.pay_to.lower() != requirements.pay_to.lower():
            self._logger.warning(
                f"PayTo mismatch: {permit.payment.pay_to} != {requirements.pay_to}"
            )
            return "payto_mismatch"

        if permit.payment.pay_token.lower() != requirements.asset.lower():
            self._logger.warning(
                f"Token mismatch: {permit.payment.pay_token} != {requirements.asset}"
            )
            return "token_mismatch"

        now = int(time.time())
        if permit.meta.valid_before < now:
            self._logger.warning(
                f"Permit expired: validBefore={permit.meta.valid_before} < now={now}"
            )
            return "expired"

        if permit.meta.valid_after > now:
            self._logger.warning(
                f"Permit not yet valid: validAfter={permit.meta.valid_after} > now={now}"
            )
            return "not_yet_valid"

        return None

    async def _verify_signature(
        self,
        permit: Any,
        signature: str,
        network: str,
    ) -> bool:
        """Verify EIP-712 signature"""
        permit_address = NetworkConfig.get_payment_permit_address(network)
        chain_id = NetworkConfig.get_chain_id(network)
        converter = self._address_converter

        message = convert_permit_to_eip712_message(permit)
        message = converter.convert_message_addresses(message)

        return await self._signer.verify_typed_data(
            address=permit.buyer,
            domain={
                "name": "PaymentPermit",
                "chainId": chain_id,
                "verifyingContract": converter.to_evm_format(permit_address),
            },
            types=get_payment_permit_eip712_types(),
            message=message,
            signature=signature,
        )

    @abstractmethod
    async def _settle_payment_only(
        self,
        permit: Any,
        signature: str,
        requirements: PaymentRequirements,
    ) -> str | None:
        """Payment only settlement (no on-chain delivery), implemented by subclasses"""
        pass

    @abstractmethod
    async def _settle_with_delivery(
        self,
        permit: Any,
        signature: str,
        requirements: PaymentRequirements,
    ) -> str | None:
        """Settlement with on-chain delivery, implemented by subclasses"""
        pass

    def _build_permit_tuple(self, permit: Any) -> tuple:
        """Build permit tuple for contract call"""
        converter = self._address_converter

        payment_id = permit.meta.payment_id
        if isinstance(payment_id, str):
            payment_id = payment_id_to_bytes(payment_id)

        buyer = converter.normalize(permit.buyer)
        caller = converter.normalize(permit.caller)
        pay_token = converter.normalize(permit.payment.pay_token)
        pay_to = converter.normalize(permit.payment.pay_to)
        fee_to = converter.normalize(permit.fee.fee_to)
        receive_token = converter.normalize(permit.delivery.receive_token)

        return (
            (  # meta tuple
                KIND_MAP.get(permit.meta.kind, 0),
                payment_id,
                int(permit.meta.nonce),
                permit.meta.valid_after,
                permit.meta.valid_before,
            ),
            buyer,
            caller,
            (pay_token, int(permit.payment.max_pay_amount), pay_to),
            (fee_to, int(permit.fee.fee_amount)),
            (receive_token, int(permit.delivery.mini_receive_amount), int(permit.delivery.token_id)),
        )
