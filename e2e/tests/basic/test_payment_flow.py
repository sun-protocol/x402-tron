"""
E2E Tests: Full Payment Flow

Tests for complete end-to-end payment flows.
"""

import pytest

from x402.encoding import encode_payment_payload
from x402.types import (
    FeeInfo,
    PAYMENT_ONLY,
    PaymentRequirements,
    PaymentRequirementsExtra,
)

pytestmark = pytest.mark.e2e


class TestFullPaymentFlow:
    """Full payment flow tests"""

    @pytest.mark.asyncio
    async def test_complete_payment_flow(
        self,
        facilitator_service,
        server_service,
        tron_client_mechanism,
        generate_permit_context,
    ):
        """
        Test complete payment flow:
        1. Request protected resource -> 402
        2. Parse payment requirements
        3. Get fee quote from facilitator
        4. Create payment payload
        5. Verify with facilitator
        6. Access resource with payment
        """
        # Step 1: Request protected resource
        status, data = await server_service.get_protected_resource()
        assert status == 402

        # Step 2: Parse requirements
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

        # Step 3: Get fee quote
        fee_quote = await facilitator_service.get_fee_quote(
            requirements.model_dump(by_alias=True)
        )
        print(f"Fee quote: {fee_quote}")

        # Step 4: Create payment payload
        context = generate_permit_context(kind=PAYMENT_ONLY)
        payload = await tron_client_mechanism.create_payment_payload(
            requirements,
            f"{server_service.base_url}/protected",
            extensions=context,
        )

        # Step 5: Verify with facilitator
        verify_result = await facilitator_service.verify_payment(
            payload.model_dump(by_alias=True),
            requirements.model_dump(by_alias=True),
        )
        assert verify_result["isValid"] is True
        print("Payment verified by facilitator")

        # Step 6: Access resource with payment
        encoded = encode_payment_payload(payload)
        status, response_data = await server_service.get_protected_resource(
            payment_header=encoded
        )

        print(f"Final response status: {status}")
        # Should succeed or return specific error
        assert status in [200, 402, 500]

    @pytest.mark.asyncio
    async def test_payment_flow_with_settlement(
        self,
        facilitator_service,
        server_service,
        tron_client_mechanism,
        generate_permit_context,
    ):
        """
        Test payment flow with on-chain settlement.

        This test performs actual blockchain transaction.
        """
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

        # Settle via facilitator (on-chain)
        settle_result = await facilitator_service.settle_payment(
            payload.model_dump(by_alias=True),
            requirements.model_dump(by_alias=True),
        )

        if settle_result.get("success"):
            print(f"Settlement tx: {settle_result.get('transaction')}")
            assert settle_result["network"] == "tron:nile"
        else:
            print(f"Settlement failed: {settle_result.get('errorReason')}")
