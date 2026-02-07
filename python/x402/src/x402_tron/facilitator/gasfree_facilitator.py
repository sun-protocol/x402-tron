"""
GasFreeFacilitator - Specialized facilitator for GasFree payments
"""

from typing import List

from x402_tron.facilitator.x402_facilitator import X402Facilitator
from x402_tron.mechanisms.facilitator.gasfree import GasFreeFacilitatorMechanism
from x402_tron.signers.facilitator.tron_signer import TronFacilitatorSigner


class GasFreeFacilitator(X402Facilitator):
    """
    Specialized facilitator for GasFree payments.

    Pre-registered with GasFreeFacilitatorMechanism for easier initialization.
    """

    def __init__(self, networks: list[str], signer: TronFacilitatorSigner) -> None:
        super().__init__()
        self.register(networks, GasFreeFacilitatorMechanism(signer))
