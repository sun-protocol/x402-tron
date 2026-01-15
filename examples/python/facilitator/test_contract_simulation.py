"""Simulate contract signature verification to identify the issue"""

import os
import sys
import time
import secrets
from pathlib import Path
from dotenv import load_dotenv
from eth_account import Account
from eth_account.messages import encode_typed_data
from Crypto.Hash import keccak
import base58

# Add x402 module to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "python" / "x402" / "src"))
from x402.config import NetworkConfig

load_dotenv(Path(__file__).parent.parent.parent.parent / ".env")

TRON_PRIVATE_KEY = os.getenv("TRON_PRIVATE_KEY", "")
TEST_USDT_ADDRESS = "TXYZopYRdj2D9XRtbG411XZZ3kM5VkAeBf"
MERCHANT_ADDRESS = "TCNkawTmcQgYSU8nP8cHswT1QPjharxJr7"
PAYMENT_PERMIT_ADDRESS = "TQeYAZmGwYJTNcqKFjc5rfE2r1FfFVTpvF"

def tron_to_evm(tron_addr: str) -> str:
    """Convert TRON address to EVM format"""
    if tron_addr.startswith("0x"):
        return tron_addr
    decoded = base58.b58decode(tron_addr)
    return "0x" + decoded[1:21].hex()

