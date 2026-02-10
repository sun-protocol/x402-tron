"""
x402 Mechanisms - Payment mechanisms for different chains

Structure:
    _base/                  - ABC interfaces (ClientMechanism, FacilitatorMechanism, ServerMechanism)
    _exact_permit_base/     - Shared base classes for "exact_permit" scheme
    _exact_base/            - Shared base classes for "exact" scheme
    evm/                    - EVM chain implementations
        exact_permit/       - exact_permit scheme (client, facilitator, server)
        exact/              - exact scheme (adapter, client, facilitator, server)
    tron/                   - TRON chain implementations
        exact_permit/       - exact_permit scheme (client, facilitator, server)
        exact/              - exact scheme (adapter, client, facilitator, server)
"""

from x402_tron.mechanisms import evm, tron
from x402_tron.mechanisms._base import ClientMechanism, FacilitatorMechanism, ServerMechanism
from x402_tron.mechanisms._exact_permit_base import (
    BaseExactPermitClientMechanism,
    BaseExactPermitFacilitatorMechanism,
    BaseExactPermitServerMechanism,
)
from x402_tron.mechanisms._exact_base import (
    ChainAdapter,
    ExactBaseClientMechanism,
    ExactBaseFacilitatorMechanism,
    ExactBaseServerMechanism,
)
from x402_tron.mechanisms.evm import (
    ExactPermitEvmClientMechanism,
    ExactPermitEvmFacilitatorMechanism,
    ExactPermitEvmServerMechanism,
    ExactEvmClientMechanism,
    ExactEvmFacilitatorMechanism,
    ExactEvmServerMechanism,
)
from x402_tron.mechanisms.tron import (
    ExactPermitTronClientMechanism,
    ExactPermitTronFacilitatorMechanism,
    ExactPermitTronServerMechanism,
    ExactTronClientMechanism,
    ExactTronFacilitatorMechanism,
    ExactTronServerMechanism,
)

__all__ = [
    # Base interfaces
    "ClientMechanism",
    "FacilitatorMechanism",
    "ServerMechanism",
    # ExactPermit base
    "BaseExactPermitClientMechanism",
    "BaseExactPermitFacilitatorMechanism",
    "BaseExactPermitServerMechanism",
    # Exact base
    "ChainAdapter",
    "ExactBaseClientMechanism",
    "ExactBaseFacilitatorMechanism",
    "ExactBaseServerMechanism",
    # EVM
    "ExactPermitEvmClientMechanism",
    "ExactPermitEvmFacilitatorMechanism",
    "ExactPermitEvmServerMechanism",
    "ExactEvmClientMechanism",
    "ExactEvmFacilitatorMechanism",
    "ExactEvmServerMechanism",
    # TRON
    "ExactPermitTronClientMechanism",
    "ExactPermitTronFacilitatorMechanism",
    "ExactPermitTronServerMechanism",
    "ExactTronClientMechanism",
    "ExactTronFacilitatorMechanism",
    "ExactTronServerMechanism",
    # Subpackages
    "evm",
    "tron",
]
