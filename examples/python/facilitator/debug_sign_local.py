"""
Debug script for testing TRON local signing using TronClientSigner.sign_typed_data
Based on debug_sign_sol.py but adapted for TRON network.
Aligns with create_payment_payload implementation logic.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path to import x402
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "python" / "x402" / "src"))

from x402.abi import get_payment_permit_eip712_types
from x402.signers.client.tron_signer import TronClientSigner


async def sign_permit_transfer_from(
    private_key: str,
    verifying_contract: str,
    chain_id: int,
    permit_details: dict,
    transfer_amount: int
):
    """
    Signs a permitTransferFrom message for the PaymentPermit contract using TRON signer.
    
    This implementation aligns with create_payment_payload logic in tron_upto.py:
    1. Uses same EIP-712 types structure (get_payment_permit_eip712_types)
    2. Uses "PaymentPermitDetails" as primaryType (matching contract's PermitHash.sol)
    3. Domain without version field (name, chainId, verifyingContract only)
    4. Calls signer.sign_typed_data with same parameters
    
    Args:
        private_key: Private key for signing
        verifying_contract: Contract address (EVM format 0x...)
        chain_id: Chain ID
        permit_details: Permit message data
        transfer_amount: Transfer amount (kept for compatibility with debug_sol_sign.py)
    """
    # Create TRON signer (same as create_payment_payload uses self._signer)
    signer = TronClientSigner.from_private_key(private_key, network="nile")
    
    print(f"Signer address: {signer.get_address()}")
    
    # EIP-712 Domain (same as create_payment_payload)
    # Note: Contract EIP712Domain only has (name, chainId, verifyingContract) - NO version!
    domain = {
        "name": "PaymentPermit",
        "chainId": chain_id,
        "verifyingContract": verifying_contract
    }
    
    # EIP-712 Types - use the same method as tron_upto.py to avoid duplication
    types = get_payment_permit_eip712_types()
    
    # Message data
    message = permit_details
    
    print(f"\nDomain: {domain}")
    print(f"Primary Type: PaymentPermit")
    print(f"Message: {message}")
    
    # Sign using TronClientSigner (same call as create_payment_payload)
    signature = await signer.sign_typed_data(
        domain=domain,
        types=types,
        message=message
    )
    
    return signature


async def main():
    """Main function to test TRON signing
    
    Uses same test data as debug_sol_sign.py but with EVM format addresses
    to match create_payment_payload behavior (which converts TRON to EVM format)
    """
    # Mock data matching Solidity test (same as debug_sol_sign.py)
    PRIVATE_KEY = "0x00000000000000000000000000000000000000000000000000000000000a11ce"
    
    # Data from Solidity Logs (same as debug_sol_sign.py)
    # Using EVM format addresses (0x...) as create_payment_payload converts TRON to EVM
    CONTRACT_ADDRESS = "0x5615dEB798BB3E4dFa0139dFa1b3D433Cc23b72f"
    CHAIN_ID = 3448148188
    
    # Permit details (same structure as debug_sol_sign.py)
    # Addresses in EVM format to match create_payment_payload conversion
    permit = {
        "meta": {
            "kind": 0,
            "paymentId": b"\x00" * 16,
            "nonce": 0,
            "validAfter": 0,
            "validBefore": 1000
        },
        "buyer": "0xe05fcC23807536bEe418f142D19fa0d21BB0cfF7",
        "caller": "0x0000000000000000000000000000000000000000",
        "payment": {
            "payToken": "0x2e234DAe75C793f67A35089C9d99245E1C58470b",
            "maxPayAmount": 100 * 10**18,
            "payTo": "0x0000000000000000000000000000000000000B0b"
        },
        "fee": {
            "feeTo": "0x0000000000000000000000000000000000000FEE",
            "feeAmount": 1 * 10**18
        },
        "delivery": {
            "receiveToken": "0x0000000000000000000000000000000000000000",
            "miniReceiveAmount": 0,
            "tokenId": 0
        }
    }
    
    transfer_details = {
        "amount": 90 * 10**6
    }
    
    print("=" * 80)
    print("TRON Local Signing Debug (aligned with create_payment_payload)")
    print("=" * 80)
    
    signature = await sign_permit_transfer_from(
        PRIVATE_KEY,
        CONTRACT_ADDRESS,
        CHAIN_ID,
        permit,
        transfer_details["amount"]
    )
    
    print(f"Signature: {signature}")
    print(f"Signature length: {len(signature)} chars ({len(signature)//2} bytes)")


if __name__ == "__main__":
    asyncio.run(main())
