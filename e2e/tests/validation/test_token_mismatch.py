"""
E2E Tests: Token Mismatch

Tests for token validation edge cases.
"""

import pytest

from x402.types import FeeInfo, PaymentRequirements, PaymentRequirementsExtra

pytestmark = pytest.mark.e2e


class TestTokenMismatch:
    """Token mismatch tests with Facilitator service"""

    @pytest.mark.asyncio
    async def test_wrong_token_rejected(
        self,
        server_service,
        tron_client_mechanism,
        generate_permit_context,
    ):
        """Test wrong token is rejected by Server"""
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

        # Create requirements with WTRX instead of USDT
        wtrx_requirements = PaymentRequirements(
            scheme=req_data["scheme"],
            network=req_data["network"],
            amount=req_data["amount"],
            asset="T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuWwb",  # WTRX
            payTo=req_data["payTo"],
            extra=extra,
        )

        context = generate_permit_context()

        # Create payload with WTRX
        payload = await tron_client_mechanism.create_payment_payload(
            wtrx_requirements,
            f"{server_service.base_url}/protected",
            extensions=context,
        )

        # Try to access protected resource with wrong token
        import json
        payment_header = json.dumps(payload.model_dump(by_alias=True))
        status, response = await server_service.get_protected_resource(
            "/protected",
            payment_header=payment_header,
        )

        assert status == 402
        assert "error" in response or "accepts" in response
