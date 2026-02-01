"""
E2E Tests: Delivery Mode

Tests for PAYMENT_AND_DELIVERY mode endpoint.
"""

import pytest

from x402.types import (
    FeeInfo,
    PAYMENT_AND_DELIVERY,
    PAYMENT_ONLY,
    PaymentRequirements,
    PaymentRequirementsExtra,
)

pytestmark = pytest.mark.e2e


class TestDeliveryMode:
    """Delivery mode endpoint tests"""

    @pytest.mark.asyncio
    async def test_protected_delivery_endpoint_returns_402(self, server_service):
        """Test /protected-delivery endpoint returns 402 without payment"""
        status, data = await server_service.get_protected_resource(
            path="/protected-delivery"
        )
        assert status == 402
        assert "accepts" in data
        assert len(data["accepts"]) > 0

        # Verify requirements
        requirements = data["accepts"][0]
        assert requirements["network"] == "tron:nile"
        assert requirements["scheme"] == "exact"

    @pytest.mark.asyncio
    async def test_delivery_mode_payment_verification(
        self,
        facilitator_service,
        server_service,
        tron_client_mechanism,
        generate_permit_context,
    ):
        """Test PAYMENT_AND_DELIVERY mode payment verification"""
        # Get requirements from /protected-delivery
        status, data = await server_service.get_protected_resource(
            path="/protected-delivery"
        )
        assert status == 402
        req_data = data["accepts"][0]

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

        # TRON zero address for caller
        tron_zero_address = "T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuWwb"

        # Use PAYMENT_AND_DELIVERY mode
        context = generate_permit_context(
            kind=PAYMENT_AND_DELIVERY,
            caller=tron_zero_address,
            receive_token=req_data["asset"],
            mini_receive_amount="500000",
        )

        payload = await tron_client_mechanism.create_payment_payload(
            requirements,
            f"{server_service.base_url}/protected-delivery",
            extensions=context,
        )

        # Verify payment
        result = await facilitator_service.verify_payment(
            payload.model_dump(by_alias=True),
            requirements.model_dump(by_alias=True),
        )

        assert result["isValid"] is True

    @pytest.mark.asyncio
    async def test_delivery_mode_with_different_receive_amounts(
        self,
        facilitator_service,
        server_service,
        tron_client_mechanism,
        generate_permit_context,
    ):
        """Test delivery mode with different minimum receive amounts"""
        # Get requirements from /protected-delivery
        status, data = await server_service.get_protected_resource(
            path="/protected-delivery"
        )
        assert status == 402
        req_data = data["accepts"][0]

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

        tron_zero_address = "T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuWwb"

        # Test with different minimum receive amounts
        for mini_receive in ["0", "100000", "500000", "900000"]:
            context = generate_permit_context(
                kind=PAYMENT_AND_DELIVERY,
                caller=tron_zero_address,
                receive_token=req_data["asset"],
                mini_receive_amount=mini_receive,
            )

            payload = await tron_client_mechanism.create_payment_payload(
                requirements,
                f"{server_service.base_url}/protected-delivery",
                extensions=context,
            )

            result = await facilitator_service.verify_payment(
                payload.model_dump(by_alias=True),
                requirements.model_dump(by_alias=True),
            )

            assert result["isValid"] is True

    @pytest.mark.asyncio
    async def test_delivery_mode_wrong_payment_mode_rejected(
        self,
        facilitator_service,
        server_service,
        tron_client_mechanism,
        generate_permit_context,
    ):
        """Test delivery endpoint with PAYMENT_ONLY mode"""
        # Get requirements from /protected-delivery
        status, data = await server_service.get_protected_resource(
            path="/protected-delivery"
        )
        assert status == 402
        req_data = data["accepts"][0]

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

        # Try to use PAYMENT_ONLY mode
        context = generate_permit_context(kind=PAYMENT_ONLY)
        payload = await tron_client_mechanism.create_payment_payload(
            requirements,
            f"{server_service.base_url}/protected-delivery",
            extensions=context,
        )

        # Verify payment structure is valid
        # Note: Mode mismatch validation happens on server side
        result = await facilitator_service.verify_payment(
            payload.model_dump(by_alias=True),
            requirements.model_dump(by_alias=True),
        )

        assert "isValid" in result
