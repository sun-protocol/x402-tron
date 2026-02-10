"""
ExactTronServerMechanism - exact server mechanism for TRON.
"""

from x402_tron.mechanisms._exact_base.base import ExactBaseServerMechanism
from x402_tron.mechanisms.tron.exact.adapter import TronChainAdapter


class ExactTronServerMechanism(ExactBaseServerMechanism):
    """TransferWithAuthorization server mechanism for TRON."""

    def __init__(self) -> None:
        super().__init__(TronChainAdapter())