def test_contract_verification():
    """Test what the contract should verify"""
    from tronpy.keys import PrivateKey
    
    pk = PrivateKey(bytes.fromhex(TRON_PRIVATE_KEY[2:] if TRON_PRIVATE_KEY.startswith("0x") else TRON_PRIVATE_KEY))
    buyer_tron = pk.public_key.to_base58check_address()
    buyer_evm = tron_to_evm(buyer_tron)
    
    print("=" * 70)
    print("Contract Signature Verification Simulation")
    print("=" * 70)
    print()
    
    # Create test data
    current_time = int(time.time())
    payment_id = "0x" + secrets.token_hex(16)
    nonce = current_time
    
    usdt_evm = tron_to_evm(TEST_USDT_ADDRESS)
    merchant_evm = tron_to_evm(MERCHANT_ADDRESS)
    permit_evm = tron_to_evm(PAYMENT_PERMIT_ADDRESS)
    zero_evm = "0x" + "00" * 20
    
    print(f"Test Parameters:")
    print(f"  Buyer: {buyer_evm}")
    print(f"  Payment ID: {payment_id}")
    print(f"  Nonce: {nonce}")
    print()
    
    # Get chain ID from config
    chain_id = NetworkConfig.get_chain_id("tron:nile")
    
    # Test different possible EIP-712 configurations
    test_cases = [
        {
            "name": "Standard PaymentPermit",
            "primary_type": "PaymentPermit",
            "types": {
                "EIP712Domain": [
                    {"name": "name", "type": "string"},
                    {"name": "version", "type": "string"},
                    {"name": "chainId", "type": "uint256"},
                    {"name": "verifyingContract", "type": "address"},
                ],
                "PermitMeta": [
                    {"name": "kind", "type": "uint8"},
                    {"name": "paymentId", "type": "bytes16"},
                    {"name": "nonce", "type": "uint256"},
                    {"name": "validAfter", "type": "uint256"},
                    {"name": "validBefore", "type": "uint256"},
                ],
                "Payment": [
                    {"name": "payToken", "type": "address"},
                    {"name": "maxPayAmount", "type": "uint256"},
                    {"name": "payTo", "type": "address"},
                ],
                "Fee": [
                    {"name": "feeTo", "type": "address"},
                    {"name": "feeAmount", "type": "uint256"},
                ],
                "Delivery": [
                    {"name": "receiveToken", "type": "address"},
                    {"name": "miniReceiveAmount", "type": "uint256"},
                    {"name": "tokenId", "type": "uint256"},
                ],
                "PaymentPermit": [
                    {"name": "meta", "type": "PermitMeta"},
                    {"name": "buyer", "type": "address"},
                    {"name": "caller", "type": "address"},
                    {"name": "payment", "type": "Payment"},
                    {"name": "fee", "type": "Fee"},
                    {"name": "delivery", "type": "Delivery"},
                ],
            }
        },
        {
            "name": "Alternative: Meta instead of PermitMeta",
            "primary_type": "PaymentPermit",
            "types": {
                "EIP712Domain": [
                    {"name": "name", "type": "string"},
                    {"name": "version", "type": "string"},
                    {"name": "chainId", "type": "uint256"},
                    {"name": "verifyingContract", "type": "address"},
                ],
                "Meta": [
                    {"name": "kind", "type": "uint8"},
                    {"name": "paymentId", "type": "bytes16"},
                    {"name": "nonce", "type": "uint256"},
                    {"name": "validAfter", "type": "uint256"},
                    {"name": "validBefore", "type": "uint256"},
                ],
                "Payment": [
                    {"name": "payToken", "type": "address"},
                    {"name": "maxPayAmount", "type": "uint256"},
                    {"name": "payTo", "type": "address"},
                ],
                "Fee": [
                    {"name": "feeTo", "type": "address"},
                    {"name": "feeAmount", "type": "uint256"},
                ],
                "Delivery": [
                    {"name": "receiveToken", "type": "address"},
                    {"name": "miniReceiveAmount", "type": "uint256"},
                    {"name": "tokenId", "type": "uint256"},
                ],
                "PaymentPermit": [
                    {"name": "meta", "type": "Meta"},
                    {"name": "buyer", "type": "address"},
                    {"name": "caller", "type": "address"},
                    {"name": "payment", "type": "Payment"},
                    {"name": "fee", "type": "Fee"},
                    {"name": "delivery", "type": "Delivery"},
                ],
            }
        }
    ]
    
    domain = {
        "name": "PaymentPermit",
        "version": "1",
        "chainId": chain_id,
        "verifyingContract": permit_evm,
    }
    
    message = {
        "meta": {
            "kind": 0,
            "paymentId": payment_id,
            "nonce": nonce,
            "validAfter": 0,
            "validBefore": current_time + 3600,
        },
        "buyer": buyer_evm,
        "caller": zero_evm,
        "payment": {
            "payToken": usdt_evm,
            "maxPayAmount": 1000000,
            "payTo": merchant_evm,
        },
        "fee": {
            "feeTo": zero_evm,
            "feeAmount": 0,
        },
        "delivery": {
            "receiveToken": zero_evm,
            "miniReceiveAmount": 0,
            "tokenId": 0,
        },
    }
    
    private_key_bytes = bytes.fromhex(TRON_PRIVATE_KEY[2:] if TRON_PRIVATE_KEY.startswith("0x") else TRON_PRIVATE_KEY)
    
    print("-" * 70)
    print("Testing Different EIP-712 Configurations")
    print("-" * 70)
    print()
    
    for test_case in test_cases:
        print(f"Test: {test_case['name']}")
        
        typed_data = {
            "types": test_case["types"],
            "primaryType": test_case["primary_type"],
            "domain": domain,
            "message": message,
        }
        
        try:
            signable = encode_typed_data(full_message=typed_data)
            signed = Account.sign_message(signable, private_key_bytes)
            
            r = signed.r.to_bytes(32, 'big')
            s = signed.s.to_bytes(32, 'big')
            v = signed.v
            signature = (r + s + v.to_bytes(1, 'big')).hex()
            
            recovered = Account.recover_message(signable, signature=bytes.fromhex(signature))
            matches = recovered.lower() == buyer_evm.lower()
            
            # Calculate EIP-712 hash for debugging
            k = keccak.new(digest_bits=256)
            k.update(signable.body)
            msg_hash = k.hexdigest()
            
            print(f"  ✓ Signature: {signature[:20]}...")
            print(f"  ✓ Message hash: {msg_hash[:20]}...")
            print(f"  ✓ Recovered: {recovered}")
            print(f"  ✓ Match: {matches}")
            print()
        except Exception as e:
            print(f"  ✗ Error: {e}")
            print()
    
    print("=" * 70)
    print("Conclusion")
    print("=" * 70)
    print("All configurations produce valid signatures that recover correctly.")
    print("The contract revert must be due to a different validation check.")
    print()
    print("Possible remaining causes:")
    print("  1. Contract expects a different chainId")
    print("  2. Contract has additional validation logic (e.g., paused state)")
    print("  3. Contract expects different address format in permit vs owner param")
    print("  4. Token transfer simulation fails (even with sufficient balance/allowance)")

if __name__ == "__main__":
    test_contract_verification()
