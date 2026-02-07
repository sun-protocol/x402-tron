"""
FastAPI middleware for x402 payment processing
"""

from functools import wraps
from typing import TYPE_CHECKING, Any, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from x402_tron.encoding import decode_payment_payload, encode_payment_payload
from x402_tron.server import ResourceConfig, X402Server
from x402_tron.types import PaymentPayload, PaymentRequirements

if TYPE_CHECKING:
    from x402_tron.utils.tx_verification import TransactionVerificationResult

PAYMENT_SIGNATURE_HEADER = "PAYMENT-SIGNATURE"
PAYMENT_REQUIRED_HEADER = "PAYMENT-REQUIRED"
PAYMENT_RESPONSE_HEADER = "PAYMENT-RESPONSE"


class X402Middleware:
    """
    FastAPI middleware for automatic 402 payment handling.

    Usage:
        app = FastAPI()
        server = X402Server().set_facilitator(...)
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
        Decorator to protect endpoints with payment requirements.

        Args:
            price: Price string (e.g. "100 USDC")
            network: Network identifier
            pay_to: Payment recipient address
            scheme: Payment scheme
            valid_for: Payment validity period (seconds)
            delivery_mode: Delivery mode

        Returns:
            Decorated function
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
                except Exception as e:
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.error(f"Failed to decode payment payload: {e}", exc_info=True)
                    logger.error(
                        f"Payment header content (first 200 chars): {payment_header[:200]}"
                    )
                    return JSONResponse(
                        content={"error": f"Invalid payment payload: {str(e)}"}, status_code=400
                    )

                requirements = await self._server.build_payment_requirements(config)

                verify_result = await self._server.verify_payment(payload, requirements)
                if not verify_result.is_valid:
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.error(f"Payment verification failed: {verify_result.invalid_reason}")
                    logger.error(f"Payload details: {payload.model_dump(by_alias=True)}")
                    logger.error(f"Requirements: {requirements.model_dump(by_alias=True)}")
                    return JSONResponse(
                        content={"error": f"Verification failed: {verify_result.invalid_reason}"},
                        status_code=400,
                    )

                settle_result = await self._server.settle_payment(payload, requirements)
                if not settle_result.success:
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.error(f"Payment settlement failed: {settle_result.error_reason}")
                    logger.error(f"Settlement result: {settle_result.model_dump(by_alias=True)}")
                    return JSONResponse(
                        content={"error": f"Settlement failed: {settle_result.error_reason}"},
                        status_code=500,
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
                                "error": (
                                    "Transaction verification failed: "
                                    f"{tx_verify_result.error_reason}"
                                ),
                                "txHash": settle_result.transaction,
                            },
                            status_code=500,
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
        requirements: PaymentRequirements,
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
        from x402_tron.utils.tx_verification import (
            TransactionVerificationResult,
            get_verifier_for_network,
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
        """Return 402 payment required response"""
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
    Convenience decorator to protect endpoints.

    Usage:
        @app.get("/protected")
        @x402_protected(server, price="100 USDC", network="eip155:8453", pay_to="0x...")
        async def protected_endpoint():
            return {"data": "secret"}
    """
    middleware = X402Middleware(server)
    return middleware.protect(price=price, network=network, pay_to=pay_to, **kwargs)
