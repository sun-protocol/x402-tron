"""
X402 Network Configuration
Centralized configuration for contract addresses and network settings
"""

from typing import Dict


class NetworkConfig:
    """Network configuration for contract addresses and chain IDs"""

    # Default networks
    TRON_MAINNET = "tron:mainnet"
    TRON_SHASTA = "tron:shasta"
    TRON_NILE = "tron:nile"

    # TRON Chain IDs
    CHAIN_IDS: Dict[str, int] = {
        "tron:mainnet": 728126428,  # 0x2b6653dc
        "tron:shasta": 2494104990,  # 0x94a9059e
        "tron:nile": 3448148188,  # 0xcd8690dc
    }

    # PaymentPermit contract addresses
    PAYMENT_PERMIT_ADDRESSES: Dict[str, str] = {
        "tron:mainnet": "THnW1E6yQWgx9P3QtSqWw2t3qGwH35jARg",
        "tron:shasta": "TVjYLoXatyMkemxzeB9M8ZE3uGttR9QZJ8",
        "tron:nile": "TLEwy4d8oh5gTGUiwWcNUBSzppRNfaWymc",
    }

    @classmethod
    def get_chain_id(cls, network: str) -> int:
        """Get chain ID for network

        Args:
            network: Network identifier (e.g., "tron:nile", "tron:mainnet")

        Returns:
            Chain ID as integer

        Raises:
            ValueError: If network is not supported
        """
        chain_id = cls.CHAIN_IDS.get(network)
        if chain_id is None:
            raise ValueError(f"Unsupported network: {network}")
        return chain_id

    @classmethod
    def get_payment_permit_address(cls, network: str) -> str:
        """Get PaymentPermit contract address for network

        Args:
            network: Network identifier (e.g., "tron:nile", "tron:mainnet")

        Returns:
            Contract address in Base58 format
        """
        return cls.PAYMENT_PERMIT_ADDRESSES.get(network, "T0000000000000000000000000000000")
