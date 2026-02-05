"""
X402Facilitator - Core payment processor for x402 protocol
"""

from typing import Any, Protocol

from x402_tron.types import (
    FeeQuoteResponse,
    PaymentPayload,
    PaymentRequirements,
    SettleResponse,
    SupportedFee,
    SupportedKind,
    SupportedResponse,
    VerifyResponse,
)


class FacilitatorMechanism(Protocol):
    """Facilitator mechanism interface"""

    def scheme(self) -> str:
        """Get the payment scheme name"""
        ...

    async def fee_quote(
        self,
        accept: PaymentRequirements,
        context: dict[str, Any] | None = None,
    ) -> FeeQuoteResponse:
        """Calculate fee quote"""
        ...

    async def verify(
        self,
        payload: PaymentPayload,
        requirements: PaymentRequirements,
    ) -> VerifyResponse:
        """Verify payment signature"""
        ...

    async def settle(
        self,
        payload: PaymentPayload,
        requirements: PaymentRequirements,
    ) -> SettleResponse:
        """Execute payment settlement"""
        ...


class X402Facilitator:
    """
    Core payment processor for x402 protocol.

    Manages payment mechanisms and coordinates verification/settlement.
    """

    def __init__(self, fee_to: str | None = None, pricing: str = "flat") -> None:
        self._mechanisms: dict[str, dict[str, FacilitatorMechanism]] = {}
        self._fee_to = fee_to
        self._pricing = pricing

    def register(
        self,
        networks: list[str],
        mechanism: FacilitatorMechanism,
    ) -> "X402Facilitator":
        """
        Register a payment mechanism for multiple networks.

        Args:
            networks: List of network identifiers
            mechanism: Facilitator mechanism instance

        Returns:
            self for method chaining
        """
        scheme = mechanism.scheme()
        for network in networks:
            if network not in self._mechanisms:
                self._mechanisms[network] = {}
            self._mechanisms[network][scheme] = mechanism
        return self

    def supported(self) -> SupportedResponse:
        """
        Return supported network/scheme combinations.

        Returns:
            SupportedResponse with all supported capabilities including fee info
        """
        kinds: list[SupportedKind] = []
        for network, schemes in self._mechanisms.items():
            for scheme in schemes:
                kinds.append(
                    SupportedKind(
                        x402Version=2,
                        scheme=scheme,
                        network=network,
                    )
                )
        
        # Create fee configuration if fee_to is set
        fee = None
        if self._fee_to:
            fee = SupportedFee(
                fee_to=self._fee_to,
                pricing=self._pricing
            )
        
        return SupportedResponse(kinds=kinds, fee=fee)

    async def fee_quote(
        self,
        accept: PaymentRequirements,
        context: dict[str, Any] | None = None,
    ) -> FeeQuoteResponse:
        """
        Calculate fee quote for payment requirements.

        Args:
            accept: Payment requirements
            context: Optional payment context

        Returns:
            FeeQuoteResponse with fee information
        """
        mechanism = self._find_mechanism(accept.network, accept.scheme)
        if mechanism is None:
            raise ValueError(f"No mechanism for network={accept.network}, scheme={accept.scheme}")
        return await mechanism.fee_quote(accept, context)

    async def verify(
        self,
        payload: PaymentPayload,
        requirements: PaymentRequirements,
    ) -> VerifyResponse:
        """
        Verify payment signature and validity.

        Args:
            payload: Payment payload from client
            requirements: Payment requirements

        Returns:
            VerifyResponse
        """
        mechanism = self._find_mechanism(requirements.network, requirements.scheme)
        if mechanism is None:
            return VerifyResponse(
                isValid=False,
                invalidReason=(
                    f"unsupported_network_scheme: {requirements.network}/{requirements.scheme}"
                ),
            )
        return await mechanism.verify(payload, requirements)

    async def settle(
        self,
        payload: PaymentPayload,
        requirements: PaymentRequirements,
    ) -> SettleResponse:
        """
        Execute payment settlement.

        Args:
            payload: Payment payload from client
            requirements: Payment requirements

        Returns:
            SettleResponse with tx_hash
        """
        mechanism = self._find_mechanism(requirements.network, requirements.scheme)
        if mechanism is None:
            return SettleResponse(
                success=False,
                errorReason=(
                    f"unsupported_network_scheme: {requirements.network}/{requirements.scheme}"
                ),
            )
        return await mechanism.settle(payload, requirements)

    def _find_mechanism(self, network: str, scheme: str) -> FacilitatorMechanism | None:
        """Find mechanism for network and scheme"""
        network_mechanisms = self._mechanisms.get(network)
        if network_mechanisms is None:
            return None
        return network_mechanisms.get(scheme)
