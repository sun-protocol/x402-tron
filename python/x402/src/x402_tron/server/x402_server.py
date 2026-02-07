"""
X402Server - Core payment server for x402 protocol
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from x402_tron.config import NetworkConfig
from x402_tron.types import (
    PAYMENT_ONLY,
    PaymentPayload,
    PaymentPermitContext,
    PaymentPermitContextMeta,
    PaymentRequired,
    PaymentRequiredExtensions,
    PaymentRequirements,
    SettleResponse,
    VerifyResponse,
)

if TYPE_CHECKING:
    from x402_tron.facilitator.facilitator_client import FacilitatorClient


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
        from x402_tron.mechanisms.server import ExactTronServerMechanism

        tron_mechanism = ExactTronServerMechanism()
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
            # Fetch and cache facilitator address for use in create_payment_required_response
            await facilitator.fetch_facilitator_address()

            # Get fee quote from facilitator (fee is required)
            fee_quote = await facilitator.fee_quote(requirements)
            if fee_quote:
                if requirements.extra is None:
                    from x402_tron.types import PaymentRequirementsExtra

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
        caller: str | None = None,
    ) -> PaymentRequired:
        """Create 402 Payment Required response.

        Args:
            requirements: List of payment requirements
            resource_info: Resource information
            payment_id: Payment ID for tracking (hex format with 0x prefix)
            nonce: Idempotency nonce
            valid_after: Valid from timestamp
            valid_before: Valid until timestamp
            caller: Caller address (facilitator address that will execute the permit)

        Returns:
            PaymentRequired response
        """
        import time
        import uuid

        from x402_tron.utils import generate_payment_id

        now = int(time.time())

        # Get caller (facilitator address) from first facilitator if not provided
        effective_caller = caller
        if effective_caller is None and self._facilitators:
            effective_caller = self._facilitators[0].facilitator_address
            # Log for debugging
            import logging

            logger = logging.getLogger(__name__)
            logger.info(f"[CALLER] Setting caller from facilitator: {effective_caller}")

        extensions = PaymentRequiredExtensions(
            paymentPermitContext=PaymentPermitContext(
                meta=PaymentPermitContextMeta(
                    kind=PAYMENT_ONLY,
                    paymentId=payment_id or generate_payment_id(),
                    nonce=nonce or str(uuid.uuid4().int),
                    validAfter=valid_after or now,
                    validBefore=valid_before or (now + 3600),
                ),
                caller=effective_caller,
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

        # Server-side signature verification to prevent incorrect signatures from frontend
        mechanism = self._mechanisms.get(requirements.network)
        if mechanism is not None:
            permit = payload.payload.payment_permit
            signature = payload.payload.signature

            is_valid = await mechanism.verify_signature(permit, signature, requirements.network)
            if not is_valid:
                return VerifyResponse(isValid=False, invalidReason="invalid_signature_server")

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
        if int(permit.payment.pay_amount) < int(requirements.amount):
            return False

        return True

    def _find_facilitator_for_payload(self, payload: PaymentPayload) -> "FacilitatorClient | None":
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
