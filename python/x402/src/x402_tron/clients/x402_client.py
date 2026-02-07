"""
X402Client - Core payment client for x402 protocol
"""

import logging
from typing import TYPE_CHECKING, Any, Callable, Protocol

from x402_tron.types import (
    PaymentPayload,
    PaymentRequirements,
)

if TYPE_CHECKING:
    from x402_tron.clients.token_selection import TokenSelectionStrategy

logger = logging.getLogger(__name__)


class ClientMechanism(Protocol):
    """Client mechanism interface"""

    def scheme(self) -> str:
        """Get the payment scheme name"""
        ...

    async def create_payment_payload(
        self,
        requirements: PaymentRequirements,
        resource: str,
        extensions: dict[str, Any] | None = None,
    ) -> PaymentPayload:
        """Create payment payload"""
        ...


PaymentRequirementsSelector = Callable[[list[PaymentRequirements]], PaymentRequirements]


class PaymentRequirementsFilter:
    """Filter options for selecting payment requirements"""

    def __init__(
        self,
        scheme: str | None = None,
        network: str | None = None,
    ):
        self.scheme = scheme
        self.network = network


class MechanismEntry:
    """Registered mechanism entry"""

    def __init__(self, pattern: str, mechanism: ClientMechanism, priority: int):
        self.pattern = pattern
        self.mechanism = mechanism
        self.priority = priority


class X402Client:
    """
    Core payment client for x402 protocol.

    Manages payment mechanism registry and coordinates payment flow.
    """

    def __init__(
        self,
        token_strategy: "TokenSelectionStrategy | None" = None,
    ) -> None:
        """
        Initialize X402Client.

        Args:
            token_strategy: Strategy for selecting which token to pay with.
                            If None, uses first available option.
        """
        self._mechanisms: list[MechanismEntry] = []
        self._token_strategy = token_strategy

    def register(self, network_pattern: str, mechanism: ClientMechanism) -> "X402Client":
        """
        Register a payment mechanism for a network pattern.

        Args:
            network_pattern: Network pattern (e.g., "eip155:*", "tron:shasta")
            mechanism: Payment mechanism instance

        Returns:
            self for method chaining
        """
        priority = self._calculate_priority(network_pattern)
        logger.info(
            f"Registering mechanism for pattern '{network_pattern}' with priority {priority}"
        )
        self._mechanisms.append(MechanismEntry(network_pattern, mechanism, priority))
        self._mechanisms.sort(key=lambda e: e.priority, reverse=True)
        return self

    async def select_payment_requirements(
        self,
        accepts: list[PaymentRequirements],
        filters: PaymentRequirementsFilter | None = None,
    ) -> PaymentRequirements:
        """
        Select payment requirements from available options.

        Applies filters, then delegates to the token selection strategy
        if one is configured (and a signer is available). Otherwise
        falls back to picking the first candidate.

        Args:
            accepts: Available payment requirements
            filters: Optional filters

        Returns:
            Selected payment requirements

        Raises:
            ValueError: No supported payment requirements found
        """
        logger.info(f"Selecting payment requirements from {len(accepts)} options")
        logger.debug(f"Available payment requirements: {[r.model_dump() for r in accepts]}")

        candidates = list(accepts)

        if filters:
            if hasattr(filters, "scheme") and filters.scheme:
                candidates = [r for r in candidates if r.scheme == filters.scheme]
                logger.debug(f"After scheme filter: {len(candidates)} candidates")
            if hasattr(filters, "network") and filters.network:
                candidates = [r for r in candidates if r.network == filters.network]
                logger.debug(f"After network filter: {len(candidates)} candidates")

        candidates = [r for r in candidates if self._find_mechanism(r.network) is not None]
        logger.debug(f"After mechanism filter: {len(candidates)} candidates")

        if not candidates:
            logger.error("No supported payment requirements found")
            raise ValueError("No supported payment requirements found")

        if self._token_strategy:
            selected = await self._token_strategy.select(candidates)
        else:
            selected = candidates[0]

        logger.info(
            "Selected payment requirement: network=%s, scheme=%s, amount=%s",
            selected.network,
            selected.scheme,
            selected.amount,
        )
        return selected

    async def create_payment_payload(
        self,
        requirements: PaymentRequirements,
        resource: str,
        extensions: dict[str, Any] | None = None,
    ) -> PaymentPayload:
        """
        Create payment payload for given requirements.

        Args:
            requirements: Selected payment requirements
            resource: Resource URL
            extensions: Optional extensions

        Returns:
            Payment payload
        """
        logger.info(
            f"Creating payment payload for network={requirements.network}, resource={resource}"
        )
        mechanism = self._find_mechanism(requirements.network)
        if mechanism is None:
            logger.error(f"No mechanism registered for network: {requirements.network}")
            raise ValueError(f"No mechanism registered for network: {requirements.network}")

        logger.debug(f"Using mechanism: {mechanism.__class__.__name__}")
        payload = await mechanism.create_payment_payload(requirements, resource, extensions)
        logger.info("Payment payload created successfully")
        return payload

    async def handle_payment(
        self,
        accepts: list[PaymentRequirements],
        resource: str,
        extensions: dict[str, Any] | None = None,
        selector: PaymentRequirementsSelector | None = None,
    ) -> PaymentPayload:
        """
        Handle payment required response.

        Args:
            accepts: Available payment requirements
            resource: Resource URL
            extensions: Optional extensions
            selector: Optional custom selector

        Returns:
            Payment payload
        """
        if selector:
            requirements = selector(accepts)
        else:
            requirements = await self.select_payment_requirements(accepts)

        return await self.create_payment_payload(requirements, resource, extensions)

    def _find_mechanism(self, network: str) -> ClientMechanism | None:
        """Find mechanism for network"""
        for entry in self._mechanisms:
            if self._match_pattern(entry.pattern, network):
                return entry.mechanism
        return None

    def _match_pattern(self, pattern: str, network: str) -> bool:
        """Match network against pattern"""
        if pattern == network:
            return True
        if pattern.endswith(":*"):
            prefix = pattern[:-1]
            return network.startswith(prefix)
        return False

    def _calculate_priority(self, pattern: str) -> int:
        """Calculate priority for pattern (more specific = higher priority)"""
        if pattern.endswith(":*"):
            return 1
        return 10
