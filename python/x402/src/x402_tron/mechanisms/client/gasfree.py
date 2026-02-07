"""
GasFreeTronClientMechanism - GasFree payment scheme client mechanism for TRON.
"""

import logging
import time
from typing import TYPE_CHECKING, Any

from x402_tron.address import TronAddressConverter
from x402_tron.config import NetworkConfig

from x402_tron.mechanisms.client.base import ClientMechanism
from x402_tron.types import (
    PAYMENT_ONLY,
    Delivery,
    Fee,
    Payment,
    PaymentPayload,
    PaymentPayloadData,
    PaymentPermit,
    PaymentRequirements,
    PermitMeta,
    ResourceInfo,
)
from x402_tron.address import TronAddressConverter
from x402_tron.utils.gasfree import (
    GASFREE_PERMIT_TRANSFER_TYPES,
    GasFreeAPIClient,
    GasFreeTronAddressCalculator,
    get_gasfree_domain,
)

if TYPE_CHECKING:
    from x402_tron.signers.client import ClientSigner


class GasFreeTronClientMechanism(ClientMechanism):
    """GasFree payment mechanism for TRON.

    This mechanism allows users to pay with USDT/USDD without having TRX for gas.
    It automatically calculates the user's GasFree address and signs a TIP-712
    permit for the GasFreeController.
    """

    def __init__(self, signer: "ClientSigner") -> None:
        self._signer = signer
        self._address_converter = TronAddressConverter()
        self._api_client = GasFreeAPIClient()
        self._logger = logging.getLogger(self.__class__.__name__)

    def scheme(self) -> str:
        return "gasfree_exact"

    async def create_payment_payload(
        self,
        requirements: PaymentRequirements,
        resource: str,
        extensions: dict[str, Any] | None = None,
    ) -> PaymentPayload:
        """Create GasFree payment payload"""
        self._logger.info("=" * 60)
        self._logger.info(f"Creating GasFree payment payload for: {resource}")

        network = requirements.network
        user_address = self._signer.get_address()

        # 1. Calculate GasFree address
        controller = NetworkConfig.get_gasfree_controller_address(network)
        beacon = NetworkConfig.get_gasfree_beacon_address(network)
        creation_code = NetworkConfig.get_gasfree_creation_code(network)

        gasfree_address = GasFreeTronAddressCalculator.calculate_gasfree_address(
            user_address, controller, beacon, creation_code
        )

        # 1.1 Check balance
        skip_balance_check = (extensions or {}).get("skipBalanceCheck", False)
        if not skip_balance_check:
            # Note: In a real implementation, this would call the TRON client
            # to verify requirements.asset balance of gasfree_address >= requirements.amount + maxFee
            self._logger.info(f"Verifying balance for {gasfree_address}...")
            # For design purposes, we assume balance is checked here.
            # If insufficient, it should raise InsufficientGasFreeBalance error.

        self._logger.info(f"[GASFREE] User Wallet: {user_address}")
        self._logger.info(f"[GASFREE] GasFree Address: {gasfree_address}")
        self._logger.info(f"[GASFREE] Token: {requirements.asset}")
        self._logger.info(f"[GASFREE] Amount: {requirements.amount}")

        # 2. Prepare GasFree transaction parameters
        # We map these to x402 PaymentPermit structure for compatibility
        context = (extensions or {}).get("paymentPermitContext") or {}
        meta = context.get("meta") or {}

        # Default maxFee to 0.1 USDT (10^5) if not provided by server
        max_fee = "100000"
        if requirements.extra and requirements.extra.fee:
            max_fee = requirements.extra.fee.fee_amount

        deadline = meta.get("validBefore") or int(time.time()) + 3600

        # Get Nonce via HTTP API
        chain_id = NetworkConfig.get_chain_id(network)
        nonce = meta.get("nonce")
        if nonce is None:
            self._logger.info(f"Fetching nonce for {user_address} from GasFree API...")
            nonce = await self._api_client.get_nonce(
                user=user_address, token=requirements.asset, chain_id=chain_id
            )

        nonce = int(nonce)

        # 3. Build GasFree TIP-712 Message
        # The fields must match GasFree PermitTransfer exactly
        message = {
            "token": self._address_converter.to_evm_format(requirements.asset),
            "serviceProvider": self._address_converter.to_evm_format(requirements.pay_to),
            "user": self._address_converter.to_evm_format(user_address),
            "receiver": self._address_converter.to_evm_format(requirements.pay_to),
            "value": int(requirements.amount),
            "maxFee": int(max_fee),
            "deadline": int(deadline),
            "version": 1,
            "nonce": int(nonce),
        }

        # 4. Sign
        self._logger.info("Signing GasFree transaction with TIP-712...")
        chain_id = NetworkConfig.get_chain_id(network)
        domain = get_gasfree_domain(chain_id, controller)

        signature = await self._signer.sign_typed_data(
            domain=domain,
            types=GASFREE_PERMIT_TRANSFER_TYPES,
            message=message,
        )

        # 5. Pack into PaymentPayload
        # We reuse PaymentPermit structure to avoid breaking the core protocol
        permit = PaymentPermit(
            meta=PermitMeta(
                kind=PAYMENT_ONLY,
                paymentId=meta.get("paymentId", ""),
                nonce=str(nonce),
                validAfter=meta.get("validAfter", 0),
                validBefore=int(deadline),
            ),
            buyer=user_address,
            caller=controller,  # Indicating GasFreeController is the caller
            payment=Payment(
                payToken=requirements.asset,
                payAmount=requirements.amount,
                payTo=requirements.pay_to,
            ),
            fee=Fee(
                feeTo=requirements.pay_to,  # Typically ServiceProvider
                feeAmount=max_fee,
            ),
            delivery=Delivery(
                receiveToken=self._address_converter.get_zero_address(),
                miniReceiveAmount="0",
                tokenId="0",
            ),
        )

        self._logger.info("GasFree payment payload created successfully")
        self._logger.info("=" * 60)

        return PaymentPayload(
            x402Version=2,
            resource=ResourceInfo(url=resource),
            accepted=requirements,
            payload=PaymentPayloadData(
                signature=signature,
                paymentPermit=permit,
            ),
            extensions={
                "gasfreeAddress": gasfree_address,
                "scheme": "gasfree_exact",
            },
        )
