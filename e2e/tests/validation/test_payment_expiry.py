"""
E2E Tests: Payment Expiry

Tests for payment time window validation.
"""

import time

import pytest

from x402.types import FeeInfo, PaymentRequirements, PaymentRequirementsExtra

pytestmark = pytest.mark.e2e


class TestPaymentExpiry:
    """Payment expiry tests with Facilitator service"""

    @pytest.mark.asyncio
    async def test_expired_payment_rejected(
        self,
        server_service,
        tron_client_mechanism,
        generate_permit_context,
    ):
        """Test expired payment is rejected by Server"""
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

        requirements = PaymentRequirements(
            scheme=req_data["scheme"],
            network=req_data["network"],
            amount=req_data["amount"],
            asset=req_data["asset"],
            payTo=req_data["payTo"],
            extra=extra,
        )

        # Create expired payment (validBefore in the past)
        context = generate_permit_context(
            valid_before_offset_ms=-3600000,  # 1 hour ago
        )

        payload = await tron_client_mechanism.create_payment_payload(
            requirements,
            f"{server_service.base_url}/protected",
            extensions=context,
        )

        # Try to access protected resource with expired payment
        from x402.encoding import encode_payment_payload
        payment_header = encode_payment_payload(payload)
        status, response = await server_service.get_protected_resource(
            "/protected",
            payment_header=payment_header,
        )

        # Expired payment should be rejected with 400 Bad Request
        assert status == 400, "Expired payment should be rejected"
        assert "error" in response
        assert "verification failed" in response["error"].lower()

    @pytest.mark.asyncio
    async def test_not_yet_valid_payment_rejected(
        self,
        server_service,
        tron_client_mechanism,
        generate_permit_context,
    ):
        """Test not-yet-valid payment is rejected by Server"""
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

        requirements = PaymentRequirements(
            scheme=req_data["scheme"],
            network=req_data["network"],
            amount=req_data["amount"],
            asset=req_data["asset"],
            payTo=req_data["payTo"],
            extra=extra,
        )

        # Create payment that's not yet valid (validAfter in the future)
        future_time_ms = int(time.time()) * 1000 + 3600000  # 1 hour from now
        context = generate_permit_context(valid_after=future_time_ms)

        payload = await tron_client_mechanism.create_payment_payload(
            requirements,
            f"{server_service.base_url}/protected",
            extensions=context,
        )

        # Try to access protected resource with not-yet-valid payment
        from x402.encoding import encode_payment_payload
        payment_header = encode_payment_payload(payload)
        status, response = await server_service.get_protected_resource(
            "/protected",
            payment_header=payment_header,
        )

        # Not-yet-valid payment should be rejected with 400 Bad Request
        assert status == 400
        assert "error" in response
        assert "verification failed" in response["error"].lower()
