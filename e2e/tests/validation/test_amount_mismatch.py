"""
E2E Tests: Amount Mismatch

Tests for amount validation edge cases.
"""

import pytest

from x402.types import FeeInfo, PaymentRequirements, PaymentRequirementsExtra

pytestmark = pytest.mark.e2e


class TestAmountMismatch:
    """Amount mismatch tests with Facilitator service"""

    @pytest.mark.asyncio
    async def test_insufficient_amount_rejected(
        self,
        server_service,
        tron_client_mechanism,
        generate_permit_context,
    ):
        """Test insufficient amount is rejected by Server"""
        # Get requirements from server
        req_data = await server_service.get_payment_requirements()
        assert req_data is not None

        extra = None
        if req_data.get("extra") and req_data["extra"].get("fee"):
            fee_data = req_data["extra"]["fee"]
            extra = PaymentRequirementsExtra(
                fee=FeeInfo(
                    feeTo=fee_data["feeTo"],
                    feeAmount=fee_data["feeAmount"],
                )
            )

        # Create requirements with insufficient amount
        # Server requires full amount (e.g., 1000000), but we only authorize half
        insufficient_amount = str(int(req_data["amount"]) // 2)
        low_requirements = PaymentRequirements(
            scheme=req_data["scheme"],
            network=req_data["network"],
            amount=insufficient_amount,  # Use lower amount to trigger mismatch
            asset=req_data["asset"],
            payTo=req_data["payTo"],
            extra=extra,
        )

        context = generate_permit_context()

        # Create payload with insufficient amount
        # This creates a permit with max_pay_amount < server's required amount
        payload = await tron_client_mechanism.create_payment_payload(
            low_requirements,
            f"{server_service.base_url}/protected",
            extensions=context,
        )

        # Try to access protected resource with insufficient payment
        # Server should reject due to amount mismatch
        from x402.encoding import encode_payment_payload
        payment_header = encode_payment_payload(payload)
        status, response = await server_service.get_protected_resource(
            "/protected",
            payment_header=payment_header,
        )

        # Should be rejected with 400 Bad Request (verification failure)
        assert status == 400
        assert "error" in response
        
        # Verify the error message indicates verification failure
        # Server should return "Verification failed: payload_mismatch"
        assert "verification failed" in response["error"].lower() and "payload_mismatch" in response["error"].lower()
