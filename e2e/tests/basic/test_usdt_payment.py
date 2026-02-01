"""
E2E Tests: USDT Payment

Tests for USDT token payment flow using X402Client SDK.
"""

import httpx
import pytest

from x402.clients import X402Client, X402HttpClient
from x402.encoding import decode_payment_payload
from x402.mechanisms.client import UptoTronClientMechanism
from x402.types import SettleResponse

pytestmark = pytest.mark.e2e


class TestUsdtPayment:
    """USDT payment tests using X402Client SDK"""

    @pytest.mark.asyncio
    async def test_usdt_payment_with_client_sdk(
        self,
        server_service,
        tron_client_signer,
    ):
        """Test USDT payment using X402Client SDK"""
        # Setup X402 client
        x402_client = X402Client().register(
            "tron:*", UptoTronClientMechanism(tron_client_signer)
        )

        async with httpx.AsyncClient(timeout=60.0) as http_client:
            client = X402HttpClient(http_client, x402_client)

            # Request protected resource (SDK handles 402 payment automatically)
            response = await client.get(f"{server_service.base_url}/protected")

            # Should succeed
            assert response.status_code == 200
            print(f"✅ USDT payment successful")
            print(f"Response content-type: {response.headers.get('content-type')}")
            
            # Parse and print payment-response data
            payment_response_header = response.headers.get("payment-response")
            if payment_response_header:
                try:
                    settle_response = decode_payment_payload(payment_response_header, SettleResponse)
                    print(f"\n📋 Payment Response:")
                    print(f"  Success: {settle_response.success}")
                    print(f"  Network: {settle_response.network}")
                    print(f"  Transaction: {settle_response.transaction}")
                    if settle_response.error_reason:
                        print(f"  Error: {settle_response.error_reason}")
                except Exception as e:
                    print(f"⚠️  Failed to parse payment-response: {e}")
