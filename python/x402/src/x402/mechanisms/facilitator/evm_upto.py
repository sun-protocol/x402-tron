"""
UptoEvmFacilitatorMechanism - "upto" 支付方案的 EVM facilitator 机制
"""

import json
import time
from typing import Any, TYPE_CHECKING

from x402.abi import PAYMENT_PERMIT_ABI, MERCHANT_ABI, get_abi_json, get_payment_permit_eip712_types
from x402.mechanisms.facilitator.base import FacilitatorMechanism
from x402.types import (
    PaymentPayload,
    PaymentRequirements,
    VerifyResponse,
    SettleResponse,
    FeeQuoteResponse,
    FeeInfo,
)

if TYPE_CHECKING:
    from x402.signers.facilitator import FacilitatorSigner


class UptoEvmFacilitatorMechanism(FacilitatorMechanism):
    """"upto" 支付方案的 EVM facilitator 机制"""

    def __init__(
        self,
        signer: "FacilitatorSigner",
        fee_to: str | None = None,
        base_fee: int = 1000000,
    ) -> None:
        self._signer = signer
        self._fee_to = fee_to or signer.get_address()
        self._base_fee = base_fee

    def scheme(self) -> str:
        return "exact"

    async def fee_quote(
        self,
        accept: PaymentRequirements,
        context: dict[str, Any] | None = None,
    ) -> FeeQuoteResponse:
        """基于 gas 估算计算费用报价"""
        fee_amount = str(self._base_fee)

        return FeeQuoteResponse(
            fee=FeeInfo(
                feeTo=self._fee_to,
                feeAmount=fee_amount,
            ),
            pricing="per_accept",
            network=accept.network,
            expiresAt=int(time.time()) + 300,
        )

    async def verify(
        self,
        payload: PaymentPayload,
        requirements: PaymentRequirements,
    ) -> VerifyResponse:
        """验证支付签名"""
        permit = payload.payload.payment_permit
        signature = payload.payload.signature

        if int(permit.payment.max_pay_amount) < int(requirements.amount):
            return VerifyResponse(isValid=False, invalidReason="amount_mismatch")

        if permit.payment.pay_to.lower() != requirements.pay_to.lower():
            return VerifyResponse(isValid=False, invalidReason="payto_mismatch")

        if permit.payment.pay_token.lower() != requirements.asset.lower():
            return VerifyResponse(isValid=False, invalidReason="token_mismatch")

        now = int(time.time())
        if permit.meta.valid_before < now:
            return VerifyResponse(isValid=False, invalidReason="expired")

        if permit.meta.valid_after > now:
            return VerifyResponse(isValid=False, invalidReason="not_yet_valid")

        # Get payment permit contract address and chain ID for domain
        from x402.config import NetworkConfig
        permit_address = self._get_payment_permit_address(requirements.network)
        chain_id = NetworkConfig.get_chain_id(requirements.network)
        
        # Note: Contract EIP712Domain only has (name, chainId, verifyingContract) - NO version!
        is_valid = await self._signer.verify_typed_data(
            address=permit.buyer,
            domain={
                "name": "PaymentPermit",
                "chainId": chain_id,
                "verifyingContract": permit_address,
            },
            types=get_payment_permit_eip712_types(),
            message=permit.model_dump(by_alias=True),
            signature=signature,
        )

        if not is_valid:
            return VerifyResponse(isValid=False, invalidReason="invalid_signature")

        return VerifyResponse(isValid=True)

    async def settle(
        self,
        payload: PaymentPayload,
        requirements: PaymentRequirements,
    ) -> SettleResponse:
        """Execute payment settlement on EVM"""
        verify_result = await self.verify(payload, requirements)
        if not verify_result.is_valid:
            return SettleResponse(
                success=False,
                errorReason=verify_result.invalid_reason,
                network=requirements.network,
            )

        permit = payload.payload.payment_permit
        signature = payload.payload.signature

        kind = permit.meta.kind
        if kind == "PAYMENT_AND_DELIVERY":
            tx_hash = await self._settle_with_delivery(permit, signature, requirements)
        else:
            tx_hash = await self._settle_payment_only(permit, signature, requirements)

        if tx_hash is None:
            return SettleResponse(
                success=False,
                errorReason="transaction_failed",
                network=requirements.network,
            )

        receipt = await self._signer.wait_for_transaction_receipt(tx_hash)

        return SettleResponse(
            success=True,
            transaction=tx_hash,
            network=requirements.network,
        )

    async def _settle_payment_only(
        self,
        permit: Any,
        signature: str,
        requirements: PaymentRequirements,
    ) -> str | None:
        """Settle payment only (no on-chain delivery)"""
        return await self._signer.write_contract(
            contract_address=self._get_payment_permit_address(requirements.network),
            abi=self._get_payment_permit_abi(),
            method="permitTransferFrom",
            args=[
                permit.model_dump(by_alias=True),
                permit.buyer,
                signature,
                "0x0000000000000000000000000000000000000000",
                "0x" + "00" * 32,
                "0x",
            ],
        )

    async def _settle_with_delivery(
        self,
        permit: Any,
        signature: str,
        requirements: PaymentRequirements,
    ) -> str | None:
        """Settle with on-chain delivery via merchant contract"""
        merchant_address = self._get_merchant_address(requirements)
        return await self._signer.write_contract(
            contract_address=merchant_address,
            abi=self._get_merchant_abi(),
            method="settle",
            args=[permit.model_dump(by_alias=True), signature],
        )

    def _get_payment_permit_address(self, network: str) -> str:
        """Get payment permit contract address for network"""
        addresses = {
            "eip155:1": "0x...",  # TODO: Deploy and fill
            "eip155:8453": "0x...",
            "eip155:11155111": "0x...",
        }
        return addresses.get(network, "0x0000000000000000000000000000000000000000")

    def _get_merchant_address(self, requirements: PaymentRequirements) -> str:
        """Get merchant contract address"""
        return requirements.pay_to

    def _get_payment_permit_abi(self) -> str:
        """Get payment permit contract ABI"""
        return get_abi_json(PAYMENT_PERMIT_ABI)

    def _get_merchant_abi(self) -> str:
        """Get merchant contract ABI"""
        return get_abi_json(MERCHANT_ABI)
