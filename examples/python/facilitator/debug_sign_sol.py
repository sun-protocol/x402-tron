from eth_account import Account
from eth_account.messages import encode_typed_data
import time

def sign_permit_transfer_from(
    private_key: str,
    verifying_contract: str,
    chain_id: int,
    permit_details: dict,
    transfer_amount: int
):
    """
    Signs a permitTransferFrom message for the PaymentPermit contract.
    """
    account = Account.from_key(private_key)
    print(f"Account Address: {account.address}")
    
    # EIP-712 Domain
    domain = {
        "name": "PaymentPermit",
        "chainId": chain_id,
        "verifyingContract": verifying_contract
    }
    
    # EIP-712 Types
    # Note: Types must be in alphabetical order for nested structs if they are referenced
    # However, encode_typed_data handles the dependency graph. 
    # The order in the primary type is what matters most for the signature.
    types = {
        "PermitMeta": [
            {"name": "kind", "type": "uint8"},
            {"name": "paymentId", "type": "bytes16"},
            {"name": "nonce", "type": "uint256"},
            {"name": "validAfter", "type": "uint256"},
            {"name": "validBefore", "type": "uint256"}
        ],
        "Payment": [
            {"name": "payToken", "type": "address"},
            {"name": "maxPayAmount", "type": "uint256"},
            {"name": "payTo", "type": "address"}
        ],
        "Fee": [
            {"name": "feeTo", "type": "address"},
            {"name": "feeAmount", "type": "uint256"}
        ],
        "Delivery": [
            {"name": "receiveToken", "type": "address"},
            {"name": "miniReceiveAmount", "type": "uint256"},
            {"name": "tokenId", "type": "uint256"}
        ],
        "PaymentPermitDetails": [
            {"name": "meta", "type": "PermitMeta"},
            {"name": "buyer", "type": "address"},
            {"name": "caller", "type": "address"},
            {"name": "payment", "type": "Payment"},
            {"name": "fee", "type": "Fee"},
            {"name": "delivery", "type": "Delivery"}
        ],
        "EIP712Domain": [
            {"name": "name", "type": "string"},
            {"name": "chainId", "type": "uint256"},
            {"name": "verifyingContract", "type": "address"}
        ]
    }
    
    # Message data
    message = permit_details
    
    # Encode and sign
    typed_data = {
        "types": types,
        "domain": domain,
        "primaryType": "PaymentPermitDetails",
        "message": message
    }
    signable_data = encode_typed_data(full_message=typed_data)
    
    print(f"typed_data: {typed_data}")
    print(f"signable_data: {signable_data}")
    print(f"private_key: {private_key}")
    
    signed_message = account.sign_message(signable_data)
    
    return signed_message.signature.hex()

# Example Usage
if __name__ == "__main__":
    # Mock data matching Solidity test
    PRIVATE_KEY = "0x00000000000000000000000000000000000000000000000000000000000a11ce"
    # Data from Solidity Logs:
    CONTRACT_ADDRESS = "0x5615dEB798BB3E4dFa0139dFa1b3D433Cc23b72f"
    CHAIN_ID = 3448148188
    
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
    
    signature = sign_permit_transfer_from(
        PRIVATE_KEY,
        CONTRACT_ADDRESS,
        CHAIN_ID,
        permit,
        transfer_details["amount"]
    )
    
    print(f"Signature: {signature}")
