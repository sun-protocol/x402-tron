"""
ExactTronFacilitatorMechanism - exact facilitator mechanism for TRON.
"""

from typing import TYPE_CHECKING

from x402_tron.mechanisms._exact_base.base import ExactBaseFacilitatorMechanism
from x402_tron.mechanisms.tron.exact.adapter import TronChainAdapter

if TYPE_CHECKING:
    from x402_tron.signers.facilitator import FacilitatorSigner


class ExactTronFacilitatorMechanism(ExactBaseFacilitatorMechanism):
    """TransferWithAuthorization facilitator mechanism for TRON."""

    def __init__(
        self,
        signer: "FacilitatorSigner",
        allowed_tokens: set[str] | None = None,
    ) -> None:
        super().__init__(signer, TronChainAdapter(), allowed_tokens)
