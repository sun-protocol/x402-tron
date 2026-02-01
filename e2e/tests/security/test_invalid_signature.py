"""
E2E Tests: Invalid Signature

Tests for signature validation edge cases.
"""

import pytest

from x402.types import FeeInfo, PaymentRequirements, PaymentRequirementsExtra

pytestmark = pytest.mark.e2e


class TestInvalidSignature:
    """Invalid signature tests with Facilitator service"""

    @pytest.mark.asyncio
    async def test_tampered_signature_rejected(
        self,
        server_service,
        tron_client_mechanism,
        generate_permit_context,
    ):
        """Test tampered signature is rejected by Server"""
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

        context = generate_permit_context()
        payload = await tron_client_mechanism.create_payment_payload(
            requirements,
            f"{server_service.base_url}/protected",
            extensions=context,
        )

        # Tamper with signature
        original_sig = payload.payload.signature
        tampered_sig = original_sig[:-4] + "0000"
        payload.payload.signature = tampered_sig

        # Try to access protected resource with tampered signature
        import json
        payment_header = json.dumps(payload.model_dump(by_alias=True))
        status, response = await server_service.get_protected_resource(
            "/protected",
            payment_header=payment_header,
        )

        assert status == 402
        assert "error" in response or "accepts" in response

    @pytest.mark.asyncio
    async def test_wrong_buyer_signature(
        self,
        server_service,
        generate_permit_context,
    ):
        """Test signature from different buyer with Server"""
        from x402.mechanisms.client import UptoTronClientMechanism
        from x402.signers.client import TronClientSigner

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

        # Use different private key
        different_key = (
            "1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
        )
        different_signer = TronClientSigner.from_private_key(
            different_key, network="nile"
        )
        different_mechanism = UptoTronClientMechanism(different_signer)

        context = generate_permit_context()
        payload = await different_mechanism.create_payment_payload(
            requirements,
            f"{server_service.base_url}/protected",
            extensions=context,
        )

        # Try to access protected resource - signature is valid but from different buyer
        import json
        payment_header = json.dumps(payload.model_dump(by_alias=True))
        status, response = await server_service.get_protected_resource(
            "/protected",
            payment_header=payment_header,
        )

        # Signature itself is valid (different buyer is allowed)
        assert status == 200
