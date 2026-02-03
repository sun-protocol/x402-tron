import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
import httpx
import logging

from x402.clients import X402Client, X402HttpClient
from x402.mechanisms.client import UptoTronClientMechanism
from x402.signers.client import TronClientSigner

# Enable detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

load_dotenv(Path(__file__).parent.parent.parent.parent / ".env")

TRON_PRIVATE_KEY = os.getenv("TRON_PRIVATE_KEY", "")
# Hardcoded network configuration
TRON_NETWORK = "tron:nile"
# Hardcoded server configuration
RESOURCE_SERVER_URL = "http://localhost:8000"
ENDPOINT_PATH = "/protected"
RESOURCE_URL = RESOURCE_SERVER_URL + ENDPOINT_PATH

if not TRON_PRIVATE_KEY:
    print("\n❌ Error: TRON_PRIVATE_KEY not set in .env file")
    print("\nPlease add your TRON private key to .env file\n")
    exit(1)

async def main():
    # 设置客户端
    # 传入 network 以便自动处理授权，使用 nile 网络
    network = TRON_NETWORK.split(":")[-1]  # Extract network name (e.g., "nile")
    print(f"Initializing X402 client...")
    print(f"  Network: {TRON_NETWORK}")
    print(f"  Resource: {RESOURCE_URL}")
    
    signer = TronClientSigner.from_private_key(TRON_PRIVATE_KEY, network=network)
    print(f"  Client Address: {signer.get_address()}")
    
    x402_client = X402Client().register("tron:*", UptoTronClientMechanism(signer))
    
    async with httpx.AsyncClient(timeout=60.0) as http_client:
        client = X402HttpClient(http_client, x402_client)
        
        print(f"\nRequesting: {RESOURCE_URL}")
        try:
            # 发起请求（自动处理 402 支付）
            response = await client.get(RESOURCE_URL)
            print(f"\n✅ Success!")
            print(f"Status: {response.status_code}")
            print(f"Content-Type: {response.headers.get('content-type')}")
            print(f"Content-Length: {len(response.content)} bytes")
            
            # Parse payment response if present
            payment_response = response.headers.get('payment-response')
            if payment_response:
                from x402.encoding import decode_payment_payload
                from x402.types import SettleResponse
                settle_response = decode_payment_payload(payment_response, SettleResponse)
                print(f"\n📋 Payment Response:")
                print(f"  Success: {settle_response.success}")
                print(f"  Network: {settle_response.network}")
                print(f"  Transaction: {settle_response.transaction}")
                if settle_response.error_reason:
                    print(f"  Error: {settle_response.error_reason}")
            
            # Handle response based on content type
            content_type = response.headers.get('content-type', '')
            if 'application/json' in content_type:
                print(f"\nResponse: {response.json()}")
            elif 'image/' in content_type:
                print(f"\n🖼️  Received image file")
            else:
                print(f"\nResponse (first 200 chars): {response.text[:200]}")
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
