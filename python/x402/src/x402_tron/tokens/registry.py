"""
Token registry - Centralized management of token configurations for all networks
"""

from dataclasses import dataclass
from typing import Any

from x402_tron.exceptions import UnknownTokenError


@dataclass
class TokenInfo:
    """Token information"""

    address: str
    decimals: int
    name: str
    symbol: str
    version: str = "1"


class TokenRegistry:
    """Token registry"""

    _tokens: dict[str, dict[str, TokenInfo]] = {
        # TRON Networks
        "tron:mainnet": {
            "USDT": TokenInfo(
                address="TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
                decimals=6,
                name="Tether USD",
                symbol="USDT",
            ),
        },
        "tron:shasta": {
            "USDT": TokenInfo(
                address="TG3XXyExBkPp9nzdajDZsozEu4BkaSJozs",
                decimals=6,
                name="Tether USD",
                symbol="USDT",
            ),
        },
        "tron:nile": {
            "USDT": TokenInfo(
                address="TXYZopYRdj2D9XRtbG411XZZ3kM5VkAeBf",
                decimals=6,
                name="Tether USD",
                symbol="USDT",
            ),
        },
    }

    @classmethod
    def get_token(cls, network: str, symbol: str) -> TokenInfo:
        """Get token information for specified network and symbol

        Raises:
            UnknownTokenError: If token does not exist
        """
        tokens = cls._tokens.get(network, {})
        token = tokens.get(symbol.upper())
        if token is None:
            raise UnknownTokenError(f"Unknown token {symbol} on network {network}")
        return token

    @classmethod
    def find_by_address(cls, network: str, address: str) -> TokenInfo | None:
        """Find token information by address"""
        tokens = cls._tokens.get(network, {})
        for info in tokens.values():
            if info.address.lower() == address.lower():
                return info
        return None

    @classmethod
    def get_network_tokens(cls, network: str) -> dict[str, TokenInfo]:
        """Get all tokens for specified network"""
        return cls._tokens.get(network, {})

    @classmethod
    def parse_price(cls, price: str, network: str) -> dict[str, Any]:
        """Parse price string into asset amount

        Args:
            price: Price string (e.g. "100 USDC")
            network: Network identifier

        Returns:
            Dictionary containing amount, asset, decimals, etc.
        """
        parts = price.strip().split()
        if len(parts) != 2:
            raise ValueError(f"Invalid price format: {price}")

        amount_str, symbol = parts
        amount = float(amount_str)

        token = cls.get_token(network, symbol)
        amount_smallest = int(amount * (10**token.decimals))

        return {
            "amount": amount_smallest,
            "asset": token.address,
            "decimals": token.decimals,
            "symbol": token.symbol,
            "name": token.name,
            "version": token.version,
        }
