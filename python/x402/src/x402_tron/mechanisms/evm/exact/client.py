"""
ExactEvmClientMechanism - exact client mechanism for EVM.
"""

from typing import TYPE_CHECKING

from x402_tron.mechanisms._exact_base.base import ExactBaseClientMechanism
from x402_tron.mechanisms.evm.exact.adapter import EvmChainAdapter

if TYPE_CHECKING:
    from x402_tron.signers.client import ClientSigner


class ExactEvmClientMechanism(ExactBaseClientMechanism):
    """TransferWithAuthorization client mechanism for EVM."""

    def __init__(self, signer: "ClientSigner") -> None:
        super().__init__(signer, EvmChainAdapter())
