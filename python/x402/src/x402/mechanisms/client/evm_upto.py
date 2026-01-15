"""
UptoEvmClientMechanism - "upto" 支付方案的 EVM 客户端机制
"""

from typing import Any, TYPE_CHECKING

from x402.abi import get_payment_permit_eip712_types
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
)

if TYPE_CHECKING:
    from x402.signers.client import ClientSigner


class UptoEvmClientMechanism(ClientMechanism):
    """"upto" 支付方案的 EVM 客户端机制"""

    def __init__(self, signer: "ClientSigner") -> None:
        self._signer = signer

    def scheme(self) -> str:
        return "exact"

    async def create_payment_payload(
        self,
        requirements: PaymentRequirements,
        resource: str,
        extensions: dict[str, Any] | None = None,
    ) -> PaymentPayload:
        """使用 EIP-712 签名创建支付载荷"""
        context = extensions.get("paymentPermitContext") if extensions else None
        if context is None:
            raise ValueError("paymentPermitContext is required")

        buyer_address = self._signer.get_address()
        meta = context.get("meta", {})
        delivery = context.get("delivery", {})

        fee_to = "0x0000000000000000000000000000000000000000"
        fee_amount = "0"
        if requirements.extra and requirements.extra.fee:
            fee_to = requirements.extra.fee.fee_to
            fee_amount = requirements.extra.fee.fee_amount

        permit = PaymentPermit(
            meta=PermitMeta(
                kind=meta.get("kind", "PAYMENT_ONLY"),
                paymentId=meta.get("paymentId", ""),
                nonce=str(meta.get("nonce", "0")),
                validAfter=meta.get("validAfter", 0),
                validBefore=meta.get("validBefore", 0),
            ),
            buyer=buyer_address,
            caller=fee_to,
            payment=Payment(
                payToken=requirements.asset,
                maxPayAmount=requirements.amount,
                payTo=requirements.pay_to,
            ),
            fee=Fee(
                feeTo=fee_to,
                feeAmount=fee_amount,
            ),
            delivery=Delivery(
                receiveToken=delivery.get("receiveToken", "0x0000000000000000000000000000000000000000"),
                miniReceiveAmount=str(delivery.get("miniReceiveAmount", "0")),
                tokenId=str(delivery.get("tokenId", "0")),
            ),
        )

        total_amount = int(permit.payment.max_pay_amount) + int(permit.fee.fee_amount)
        await self._signer.ensure_allowance(
            permit.payment.pay_token,
            total_amount,
            requirements.network,
        )

        # Get payment permit contract address and chain ID for domain
        from x402.config import NetworkConfig
        permit_address = NetworkConfig.get_payment_permit_address(requirements.network)
        chain_id = NetworkConfig.get_chain_id(requirements.network)
        
        # Note: Contract EIP712Domain only has (name, chainId, verifyingContract) - NO version!
        signature = await self._signer.sign_typed_data(
            domain={
                "name": "PaymentPermit",
                "chainId": chain_id,
                "verifyingContract": permit_address,
            },
            types=get_payment_permit_eip712_types(),
            message=permit.model_dump(by_alias=True),
        )

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
