"""
Client mechanism base interface
"""

from abc import ABC, abstractmethod
from typing import Any

from x402_tron.types import PaymentPayload, PaymentRequirements


class ClientMechanism(ABC):
    """
    Abstract base class for client payment mechanisms.

    Responsible for creating payment payloads for specific chains/schemes.
    """

    @abstractmethod
    def scheme(self) -> str:
        """Get the payment scheme name"""
        pass

    @abstractmethod
    async def create_payment_payload(
        self,
        requirements: PaymentRequirements,
        resource: str,
        extensions: dict[str, Any] | None = None,
    ) -> PaymentPayload:
        """
        Create a payment payload for the given requirements.

        Args:
            requirements: Payment requirements from server
            resource: Resource URL
            extensions: Optional extensions (e.g., paymentPermitContext)

        Returns:
            PaymentPayload with signature
        """
        pass
