"""
X402Server - Core payment server for x402 protocol
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
    PAYMENT_ONLY,
)
from x402.config import NetworkConfig


class ServerMechanism(Protocol):
    """Server mechanism interface"""

    def scheme(self) -> str:
        """Get the payment scheme name"""
        ...

    async def parse_price(self, price: str, network: str) -> dict[str, Any]:
        """Parse price string to AssetAmount"""
        ...

    async def enhance_payment_requirements(
        self,
        requirements: PaymentRequirements,
        kind: str,
    ) -> PaymentRequirements:
        """Enhance payment requirements with metadata"""
        ...

    def validate_payment_requirements(self, requirements: PaymentRequirements) -> bool:
        """Validate payment requirements"""
        ...


@dataclass
class ResourceConfig:
    """Resource payment configuration"""

    scheme: str
    network: str
    price: str
    pay_to: str
    valid_for: int = 3600
    delivery_mode: str = PAYMENT_ONLY


class X402Server:
    """
    Core payment server for x402 protocol.

    Manages payment mechanisms and facilitator clients, coordinates payment flow.
    """

    def __init__(self, auto_register_tron: bool = True) -> None:
        """
        Initialize X402Server.
        
        Args:
            auto_register_tron: If True, automatically register TRON mechanisms for all networks
        """
        self._mechanisms: dict[str, ServerMechanism] = {}
        self._facilitators: list["FacilitatorClient"] = []
        
        if auto_register_tron:
            self._register_default_tron_mechanisms()

    def register(self, network: str, mechanism: ServerMechanism) -> "X402Server":
        """
        Register a payment mechanism for a network.

        Args:
            network: Network identifier (e.g., "eip155:8453", "tron:mainnet")
            mechanism: Server mechanism instance

        Returns:
            self for method chaining
        """
        self._mechanisms[network] = mechanism
        return self

    def _register_default_tron_mechanisms(self) -> None:
        """Register default TRON mechanisms for all networks"""
        from x402.mechanisms.server import UptoTronServerMechanism
        
        tron_mechanism = UptoTronServerMechanism()
        self.register(NetworkConfig.TRON_MAINNET, tron_mechanism)
        self.register(NetworkConfig.TRON_SHASTA, tron_mechanism)
        self.register(NetworkConfig.TRON_NILE, tron_mechanism)

    def add_facilitator(self, client: "FacilitatorClient") -> "X402Server":
        """Add a facilitator client.

        Args:
            client: FacilitatorClient instance

        Returns:
            self for method chaining
        """
        self._facilitators.append(client)
        return self

    async def build_payment_requirements(
        self,
        config: ResourceConfig,
    ) -> PaymentRequirements:
        """Build payment requirements from resource configuration.

        Args:
            config: Resource configuration

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
            facilitator = self._facilitators[0]
            fee_quote = await facilitator.fee_quote(requirements)
            if fee_quote:
                if requirements.extra is None:
                    from x402.types import PaymentRequirementsExtra
                    requirements.extra = PaymentRequirementsExtra()
                # Set facilitatorId in the fee info
                fee_quote.fee.facilitator_id = facilitator.facilitator_id
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
        """Create 402 Payment Required response.

        Args:
            requirements: List of payment requirements
            resource_info: Resource information
            payment_id: Payment ID for tracking (hex format with 0x prefix)
            nonce: Idempotency nonce
            valid_after: Valid from timestamp
            valid_before: Valid until timestamp

        Returns:
            PaymentRequired response
        """
        import time
        import uuid
        from x402.utils import generate_payment_id

        now = int(time.time())
        extensions = PaymentRequiredExtensions(
            paymentPermitContext=PaymentPermitContext(
                meta=PaymentPermitContextMeta(
                    kind=PAYMENT_ONLY,
                    paymentId=payment_id or generate_payment_id(),
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
        Verify payment signature and validity.

        Args:
            payload: Client payment payload
            requirements: Original payment requirements

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
        Execute payment settlement.

        Args:
            payload: Client payment payload
            requirements: Payment requirements

        Returns:
            SettleResponse with tx_hash
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
        """Validate payload matches requirements (anti-tampering)"""
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
