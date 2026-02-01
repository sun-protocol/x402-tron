"""
E2E Tests: Delivery Modes

Tests for PAYMENT_ONLY and PAYMENT_AND_DELIVERY modes.
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


class TestDeliveryModes:
    """Delivery mode tests"""

    @pytest.mark.asyncio
    async def test_payment_only_mode(
        self,
        facilitator_service,
        server_service,
        tron_client_mechanism,
        generate_permit_context,
    ):
        """Test PAYMENT_ONLY mode"""
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

        context = generate_permit_context(kind=PAYMENT_ONLY)
        payload = await tron_client_mechanism.create_payment_payload(
            requirements,
            f"{server_service.base_url}/protected",
            extensions=context,
        )

        result = await facilitator_service.verify_payment(
            payload.model_dump(by_alias=True),
            requirements.model_dump(by_alias=True),
        )

        assert result["isValid"] is True

    @pytest.mark.asyncio
    async def test_payment_and_delivery_mode(
        self,
        facilitator_service,
        server_service,
        tron_client_mechanism,
        generate_permit_context,
    ):
        """Test PAYMENT_AND_DELIVERY mode"""
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

        # TRON zero address for caller
        tron_zero_address = "T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuWwb"

        context = generate_permit_context(
            kind=PAYMENT_AND_DELIVERY,
            caller=tron_zero_address,
            receive_token=req_data["asset"],
            mini_receive_amount="500000",
        )

        payload = await tron_client_mechanism.create_payment_payload(
            requirements,
            f"{server_service.base_url}/protected",
            extensions=context,
        )

        result = await facilitator_service.verify_payment(
            payload.model_dump(by_alias=True),
            requirements.model_dump(by_alias=True),
        )

        assert result["isValid"] is True
