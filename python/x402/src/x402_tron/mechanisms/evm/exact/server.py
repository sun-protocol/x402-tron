"""
ExactEvmServerMechanism - exact server mechanism for EVM.
"""

from x402_tron.mechanisms._exact_base.base import ExactBaseServerMechanism
from x402_tron.mechanisms.evm.exact.adapter import EvmChainAdapter


class ExactEvmServerMechanism(ExactBaseServerMechanism):
    """TransferWithAuthorization server mechanism for EVM."""

    def __init__(self) -> None:
        super().__init__(EvmChainAdapter())
