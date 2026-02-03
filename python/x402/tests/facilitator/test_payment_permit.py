"""
PaymentPermit 合约 Facilitator 测试 - Tron Nile 测试网
合约地址: TDw6aSVuoix8vuXdrZgVXyejpCnmuvyjbF
核心测试: settle 执行
"""

import asyncio
import time
import pytest
from unittest.mock import AsyncMock, MagicMock

from x402.mechanisms.facilitator.tron_upto import UptoTronFacilitatorMechanism
from x402.types import (
    PaymentRequirements,
    PaymentPayload,
    PaymentPayloadData,
    PaymentPermit,
    PermitMeta,
    Payment,
    Fee,
    Delivery,
    ResourceInfo,
)


@pytest.fixture
def mock_signer():
    signer = MagicMock()
    signer.get_address.return_value = "TTestFacilitator"
    signer.verify_typed_data = AsyncMock(return_value=True)
    signer.write_contract = AsyncMock(return_value="txhash123456")
    signer.wait_for_transaction_receipt = AsyncMock(
        return_value={"hash": "txhash123456", "blockNumber": "12345", "status": "confirmed"}
    )
    return signer


@pytest.fixture
def nile_requirements():
    return PaymentRequirements(
        scheme="exact",
        network="tron:nile",
        amount="1000000",
        asset="TTestUSDTAddress",
        payTo="TTestMerchantAddress",
    )


@pytest.fixture
def valid_payload(nile_requirements):
    now = int(time.time())
    return PaymentPayload(
        x402Version=2,
        resource=ResourceInfo(url="https://api.example.com/resource"),
        accepted=nile_requirements,
        payload=PaymentPayloadData(
            signature="0x" + "ab" * 65,
            paymentPermit=PaymentPermit(
                meta=PermitMeta(
                    kind="PAYMENT_ONLY",
                    paymentId="0x" + "12" * 16,
                    nonce="1",
                    validAfter=0,
                    validBefore=now + 3600,
                ),
                buyer="TTestBuyerAddress",
                caller="TTestFacilitator",
                payment=Payment(
                    payToken="TTestUSDTAddress",
                    maxPayAmount="1000000",
                    payTo="TTestMerchantAddress",
                ),
                fee=Fee(feeTo="TTestFacilitator", feeAmount="10000"),
                delivery=Delivery(
                    receiveToken="T0000000000000000000000000000000",
                    miniReceiveAmount="0",
                    tokenId="0",
                ),
            ),
        ),
    )


class TestFacilitatorSettle:
    """Facilitator settle 执行测试"""

    def test_settle_success(self, mock_signer, valid_payload, nile_requirements):
        """测试成功结算"""
        mechanism = UptoTronFacilitatorMechanism(mock_signer)

        result = asyncio.get_event_loop().run_until_complete(
            mechanism.settle(valid_payload, nile_requirements)
        )

        assert result.success is True
        assert result.transaction == "txhash123456"
        assert result.network == "tron:nile"
        mock_signer.write_contract.assert_called_once()

    def test_settle_calls_permit_transfer_from(self, mock_signer, valid_payload, nile_requirements):
        """测试 settle 调用 permitTransferFrom 方法"""
        mechanism = UptoTronFacilitatorMechanism(mock_signer)

        asyncio.get_event_loop().run_until_complete(
            mechanism.settle(valid_payload, nile_requirements)
        )

        call_args = mock_signer.write_contract.call_args
        assert call_args.kwargs["method"] == "permitTransferFrom"

    def test_settle_transaction_failed(self, mock_signer, valid_payload, nile_requirements):
        """测试交易失败"""
        mock_signer.write_contract = AsyncMock(return_value=None)
        mechanism = UptoTronFacilitatorMechanism(mock_signer)

        result = asyncio.get_event_loop().run_until_complete(
            mechanism.settle(valid_payload, nile_requirements)
        )

        assert result.success is False
        assert result.error_reason == "transaction_failed"
