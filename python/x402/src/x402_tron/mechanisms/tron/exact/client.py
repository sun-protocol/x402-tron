"""
ExactTronClientMechanism - exact client mechanism for TRON.
"""

from typing import TYPE_CHECKING

from x402_tron.mechanisms._exact_base.base import ExactBaseClientMechanism
from x402_tron.mechanisms.tron.exact.adapter import TronChainAdapter

if TYPE_CHECKING:
    from x402_tron.signers.client import ClientSigner


class ExactTronClientMechanism(ExactBaseClientMechanism):
    """TransferWithAuthorization client mechanism for TRON."""

    def __init__(self, signer: "ClientSigner") -> None:
        super().__init__(signer, TronChainAdapter())
