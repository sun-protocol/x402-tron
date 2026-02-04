"""
Client signer base interface
"""

from abc import ABC, abstractmethod
from typing import Any


class ClientSigner(ABC):
    """
    Abstract base class for client signers.

    Responsible for signing messages and managing token allowances.
    """

    @abstractmethod
    def get_address(self) -> str:
        """Get the signer's account address"""
        pass

    @abstractmethod
    async def sign_message(self, message: bytes) -> str:
        """
        Sign a raw message.

        Args:
            message: Raw message bytes

        Returns:
            Signature string (hex)
        """
        pass

    @abstractmethod
    async def sign_typed_data(
        self,
        domain: dict[str, Any],
        types: dict[str, Any],
        message: dict[str, Any],
    ) -> str:
        """
        Sign typed data (EIP-712).

        Args:
            domain: EIP-712 domain
            types: Type definitions
            message: Message to sign

        Returns:
            Signature string (hex)
        """
        pass

    @abstractmethod
    async def check_allowance(
        self,
        token: str,
        amount: int,
        network: str,
    ) -> int:
        """
        Check token allowance.

        Args:
            token: Token contract address
            amount: Required amount
            network: Network identifier

        Returns:
            Current allowance
        """
        pass

    @abstractmethod
    async def ensure_allowance(
        self,
        token: str,
        amount: int,
        network: str,
        mode: str = "auto",
    ) -> bool:
        """
        Ensure sufficient token allowance.

        Args:
            token: Token contract address
            amount: Required amount
            network: Network identifier
            mode: Approval mode (auto, interactive, skip)

        Returns:
            True if allowance is sufficient
        """
        pass
