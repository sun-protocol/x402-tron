"""
X402 Network Configuration
Centralized configuration for contract addresses and network settings
"""

from typing import Dict

from x402_tron.exceptions import UnsupportedNetworkError


class NetworkConfig:
    """Network configuration for contract addresses and chain IDs"""

    # Default networks
    TRON_MAINNET = "tron:mainnet"
    TRON_SHASTA = "tron:shasta"
    TRON_NILE = "tron:nile"

    # EVM Networks
    EVM_MAINNET = "eip155:1"
    EVM_SEPOLIA = "eip155:11155111"
    EVM_BSC = "eip155:56"
    EVM_BSC_TESTNET = "eip155:97"

    # TRON Chain IDs
    CHAIN_IDS: Dict[str, int] = {
        "tron:mainnet": 728126428,  # 0x2b6653dc
        "tron:shasta": 2494104990,  # 0x94a9059e
        "tron:nile": 3448148188,  # 0xcd8690dc
        "eip155:1": 1,
        "eip155:11155111": 11155111,
        "eip155:56": 56,
        "eip155:97": 97,
    }

    # PaymentPermit contract addresses
    PAYMENT_PERMIT_ADDRESSES: Dict[str, str] = {
        "tron:mainnet": "TT8rEWbCoNX7vpEUauxb7rWJsTgs8vDLAn",
        "tron:shasta": "TR2XninQ3jsvRRLGTifFyUHTBysffooUjt",
        "tron:nile": "TFxDcGvS7zfQrS1YzcCMp673ta2NHHzsiH",
        # Add generic EVM PaymentPermit address if known, or leave as placeholder
        # "eip155:1": "0x...",
    }

    @classmethod
    def get_chain_id(cls, network: str) -> int:
        """Get chain ID for network

        Args:
            network: Network identifier (e.g., "tron:nile", "tron:mainnet")

        Returns:
            Chain ID as integer

        Raises:
            UnsupportedNetworkError: If network is not supported
        """
        chain_id = cls.CHAIN_IDS.get(network)
        if chain_id is None:
            raise UnsupportedNetworkError(f"Unsupported network: {network}")
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
