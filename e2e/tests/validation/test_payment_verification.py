"""
E2E Tests: Payment Verification

Tests for payment verification via Facilitator API.
"""

import pytest

from x402.types import (
    FeeInfo,
    PAYMENT_ONLY,
    PaymentRequirements,
    PaymentRequirementsExtra,
)

pytestmark = pytest.mark.e2e


class TestPaymentVerification:
    """Payment verification tests via Facilitator service"""

    @pytest.mark.asyncio
    async def test_verify_payment_via_server(
        self,
        server_service,
        tron_client_mechanism,
        generate_permit_context,
    ):
        """Test payment verification via Server"""
        # Get requirements from server
        req_data = await server_service.get_payment_requirements()
        assert req_data is not None

        # Build PaymentRequirements
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

        # Create payment payload
        context = generate_permit_context(kind=PAYMENT_ONLY)
        payload = await tron_client_mechanism.create_payment_payload(
            requirements,
            f"{server_service.base_url}/protected",
            extensions=context,
        )

        # Access protected resource with valid payment
        import json
        payment_header = json.dumps(payload.model_dump(by_alias=True))
        status, response = await server_service.get_protected_resource(
            "/protected",
            payment_header=payment_header,
        )

        assert status == 200


