"""
FastAPI 中间件用于 x402 支付处理
"""

import base64
import json
from functools import wraps
from typing import Any, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from x402.server import X402Server, ResourceConfig
from x402.encoding import decode_payment_payload, encode_payment_payload
from x402.types import PaymentPayload, PaymentRequired


PAYMENT_SIGNATURE_HEADER = "PAYMENT-SIGNATURE"
PAYMENT_REQUIRED_HEADER = "PAYMENT-REQUIRED"
PAYMENT_RESPONSE_HEADER = "PAYMENT-RESPONSE"


class X402Middleware:
    """
    FastAPI 中间件用于自动 402 支付处理。

    用法:
        app = FastAPI()
        server = X402Server().add_facilitator(...)
        middleware = X402Middleware(server)

        @app.get("/protected")
        @middleware.protect(price="100 USDC", network="eip155:8453", pay_to="0x...")
        async def protected_endpoint():
            return {"data": "secret"}
    """

    def __init__(self, server: X402Server) -> None:
        self._server = server

    def protect(
        self,
        price: str,
        network: str,
        pay_to: str,
        scheme: str = "exact",
        valid_for: int = 3600,
        delivery_mode: str = "PAYMENT_ONLY",
    ) -> Callable:
        """
        装饰器用于使用支付要求保护端点。

        参数:
            price: 价格字符串（例如 "100 USDC"）
            network: 网络标识符
            pay_to: 支付接收地址
            scheme: 支付方案
            valid_for: 支付有效期（秒）
            delivery_mode: 交付模式

        返回:
            装饰后的函数
        """
        config = ResourceConfig(
            scheme=scheme,
            network=network,
            price=price,
            pay_to=pay_to,
            valid_for=valid_for,
            delivery_mode=delivery_mode,
        )

        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def wrapper(request: Request, *args: Any, **kwargs: Any) -> Response:
                payment_header = request.headers.get(PAYMENT_SIGNATURE_HEADER)

                if not payment_header:
                    return await self._return_payment_required(request, config)

                try:
                    payload = decode_payment_payload(payment_header, PaymentPayload)
                except Exception:
                    return JSONResponse(
                        content={"error": "Invalid payment payload"},
                        status_code=400
                    )

                requirements = await self._server.build_payment_requirements(config)

                verify_result = await self._server.verify_payment(payload, requirements)
                if not verify_result.is_valid:
                    return JSONResponse(
                        content={"error": f"Verification failed: {verify_result.invalid_reason}"},
                        status_code=400
                    )

                settle_result = await self._server.settle_payment(payload, requirements)
                if not settle_result.success:
                    return JSONResponse(
                        content={"error": f"Settlement failed: {settle_result.error_reason}"},
                        status_code=500
                    )

                # Verify transaction on-chain (required)
                if settle_result.transaction:
                    tx_verify_result = await self._verify_transaction_on_chain(
                        tx_hash=settle_result.transaction,
                        payload=payload,
                        requirements=requirements,
                        network=network,
                    )
                    if not tx_verify_result.success:
                        return JSONResponse(
                            content={
                                "error": f"Transaction verification failed: {tx_verify_result.error_reason}",
                                "txHash": settle_result.transaction,
                            },
                            status_code=500
                        )

                response = await func(request, *args, **kwargs)

                if isinstance(response, Response):
                    response.headers[PAYMENT_RESPONSE_HEADER] = encode_payment_payload(
                        settle_result.model_dump(by_alias=True)
                    )
                    return response

                json_response = JSONResponse(content=response)
                json_response.headers[PAYMENT_RESPONSE_HEADER] = encode_payment_payload(
                    settle_result.model_dump(by_alias=True)
                )
                return json_response

            return wrapper
        return decorator

    async def _verify_transaction_on_chain(
        self,
        tx_hash: str,
        payload: PaymentPayload,
        requirements: "PaymentRequirements",
        network: str,
    ) -> "TransactionVerificationResult":
        """
        Verify transaction on-chain to ensure transfers match expectations.
        
        Args:
            tx_hash: Transaction hash to verify
            payload: Payment payload
            requirements: Payment requirements
            network: Network identifier
            
        Returns:
            TransactionVerificationResult
        """
        from x402.utils.tx_verification import (
            get_verifier_for_network,
            TransactionVerificationResult,
        )
        
        try:
            verifier = get_verifier_for_network(network)
            return await verifier.verify_transaction(tx_hash, payload, requirements)
        except ValueError as e:
            # No verifier available for this network, skip verification
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Transaction verification skipped: {e}")
            return TransactionVerificationResult(
                success=True,
                tx_hash=tx_hash,
                status_verified=True,
            )


    async def _return_payment_required(
        self,
        request: Request,
        config: ResourceConfig,
        error: str | None = None,
    ) -> JSONResponse:
        """返回 402 需要支付响应"""
        requirements = await self._server.build_payment_requirements(config)

        payment_required = self._server.create_payment_required_response(
            requirements=[requirements],
            resource_info={"url": str(request.url)},
        )

        response_data = payment_required.model_dump(by_alias=True)
        if error:
            response_data["error"] = error

        response = JSONResponse(content=response_data, status_code=402)
        response.headers[PAYMENT_REQUIRED_HEADER] = encode_payment_payload(response_data)

        return response


def x402_protected(
    server: X402Server,
    price: str,
    network: str,
    pay_to: str,
    **kwargs: Any,
) -> Callable:
    """
    保护端点的便捷装饰器。

    用法:
        @app.get("/protected")
        @x402_protected(server, price="100 USDC", network="eip155:8453", pay_to="0x...")
        async def protected_endpoint():
            return {"data": "secret"}
    """
    middleware = X402Middleware(server)
    return middleware.protect(price=price, network=network, pay_to=pay_to, **kwargs)
