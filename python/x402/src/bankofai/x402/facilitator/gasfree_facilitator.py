"""
GasFreeFacilitator - Specialized facilitator for GasFree payments
"""

from typing import Any

from bankofai.x402.facilitator.x402_facilitator import X402Facilitator
from bankofai.x402.mechanisms.tron.gasfree.facilitator import GasFreeFacilitatorMechanism


class GasFreeFacilitator(X402Facilitator):
    """
    Specialized facilitator for GasFree payments.

    Pre-registered with GasFreeFacilitatorMechanism for easier initialization.
    """

    def __init__(
        self,
        networks: list[str],
        signer: Any,
        base_fee: dict[str, int] | None = None,
    ) -> None:
        super().__init__()
        # Default base fee if none provided
        fee_map = base_fee or {"USDT": 1_000_000, "USDD": 1_000_000_000_000_000_000}
        self.register(networks, GasFreeFacilitatorMechanism(signer, base_fee=fee_map))
