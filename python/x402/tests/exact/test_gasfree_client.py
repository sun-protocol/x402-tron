"""
Tests for ExactGasFreeClientMechanism.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bankofai.x402.abi import GASFREE_PRIMARY_TYPE
from bankofai.x402.mechanisms.tron.exact_gasfree.client import ExactGasFreeClientMechanism
from bankofai.x402.types import PaymentRequirements

USDT_ADDRESS = "TXYZopYRdj2D9XRtbG411XZZ3kM5VkAeBf"


@pytest.fixture
def mock_signer():
    signer = MagicMock()
    signer.get_address.return_value = "THKbWd2g5aS9tY59xk8hp5xMnbE8m3B3E"
    signer.sign_typed_data = AsyncMock(return_value="0x" + "ab" * 65)
    return signer


@pytest.fixture
def nile_requirements():
    return PaymentRequirements(
        scheme="exact_gasfree",
        network="tron:nile",
        amount="1000000",
        asset=USDT_ADDRESS,
        payTo="TMerchantAddr12345678901234567890",
        maxTimeoutSeconds=3600,
    )


@pytest.fixture
def mock_api_client():
    with patch("bankofai.x402.mechanisms.tron.exact_gasfree.client.GasFreeAPIClient") as mock:
        client_instance = mock.return_value
        client_instance.get_address_info = AsyncMock(
            return_value={
                "accountAddress": "THKbWd2g5aS9tY59xk8hp5xMnbE8m3B3E",
                "gasFreeAddress": "TLCvf7MktLG7XkbJRyUwnvCeDnaEXYkcbC",
                "active": True,
                "nonce": 1,
                "assets": [
                    {
                        "tokenAddress": USDT_ADDRESS,
                        "balance": 5000000,
                        "transferFee": 1000000,
                    }
                ],
            }
        )
        client_instance.get_providers = AsyncMock(
            return_value=[{"address": "TMerchantAddr12345678901234567890"}]
        )
        yield client_instance


class TestGasFreeClient:
    @pytest.mark.anyio
    async def test_create_payment_payload(self, mock_signer, nile_requirements, mock_api_client):
        mechanism = ExactGasFreeClientMechanism(mock_signer)
        payload = await mechanism.create_payment_payload(
            nile_requirements, "https://example.com/resource"
        )

        assert payload.x402_version == 2
        assert payload.resource.url == "https://example.com/resource"
        assert payload.accepted == nile_requirements
        assert payload.payload.signature == "0x" + "ab" * 65
        assert payload.extensions["gasfreeAddress"] == "TLCvf7MktLG7XkbJRyUwnvCeDnaEXYkcbC"
        assert payload.payload.payment_permit.meta.nonce == "1"

        # Verify primary_type was passed
        mock_signer.sign_typed_data.assert_called_once()
        assert mock_signer.sign_typed_data.call_args.kwargs["primary_type"] == GASFREE_PRIMARY_TYPE

    @pytest.mark.anyio
    async def test_max_fee_adjustment(self, mock_signer, nile_requirements, mock_api_client):
        # Requirements has 0.1 USDT fee, but protocol needs 1 USDT
        nile_requirements.extra = MagicMock()
        nile_requirements.extra.fee = MagicMock()
        nile_requirements.extra.fee.fee_amount = "100000"

        mechanism = ExactGasFreeClientMechanism(mock_signer)
        payload = await mechanism.create_payment_payload(
            nile_requirements, "https://example.com/resource"
        )

        # Should be adjusted to 1 USDT (10^6)
        assert payload.payload.payment_permit.fee.fee_amount == "1000000"

    @pytest.mark.anyio
    async def test_insufficient_balance(self, mock_signer, nile_requirements, mock_api_client):
        from bankofai.x402.exceptions import InsufficientGasFreeBalance

        mock_api_client.get_address_info.return_value["assets"][0]["balance"] = 1000000

        mechanism = ExactGasFreeClientMechanism(mock_signer)
        with pytest.raises(InsufficientGasFreeBalance):
            await mechanism.create_payment_payload(nile_requirements, "https://example.com")

    @pytest.mark.anyio
    async def test_not_activated(self, mock_signer, nile_requirements, mock_api_client):
        from bankofai.x402.exceptions import GasFreeAccountNotActivated

        mock_api_client.get_address_info.return_value["active"] = False

        mechanism = ExactGasFreeClientMechanism(mock_signer)
        with pytest.raises(GasFreeAccountNotActivated):
            await mechanism.create_payment_payload(nile_requirements, "https://example.com")
