import pytest
from unittest.mock import MagicMock, patch
from x402_tron.utils.gasfree import GasFreeTronAddressCalculator
from x402_tron.config import NetworkConfig


def test_gasfree_address_calculation():
    # Test vector for GasFree address calculation
    user_address = "TDn5i9p6U5vD5S6C6D6E6F6G6H6I6J6K6L"  # Mock address

    # We mock keccak to avoid dependency issues in test environment
    # In a real environment, eth-hash or pysha3 would be used
    with patch("x402_tron.utils.gasfree.GasFreeTronAddressCalculator.keccak256") as mock_keccak:
        # Mock result for keccak(create2_input)
        # For a predictable test, we just return a fixed bytes object
        # that results in a known Base58 address
        # 20 bytes for address
        mock_keccak.return_value = bytes.fromhex(
            "00" * 12 + "1234567890abcdef1234567890abcdef12345678"
        )

        # Test inputs from Nile
        controller = "THQGuFzL87ZqhxkgqYEryRAd7gqFqL5rdc"
        beacon = "TLtCGmaxH3PbuaF6kbybwteZcHptEdgQGC"
        creation_code = NetworkConfig.get_gasfree_creation_code("tron:nile")

        gasfree_address = GasFreeTronAddressCalculator.calculate_gasfree_address(
            user_address, controller, beacon, creation_code
        )

        # The Base58 of 41 + 1234567890abcdef1234567890abcdef12345678 + checksum
        # We just verify it's a valid TRON address format
        assert gasfree_address.startswith("T")
        assert len(gasfree_address) >= 33


def test_salt_calculation():
    user_address = "TQr1nSWDLWgmJ3tkbFZANnaFcB5ci7Hvxa"
    # EVM of TQr1... is 0xa613160e1d13f96b27d49826d7f9d846b4020000 (just an example)
    salt = GasFreeTronAddressCalculator.calculate_salt(user_address)
    assert salt.startswith("0x")
    assert len(salt) == 66  # 0x + 64 hex chars
