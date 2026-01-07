"""
X402Server - x402 协议的核心支付服务器
"""

from dataclasses import dataclass, field
from typing import Any, Protocol

from x402.types import (
    PaymentPayload,
    PaymentRequirements,
    PaymentRequired,
    PaymentRequiredExtensions,
    PaymentPermitContext,
    PaymentPermitContextMeta,
    PaymentPermitContextDelivery,
    VerifyResponse,
    SettleResponse,
    FeeQuoteResponse,
)


class ServerMechanism(Protocol):
    """服务器机制接口"""

    def scheme(self) -> str:
        """获取支付方案名称"""
        ...

    async def parse_price(self, price: str, network: str) -> dict[str, Any]:
        """将价格字符串解析为 AssetAmount"""
        ...

    async def enhance_payment_requirements(
        self,
        requirements: PaymentRequirements,
        kind: str,
    ) -> PaymentRequirements:
        """使用元数据增强支付要求"""
        ...

    def validate_payment_requirements(self, requirements: PaymentRequirements) -> bool:
        """验证支付要求"""
        ...


@dataclass
class ResourceConfig:
    """资源支付配置"""

    scheme: str
    network: str
    price: str
    pay_to: str
    valid_for: int = 3600
    delivery_mode: str = "PAYMENT_ONLY"


class X402Server:
    """
    x402 协议的核心支付服务器。

    管理支付机制和中间层客户端，协调支付流程。
    """

    def __init__(self) -> None:
        self._mechanisms: dict[str, ServerMechanism] = {}
        self._facilitators: list["FacilitatorClient"] = []

    def register(self, network: str, mechanism: ServerMechanism) -> "X402Server":
        """
        为网络注册支付机制。

        参数:
            network: 网络标识符（例如 "eip155:8453", "tron:mainnet"）
            mechanism: 服务器机制实例

        返回:
            self 以支持链式调用
        """
        self._mechanisms[network] = mechanism
        return self

    def add_facilitator(self, client: "FacilitatorClient") -> "X402Server":
        """添加 facilitator 客户端。

        Args:
            client: FacilitatorClient 实例

        Returns:
            self 以支持链式调用
        """
        self._facilitators.append(client)
        return self

    async def build_payment_requirements(
        self,
        config: ResourceConfig,
    ) -> PaymentRequirements:
        """从资源配置构建支付要求。

        Args:
            config: 资源配置

        Returns:
            PaymentRequirements
        """
        mechanism = self._mechanisms.get(config.network)
        if mechanism is None:
            raise ValueError(f"No mechanism registered for network: {config.network}")

        asset_info = await mechanism.parse_price(config.price, config.network)

        requirements = PaymentRequirements(
            scheme=config.scheme,
            network=config.network,
            amount=str(asset_info["amount"]),
            asset=asset_info["asset"],
            payTo=config.pay_to,
            maxTimeoutSeconds=config.valid_for,
        )

        requirements = await mechanism.enhance_payment_requirements(
            requirements, config.delivery_mode
        )

        if self._facilitators:
            fee_quote = await self._facilitators[0].fee_quote(requirements)
            if fee_quote and requirements.extra:
                requirements.extra.fee = fee_quote.fee

        return requirements

    def create_payment_required_response(
        self,
        requirements: list[PaymentRequirements],
        resource_info: dict[str, Any] | None = None,
        payment_id: str | None = None,
        nonce: str | None = None,
        valid_after: int | None = None,
        valid_before: int | None = None,
    ) -> PaymentRequired:
        """创建 402 Payment Required 响应。

        Args:
            requirements: 支付要求列表
            resource_info: 资源信息
            payment_id: 用于跟踪的支付 ID
            nonce: 幂等性 nonce
            valid_after: 有效起始时间戳
            valid_before: 有效截止时间戳

        Returns:
            PaymentRequired 响应
        """
        import time
        import uuid

        now = int(time.time())
        extensions = PaymentRequiredExtensions(
            paymentPermitContext=PaymentPermitContext(
                meta=PaymentPermitContextMeta(
                    kind="PAYMENT_ONLY",
                    paymentId=payment_id or str(uuid.uuid4()),
                    nonce=nonce or str(uuid.uuid4().int),
                    validAfter=valid_after or now,
                    validBefore=valid_before or (now + 3600),
                ),
                delivery=PaymentPermitContextDelivery(
                    receiveToken="T0000000000000000000000000000000",
                    miniReceiveAmount="0",
                    tokenId="0",
                ),
            )
        )

        return PaymentRequired(
            x402Version=2,
            error="Payment required",
            resource=resource_info,
            accepts=requirements,
            extensions=extensions,
        )

    async def verify_payment(
        self,
        payload: PaymentPayload,
        requirements: PaymentRequirements,
    ) -> VerifyResponse:
        """
        验证支付签名和有效性

        Args:
            payload: 客户端支付载荷
            requirements: 原始支付要求

        Returns:
            VerifyResponse
        """
        if not self._validate_payload_matches_requirements(payload, requirements):
            return VerifyResponse(isValid=False, invalidReason="payload_mismatch")

        facilitator = self._find_facilitator_for_payload(payload)
        if facilitator is None:
            return VerifyResponse(isValid=False, invalidReason="no_facilitator")

        return await facilitator.verify(payload, requirements)

    async def settle_payment(
        self,
        payload: PaymentPayload,
        requirements: PaymentRequirements,
    ) -> SettleResponse:
        """
        执行支付结算

        Args:
            payload: 客户端支付载荷
            requirements: 支付要求

        Returns:
            包含 tx_hash 的 SettleResponse
        """
        facilitator = self._find_facilitator_for_payload(payload)
        if facilitator is None:
            return SettleResponse(success=False, errorReason="no_facilitator")

        return await facilitator.settle(payload, requirements)

    def _validate_payload_matches_requirements(
        self,
        payload: PaymentPayload,
        requirements: PaymentRequirements,
    ) -> bool:
        """验证载荷与要求匹配（防篡改）"""
        permit = payload.payload.payment_permit

        if permit.payment.pay_token != requirements.asset:
            return False
        if permit.payment.pay_to != requirements.pay_to:
            return False
        if int(permit.payment.max_pay_amount) < int(requirements.amount):
            return False

        return True

    def _find_facilitator_for_payload(
        self, payload: PaymentPayload
    ) -> "FacilitatorClient | None":
        """Find facilitator for the payload"""
        if not self._facilitators:
            return None

        facilitator_id = None
        if payload.accepted.extra and payload.accepted.extra.fee:
            facilitator_id = payload.accepted.extra.fee.facilitator_id

        if facilitator_id:
            for f in self._facilitators:
                if f.facilitator_id == facilitator_id:
                    return f

        return self._facilitators[0]


from x402.facilitator.facilitator_client import FacilitatorClient
