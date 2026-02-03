"""
x402 类型测试
"""

import pytest
from x402.types import (
    PaymentPermit,
    PermitMeta,
    Payment,
    Fee,
    Delivery,
    PaymentRequirements,
)


def test_payment_permit_creation():
    """测试 PaymentPermit 模型创建"""
    permit = PaymentPermit(
        meta=PermitMeta(
            kind="PAYMENT_ONLY",
            paymentId="test_id",
            nonce="12345",
            validAfter=1000,
            validBefore=2000,
        ),
        buyer="TTestBuyerAddress",
        caller="TTestCallerAddress",
        payment=Payment(
            payToken="TTestTokenAddress",
            maxPayAmount="1000000",
            payTo="TTestPayToAddress",
        ),
        fee=Fee(feeTo="TTestFeeAddress", feeAmount="10000"),
        delivery=Delivery(
            receiveToken="T0000000000000000000000000000000",
            miniReceiveAmount="0",
            tokenId="0",
        ),
    )

    assert permit.buyer == "TTestBuyerAddress"
    assert permit.payment.max_pay_amount == "1000000"
    assert permit.meta.kind == "PAYMENT_ONLY"


def test_payment_requirements_creation():
    """测试 PaymentRequirements 模型创建"""
    requirements = PaymentRequirements(
        scheme="exact",
        network="tron:shasta",
        amount="1000000",
        asset="TTestUSDTAddress",
        payTo="TTestMerchantAddress",
        maxTimeoutSeconds=3600,
    )

    assert requirements.scheme == "exact"
    assert requirements.network == "tron:shasta"
    assert requirements.amount == "1000000"


def test_payment_permit_serialization():
    """测试 PaymentPermit 序列化为字典"""
    permit = PaymentPermit(
        meta=PermitMeta(
            kind="PAYMENT_ONLY",
            paymentId="test_id",
            nonce="12345",
            validAfter=1000,
            validBefore=2000,
        ),
        buyer="TTestBuyerAddress",
        caller="TTestCallerAddress",
        payment=Payment(
            payToken="TTestTokenAddress",
            maxPayAmount="1000000",
            payTo="TTestPayToAddress",
        ),
        fee=Fee(feeTo="TTestFeeAddress", feeAmount="10000"),
        delivery=Delivery(
            receiveToken="T0000000000000000000000000000000",
            miniReceiveAmount="0",
            tokenId="0",
        ),
    )

    data = permit.model_dump(by_alias=True)
    assert "buyer" in data
    assert "payment" in data
    assert data["payment"]["maxPayAmount"] == "1000000"
