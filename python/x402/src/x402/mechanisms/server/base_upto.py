"""
BaseUptoServerMechanism - Base class for "upto" payment scheme server mechanisms.

Extracts common logic from EVM and TRON implementations.
"""

import logging
from abc import abstractmethod
from typing import Any

from x402.mechanisms.server.base import ServerMechanism
from x402.tokens import TokenRegistry
from x402.types import PaymentRequirements, PaymentRequirementsExtra


class BaseUptoServerMechanism(ServerMechanism):
    """Base class for upto payment scheme server mechanisms.
    
    Subclasses only need to implement network prefix and address format validation.
    """

    def __init__(self) -> None:
        self._logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def _get_network_prefix(self) -> str:
        """Get network prefix, implemented by subclasses (e.g., 'eip155:' or 'tron:')"""
        pass

    @abstractmethod
    def _validate_address_format(self, address: str) -> bool:
        """Validate address format, implemented by subclasses"""
        pass

    def scheme(self) -> str:
        return "exact"

    async def parse_price(self, price: str, network: str) -> dict[str, Any]:
        """Parse price string to asset amount.
        
        Args:
            price: Price string (e.g., "100 USDC")
            network: Network identifier
            
        Returns:
            Dict containing amount, asset, decimals, etc.
        """
        self._logger.debug(f"Parsing price: {price} on network {network}")
        return TokenRegistry.parse_price(price, network)

    async def enhance_payment_requirements(
        self,
        requirements: PaymentRequirements,
        kind: str,
    ) -> PaymentRequirements:
        """Enhance payment requirements with token metadata"""
        if requirements.extra is None:
            requirements.extra = PaymentRequirementsExtra()

        token = TokenRegistry.find_by_address(requirements.network, requirements.asset)
        if token:
            requirements.extra.name = token.name
            requirements.extra.version = token.version

        return requirements

    def validate_payment_requirements(self, requirements: PaymentRequirements) -> bool:
        """Validate payment requirements"""
        prefix = self._get_network_prefix()

        if not requirements.network.startswith(prefix):
            self._logger.warning(f"Invalid network prefix: {requirements.network}")
            return False

        if not self._validate_address_format(requirements.asset):
            self._logger.warning(f"Invalid asset address format: {requirements.asset}")
            return False

        if not self._validate_address_format(requirements.pay_to):
            self._logger.warning(f"Invalid payTo address format: {requirements.pay_to}")
            return False

        try:
            amount = int(requirements.amount)
            if amount <= 0:
                self._logger.warning(f"Invalid amount: {amount}")
                return False
        except ValueError:
            self._logger.warning(f"Amount is not a valid integer: {requirements.amount}")
            return False

        return True
