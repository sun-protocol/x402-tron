"""
NativeExactTronServerMechanism - native_exact server mechanism for TRON.

Handles price parsing, requirement validation, and signature verification
for the native_exact scheme.
"""

import logging
from typing import Any

from x402_tron.address import TronAddressConverter
from x402_tron.mechanisms.native_exact.types import SCHEME_NATIVE_EXACT
from x402_tron.mechanisms.server.base import ServerMechanism
from x402_tron.tokens import TokenRegistry
from x402_tron.types import PaymentRequirements, PaymentRequirementsExtra

logger = logging.getLogger(__name__)


class NativeExactTronServerMechanism(ServerMechanism):
    """TransferWithAuthorization server mechanism for TRON."""

    def __init__(self) -> None:
        self._converter = TronAddressConverter()

    def scheme(self) -> str:
        return SCHEME_NATIVE_EXACT

    async def parse_price(self, price: str, network: str) -> dict[str, Any]:
        return TokenRegistry.parse_price(price, network)

    async def enhance_payment_requirements(
        self,
        requirements: PaymentRequirements,
        kind: str,
    ) -> PaymentRequirements:
        if requirements.extra is None:
            requirements.extra = PaymentRequirementsExtra()

        token = TokenRegistry.find_by_address(requirements.network, requirements.asset)
        if token:
            requirements.extra.name = token.name
            requirements.extra.version = token.version

        return requirements

    def validate_payment_requirements(self, requirements: PaymentRequirements) -> bool:
        if not requirements.network.startswith("tron:"):
            return False
        if not requirements.asset.startswith("T"):
            return False
        if not requirements.pay_to.startswith("T"):
            return False
        try:
            if int(requirements.amount) <= 0:
                return False
        except ValueError:
            return False
        return True

    async def verify_signature(
        self,
        permit: Any,
        signature: str,
        network: str,
    ) -> bool:
        """Server-side signature check for native_exact.

        For native_exact, there is no PaymentPermit (permit is None).
        Full signature verification is delegated to the facilitator,
        which has access to the complete payload including extensions.
        The server simply passes through here.
        """
        if permit is None:
            return True
        return True
