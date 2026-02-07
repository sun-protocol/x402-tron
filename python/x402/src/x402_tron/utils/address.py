"""
Address utility functions for TRON and EVM address conversion
"""

import logging

import base58

logger = logging.getLogger(__name__)


def normalize_tron_address(tron_addr: str) -> str:
    """Normalize TRON address, converting invalid placeholders to valid zero address

    Args:
        tron_addr: TRON address in Base58 format

    Returns:
        Normalized TRON address
    """
    # Handle zero address placeholder (T0000... or similar)
    if tron_addr.startswith("T") and all(c in "0T" for c in tron_addr):
        # Return valid TRON zero address with correct checksum
        return "T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuWwb"
    return tron_addr


def tron_address_to_evm(tron_addr: str) -> str:
    """Convert TRON Base58Check address to EVM hex format (0x...)

    Args:
        tron_addr: TRON address in Base58 format or hex format

    Returns:
        EVM address in hex format (0x...)
    """
    # Normalize address first
    tron_addr = normalize_tron_address(tron_addr)

    # If already in EVM format, return as-is
    if tron_addr.startswith("0x"):
        return tron_addr

    # If it's a hex string (with or without 0x prefix), normalize to 0x format
    # Check if it looks like a hex address (40 or 42 chars of hex digits, possibly with
    # 0x or 41 prefix)
    hex_str = tron_addr
    if tron_addr.startswith("41"):
        # Remove TRON version prefix
        hex_str = tron_addr[2:]

    if len(hex_str) == 40 and all(c in "0123456789abcdefABCDEF" for c in hex_str):
        return "0x" + hex_str

    try:
        # Decode Base58Check (for TRON addresses like TLBaRhANhwgZyUk6Z1ynCn1Ld7BRH1jBjZ)
        decoded = base58.b58decode(tron_addr)
        # TRON address is 25 bytes: 1 byte version + 20 bytes address + 4 bytes checksum
        # Extract the 20-byte address (skip first byte, take next 20)
        address_bytes = decoded[1:21]
        # Convert to hex with 0x prefix
        return "0x" + address_bytes.hex()
    except Exception as e:
        logger.warning(f"Failed to convert TRON address {tron_addr}: {e}, using as-is")
        return tron_addr


def evm_address_to_tron(evm_addr: str) -> str:
    """Convert EVM hex address (0x...) to TRON Base58 format

    Args:
        evm_addr: EVM address in hex format (0x...)

    Returns:
        TRON address in Base58 format
    """
    if not evm_addr.startswith("0x"):
        return evm_addr

    try:
        # Remove 0x prefix
        addr_hex = evm_addr[2:]
        # Add TRON version prefix (0x41)
        full_hex = "41" + addr_hex
        # Convert to bytes
        full_bytes = bytes.fromhex(full_hex)

        # Calculate checksum
        import hashlib

        hash1 = hashlib.sha256(full_bytes).digest()
        hash2 = hashlib.sha256(hash1).digest()
        checksum = hash2[:4]

        # Combine and encode
        final_bytes = full_bytes + checksum
        return base58.b58encode(final_bytes).decode("ascii")
    except Exception as e:
        logger.warning(f"Failed to convert EVM address {evm_addr}: {e}, using as-is")
        return evm_addr
