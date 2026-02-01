"""
E2E Tests: Nonce Replay Attack

Tests for nonce replay attack prevention.
"""

import time

import pytest

from x402.types import (
    FeeInfo,
    PAYMENT_ONLY,
    PaymentRequirements,
    PaymentRequirementsExtra,
)
from x402.utils import generate_payment_id

pytestmark = pytest.mark.e2e


class TestNonceReplay:
    """Nonce replay tests"""

    @pytest.mark.asyncio
    async def test_same_nonce_different_payment_id_verify_passes(
        self,
        server_service,
        tron_client_mechanism,
        generate_permit_context,
    ):
        """Test same nonce with different paymentId passes verification"""
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

        fixed_nonce = str(int(time.time()))

        # First payment
        context1 = generate_permit_context(nonce=fixed_nonce)
        payload1 = await tron_client_mechanism.create_payment_payload(
            requirements,
            f"{server_service.base_url}/protected",
            extensions=context1,
        )

        import json
        payment_header1 = json.dumps(payload1.model_dump(by_alias=True))
        status1, response1 = await server_service.get_protected_resource(
            "/protected",
            payment_header=payment_header1,
        )
        assert status1 == 200

        # Second payment with same nonce but different paymentId
        context2 = generate_permit_context(nonce=fixed_nonce)
        payload2 = await tron_client_mechanism.create_payment_payload(
            requirements,
            f"{server_service.base_url}/protected",
            extensions=context2,
        )

        payment_header2 = json.dumps(payload2.model_dump(by_alias=True))
        status2, response2 = await server_service.get_protected_resource(
            "/protected",
            payment_header=payment_header2,
        )

        # Verification passes - nonce replay is enforced on-chain
        assert status2 == 200

    @pytest.mark.asyncio
    async def test_large_nonce_value(
        self,
        server_service,
        tron_client_mechanism,
        generate_permit_context,
    ):
        """Test large nonce value is accepted"""
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

        large_nonce = "999999999999999999"
        context = generate_permit_context(nonce=large_nonce)

        payload = await tron_client_mechanism.create_payment_payload(
            requirements,
            f"{server_service.base_url}/protected",
            extensions=context,
        )

        import json
        payment_header = json.dumps(payload.model_dump(by_alias=True))
        status, response = await server_service.get_protected_resource(
            "/protected",
            payment_header=payment_header,
        )

        assert status == 200

    @pytest.mark.asyncio
    async def test_nonce_replay_rejected_on_chain(
        self,
        facilitator_service,
        server_service,
        tron_client_mechanism,
    ):
        """
        Test nonce replay is rejected on-chain.

        This test performs two on-chain settlements with the same nonce.
        The second should fail.
        """
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

        fixed_nonce = str(int(time.time()))
        current_time_ms = int(time.time()) * 1000

        # First payment
        context1 = {
            "paymentPermitContext": {
                "meta": {
                    "kind": PAYMENT_ONLY,
                    "paymentId": generate_payment_id(),
                    "nonce": fixed_nonce,
                    "validAfter": 0,
                    "validBefore": current_time_ms + 3600000,
                },
                "delivery": {
                    "receiveToken": "T" + "0" * 33,
                    "miniReceiveAmount": "0",
                    "tokenId": "0",
                },
            }
        }

        payload1 = await tron_client_mechanism.create_payment_payload(
            requirements,
            f"{server_service.base_url}/protected",
            extensions=context1,
        )

        # First settlement
        result1 = await facilitator_service.settle_payment(
            payload1.model_dump(by_alias=True),
            requirements.model_dump(by_alias=True),
        )

        assert result1.get("success") is True, f"First settlement failed: {result1.get('errorReason')}"
        print(f"First settlement tx: {result1.get('transaction')}")

        # Second payment with same nonce
        context2 = {
            "paymentPermitContext": {
                "meta": {
                    "kind": PAYMENT_ONLY,
                    "paymentId": generate_payment_id(),
                    "nonce": fixed_nonce,  # Same nonce
                    "validAfter": 0,
                    "validBefore": current_time_ms + 3600000,
                },
                "delivery": {
                    "receiveToken": "T" + "0" * 33,
                    "miniReceiveAmount": "0",
                    "tokenId": "0",
                },
            }
        }

        payload2 = await tron_client_mechanism.create_payment_payload(
            requirements,
            f"{server_service.base_url}/protected",
            extensions=context2,
        )

        # Second settlement should fail (nonce already used)
        result2 = await facilitator_service.settle_payment(
            payload2.model_dump(by_alias=True),
            requirements.model_dump(by_alias=True),
        )

        # Nonce replay should be rejected on-chain
        assert result2.get("success") is False, "Nonce replay should be rejected by contract"
        print(f"Second settlement failed as expected: {result2.get('errorReason')}")
