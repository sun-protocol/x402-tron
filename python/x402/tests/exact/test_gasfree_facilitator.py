"""
Tests for GasFreeFacilitatorMechanism.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bankofai.x402.mechanisms.tron.gasfree.facilitator import GasFreeFacilitatorMechanism
from bankofai.x402.types import (
    Fee,
    Payment,
    PaymentPayload,
    PaymentPayloadData,
    PaymentPermit,
    PaymentRequirements,
    PermitMeta,
    ResourceInfo,
)


@pytest.fixture
def mock_facilitator_signer():
    signer = MagicMock()
    signer.get_address.return_value = "TFacilitatorAddr1234567890123456"
    signer.verify_typed_data = AsyncMock(return_value=True)
    signer.wait_for_transaction_receipt = AsyncMock(
        return_value={"status": "1", "transactionHash": "0xabc"}
    )
    return signer


@pytest.fixture
def gasfree_requirements():
    return PaymentRequirements(
        scheme="gasfree_exact",
        network="tron:nile",
        amount="1000000",
        asset="TXYZopYRdj2D9XRtbG411XZZ3kM5VkAeBf",
        payTo="TMerchantAddr12345678901234567890",
        maxTimeoutSeconds=3600,
    )


@pytest.fixture
def gasfree_payload(gasfree_requirements):
    permit = PaymentPermit(
        buyer="TBuyerAddr12345678901234567890",
        caller="TFacilitatorAddr1234567890123456",
        meta=PermitMeta(
            kind="PAYMENT_ONLY",
            paymentId="pay-123",
            nonce="1",
            validAfter=0,
            validBefore=2000000000,
        ),
        payment=Payment(
            payToken="TXYZopYRdj2D9XRtbG411XZZ3kM5VkAeBf",
            payAmount="1000000",
            payTo="TMerchantAddr12345678901234567890",
        ),
        fee=Fee(
            feeTo="TFacilitatorAddr1234567890123456",
            feeAmount="1000000",
        ),
    )
    return PaymentPayload(
        x402Version=2,
        resource=ResourceInfo(url="https://example.com", mimeType="application/json"),
        accepted=gasfree_requirements,
        payload=PaymentPayloadData(
            signature="0x" + "ab" * 65,
            merchantSignature=None,
            paymentPermit=permit,
        ),
        extensions={"gasfreeAddress": "TLCvf7MktLG7XkbJRyUwnvCeDnaEXYkcbC"},
    )


class TestGasFreeFacilitator:
    @pytest.mark.anyio
    async def test_verify_success(
        self, mock_facilitator_signer, gasfree_requirements, gasfree_payload
    ):
        # Configure mechanism with 1 USDT base fee
        mechanism = GasFreeFacilitatorMechanism(mock_facilitator_signer, base_fee={"USDT": 1000000})

        with patch("bankofai.x402.tokens.TokenRegistry.find_by_address") as mock_find:
            mock_find.return_value = MagicMock(symbol="USDT")
            result = await mechanism.verify(gasfree_payload, gasfree_requirements)

        assert result.is_valid is True
        mock_facilitator_signer.verify_typed_data.assert_called_once()

    @pytest.mark.anyio
    async def test_settle_success(
        self, mock_facilitator_signer, gasfree_requirements, gasfree_payload
    ):
        mechanism = GasFreeFacilitatorMechanism(mock_facilitator_signer, base_fee={"USDT": 1000000})

        with patch(
            "bankofai.x402.mechanisms.tron.gasfree.facilitator.GasFreeAPIClient"
        ) as mock_api:
            mock_api.return_value.submit = AsyncMock(return_value="0xhash123")
            with patch("bankofai.x402.tokens.TokenRegistry.find_by_address") as mock_find:
                mock_find.return_value = MagicMock(symbol="USDT")
                result = await mechanism.settle(gasfree_payload, gasfree_requirements)

        assert result.success is True
        assert result.transaction == "0xhash123"

    @pytest.mark.anyio
    async def test_verify_fail_bad_signature(
        self, mock_facilitator_signer, gasfree_requirements, gasfree_payload
    ):
        mock_facilitator_signer.verify_typed_data.return_value = False
        mechanism = GasFreeFacilitatorMechanism(mock_facilitator_signer, base_fee={"USDT": 1000000})

        with patch("bankofai.x402.tokens.TokenRegistry.find_by_address") as mock_find:
            mock_find.return_value = MagicMock(symbol="USDT")
            result = await mechanism.verify(gasfree_payload, gasfree_requirements)

        assert result.is_valid is False
        assert result.invalid_reason == "invalid_signature"
