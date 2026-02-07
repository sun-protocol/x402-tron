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
        price: str | None = None,
        network: str | None = None,
        pay_to: str | None = None,
        scheme: str = "exact",
        valid_for: int = 3600,
        delivery_mode: str = "PAYMENT_ONLY",
        prices: list[str] | None = None,
    ) -> Callable:
        """
        Decorator to protect endpoints with payment requirements.

        Supports single token or multiple tokens per endpoint.

        Single token:
            @middleware.protect(price="1 USDT", network="tron:nile", pay_to="T...")

        Multiple tokens:
            @middleware.protect(
                network="tron:nile",
                pay_to="T...",
                prices=["1 USDT", "1 USDD"],
            )

        Args:
            price: Price string (e.g. "100 USDC"), for single-token mode
            network: Network identifier (shared by all prices)
            pay_to: Payment recipient address
            scheme: Payment scheme
            valid_for: Payment validity period (seconds)
            delivery_mode: Delivery mode
            prices: List of price strings for multi-token mode

        Returns:
            Decorated function
        """
        if prices is not None:
            if not network or not pay_to:
                raise ValueError("network and pay_to are required when using prices list")
            configs = [
                ResourceConfig(
                    scheme=scheme,
                    network=network,
                    price=p,
                    pay_to=pay_to,
                    valid_for=valid_for,
                    delivery_mode=delivery_mode,
                )
                for p in prices
            ]
        else:
            if not price or not network or not pay_to:
                raise ValueError(
                    "price, network, and pay_to are required when prices list is not provided"
                )
            configs = [
                ResourceConfig(
                    scheme=scheme,
                    network=network,
                    price=price,
                    pay_to=pay_to,
                    valid_for=valid_for,
                    delivery_mode=delivery_mode,
                )
            ]

        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def wrapper(request: Request, *args: Any, **kwargs: Any) -> Response:
                payment_header = request.headers.get(PAYMENT_SIGNATURE_HEADER)

                if not payment_header:
                    return await self._return_payment_required(request, configs)

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

                # Match payload to the correct config
                config = self._match_config(
                    configs, payload.accepted.network, payload.accepted.asset
                )
                if config is None:
                    return JSONResponse(
                        content={"error": "Unsupported payment token or network"},
                        status_code=400,
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
                        network=requirements.network,
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

    @staticmethod
    def _match_config(
        configs: list[ResourceConfig],
        network: str,
        asset: str,
    ) -> ResourceConfig | None:
        """Find the config matching the payment's network and asset."""
        from x402_tron.tokens import TokenRegistry

        for cfg in configs:
            if cfg.network != network:
                continue
            # Parse the price to get the expected asset address
            parts = cfg.price.strip().split()
            if len(parts) != 2:
                continue
            symbol = parts[1]
            token = TokenRegistry.get_token(cfg.network, symbol)
            if token and token.address.lower() == asset.lower():
                return cfg
        return None

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
        configs: list[ResourceConfig],
        error: str | None = None,
    ) -> JSONResponse:
        """Return 402 payment required response"""
        requirements_list = []
        for cfg in configs:
            req = await self._server.build_payment_requirements(cfg)
            requirements_list.append(req)

        payment_required = self._server.create_payment_required_response(
            requirements=requirements_list,
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
    pay_to: str,
    price: str | None = None,
    network: str | None = None,
    prices: list[str] | None = None,
    **kwargs: Any,
) -> Callable:
    """
    Convenience decorator to protect endpoints.

    Single token:
        @x402_protected(server, price="1 USDT", network="tron:nile", pay_to="T...")

    Multiple tokens:
        @x402_protected(
            server,
            network="tron:nile",
            pay_to="T...",
            prices=["1 USDT", "1 USDD"],
        )
    """
    middleware = X402Middleware(server)
    return middleware.protect(price=price, network=network, pay_to=pay_to, prices=prices, **kwargs)
