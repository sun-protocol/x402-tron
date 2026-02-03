"""
BaseUptoClientMechanism - Base class for "upto" payment scheme client mechanisms.

Extracts common logic from EVM and TRON implementations.
"""

import logging
from abc import abstractmethod
from typing import Any, TYPE_CHECKING

from x402.abi import get_payment_permit_eip712_types
from x402.address import AddressConverter
from x402.config import NetworkConfig
from x402.mechanisms.client.base import ClientMechanism
from x402.types import (
    PaymentPayload,
    PaymentPayloadData,
    PaymentPermit,
    PaymentRequirements,
    PermitMeta,
    Payment,
    Fee,
    Delivery,
    ResourceInfo,
    PAYMENT_ONLY,
)
from x402.utils import convert_permit_to_eip712_message

if TYPE_CHECKING:
    from x402.signers.client import ClientSigner


class BaseUptoClientMechanism(ClientMechanism):
    """Base class for upto payment scheme client mechanisms.
    
    Subclasses only need to implement _get_address_converter() method.
    """

    def __init__(self, signer: "ClientSigner") -> None:
        self._signer = signer
        self._address_converter = self._get_address_converter()
        self._logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def _get_address_converter(self) -> AddressConverter:
        """Get address converter, implemented by subclasses"""
        pass

    def scheme(self) -> str:
        return "exact"

    async def create_payment_payload(
        self,
        requirements: PaymentRequirements,
        resource: str,
        extensions: dict[str, Any] | None = None,
    ) -> PaymentPayload:
        """Create payment payload with EIP-712 signature"""
        self._logger.info("=" * 60)
        self._logger.info(f"Creating payment payload for: {resource}")
        
        # Log payment details
        self._logger.info(f"[PAYMENT] Token: {requirements.asset}")
        self._logger.info(f"[PAYMENT] From: {self._signer.get_address()}")
        self._logger.info(f"[PAYMENT] To: {requirements.pay_to}")
        self._logger.info(f"[PAYMENT] Amount: {requirements.amount}")
        
        # Log fee details
        if requirements.extra and requirements.extra.fee:
            fee = requirements.extra.fee
            self._logger.info(f"[FEE] To: {fee.fee_to}")
            self._logger.info(f"[FEE] Amount: {fee.fee_amount}")
            total = int(requirements.amount) + int(fee.fee_amount)
            self._logger.info(f"[TOTAL] {total} = {requirements.amount} (payment) + {fee.fee_amount} (fee)")
        else:
            self._logger.info(f"[FEE] None")
            self._logger.info(f"[TOTAL] {requirements.amount}")

        context = extensions.get("paymentPermitContext") if extensions else None
        if context is None:
            raise ValueError("paymentPermitContext is required")

        permit = self._build_permit(requirements, context)
        self._logger.debug(f"Buyer address: {permit.buyer}, paymentId: {permit.meta.payment_id}")

        await self._ensure_allowance(permit, requirements.network)

        self._logger.info("Signing payment permit with EIP-712...")
        signature = await self._sign_permit(permit, requirements.network)

        self._logger.info(f"Payment payload created successfully")
        self._logger.info("=" * 60)
        return PaymentPayload(
            x402Version=2,
            resource=ResourceInfo(url=resource),
            accepted=requirements,
            payload=PaymentPayloadData(
                signature=signature,
                paymentPermit=permit,
            ),
            extensions={},
        )

    def _build_permit(
        self,
        requirements: PaymentRequirements,
        context: dict[str, Any],
    ) -> PaymentPermit:
        """Build PaymentPermit from requirements and context"""
        buyer_address = self._signer.get_address()
        meta = context.get("meta", {})
        delivery = context.get("delivery", {})
        converter = self._address_converter

        fee_to = converter.get_zero_address()
        fee_amount = "0"
        if requirements.extra and requirements.extra.fee:
            fee_to = requirements.extra.fee.fee_to
            fee_amount = requirements.extra.fee.fee_amount

        caller = context.get("caller") or converter.get_zero_address()

        # Normalize addresses (required for TRON, EVM returns as-is)
        return PaymentPermit(
            meta=PermitMeta(
                kind=meta.get("kind", PAYMENT_ONLY),
                paymentId=meta.get("paymentId", ""),
                nonce=str(meta.get("nonce", "0")),
                validAfter=meta.get("validAfter", 0),
                validBefore=meta.get("validBefore", 0),
            ),
            buyer=buyer_address,
            caller=caller,
            payment=Payment(
                payToken=converter.normalize(requirements.asset),
                maxPayAmount=requirements.amount,
                payTo=converter.normalize(requirements.pay_to),
            ),
            fee=Fee(
                feeTo=fee_to,
                feeAmount=fee_amount,
            ),
            delivery=Delivery(
                receiveToken=converter.normalize(
                    delivery.get("receiveToken", converter.get_zero_address())
                ),
                miniReceiveAmount=str(delivery.get("miniReceiveAmount", "0")),
                tokenId=str(delivery.get("tokenId", "0")),
            ),
        )

    async def _ensure_allowance(self, permit: PaymentPermit, network: str) -> None:
        """Ensure token allowance is sufficient for payment + fee"""
        total_amount = int(permit.payment.max_pay_amount) + int(permit.fee.fee_amount)
        self._logger.info(
            f"Total amount (payment + fee): {total_amount} = "
            f"{permit.payment.max_pay_amount} + {permit.fee.fee_amount}"
        )

        await self._signer.ensure_allowance(
            permit.payment.pay_token,
            total_amount,
            network,
        )

    async def _sign_permit(self, permit: PaymentPermit, network: str) -> str:
        """Sign permit with EIP-712"""
        permit_address = NetworkConfig.get_payment_permit_address(network)
        chain_id = NetworkConfig.get_chain_id(network)
        converter = self._address_converter

        # Convert permit to EIP-712 message format
        message = convert_permit_to_eip712_message(permit)
        # Convert addresses to EVM format (required for TRON, EVM returns as-is)
        message = converter.convert_message_addresses(message)

        return await self._signer.sign_typed_data(
            domain={
                "name": "PaymentPermit",
                "chainId": chain_id,
                "verifyingContract": converter.to_evm_format(permit_address),
            },
            types=get_payment_permit_eip712_types(),
            message=message,
        )
