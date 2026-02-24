"""
GasFreeTronClientMechanism - GasFree payment scheme client mechanism for TRON.
"""

import logging
import time
from typing import TYPE_CHECKING, Any

from bankofai.x402.address.converter import TronAddressConverter
from bankofai.x402.config import NetworkConfig
from bankofai.x402.exceptions import GasFreeAccountNotActivated, InsufficientGasFreeBalance
from bankofai.x402.mechanisms._base.client import ClientMechanism
from bankofai.x402.types import (
    PAYMENT_ONLY,
    Fee,
    Payment,
    PaymentPayload,
    PaymentPayloadData,
    PaymentPermit,
    PaymentRequirements,
    PermitMeta,
    ResourceInfo,
)
from bankofai.x402.utils.gasfree import (
    GASFREE_PERMIT_TRANSFER_TYPES,
    GasFreeAPIClient,
    get_gasfree_domain,
)

if TYPE_CHECKING:
    from bankofai.x402.signers.client.base import ClientSigner


class GasFreeTronClientMechanism(ClientMechanism):
    """GasFree payment mechanism for TRON (USDT/USDD)"""

    def __init__(self, signer: "ClientSigner") -> None:
        self._signer = signer
        self._address_converter = TronAddressConverter()
        self._logger = logging.getLogger(self.__class__.__name__)

    def scheme(self) -> str:
        return "gasfree_exact"

    def get_signer(self) -> Any:
        return self._signer

    async def create_payment_payload(
        self,
        requirements: PaymentRequirements,
        resource: str,
        extensions: dict[str, Any] | None = None,
    ) -> PaymentPayload:
        """Create GasFree payment payload using official API for status checks and nonce"""
        network = requirements.network
        user_address = self._signer.get_address()
        api_base_url = NetworkConfig.get_gasfree_api_base_url(network)
        api_key = NetworkConfig.get_gasfree_api_key(network)
        api_secret = NetworkConfig.get_gasfree_api_secret(network)
        api_client = GasFreeAPIClient(api_base_url, api_key, api_secret)

        # 1. Fetch account info
        self._logger.debug(f"Fetching account info for {user_address} from GasFree API...")
        account_info = await api_client.get_address_info(user_address)
        gasfree_address = account_info.get("gasFreeAddress")
        is_active = account_info.get("active", False)
        nonce = int(account_info.get("nonce", 0))

        if not gasfree_address:
            raise RuntimeError(f"Could not retrieve GasFree address for {user_address}")

        # 2. Check activation status
        if not is_active:
            raise GasFreeAccountNotActivated(user_address, gasfree_address)

        # 3. Prepare maxFee and validate against protocol transferFee
        assets = account_info.get("assets", [])
        asset_balance = 0
        transfer_fee = 0
        target_token = self._address_converter.normalize(requirements.asset)

        for asset in assets:
            if asset.get("tokenAddress") == target_token:
                asset_balance = int(asset.get("balance", 0))
                transfer_fee = int(asset.get("transferFee", 0))
                break

        # Facilitator base fee is usually 1,000,000 (1 USDT)
        max_fee = str(transfer_fee)
        if requirements.extra and requirements.extra.fee:
            max_fee = requirements.extra.fee.fee_amount
        elif transfer_fee == 0:
            max_fee = "1000000"  # Default fallback to 1 USDT if API returns 0

        max_fee_val = int(max_fee)
        if max_fee_val < transfer_fee:
            self._logger.debug(f"Increasing maxFee to {transfer_fee} to meet protocol requirement")
            max_fee_val = transfer_fee
            max_fee = str(max_fee_val)

        # 4. Balance verification
        skip_balance_check = (extensions or {}).get("skipBalanceCheck", False)
        if not skip_balance_check:
            self._logger.debug(f"Verifying balance for {gasfree_address}...")
            required_total = int(requirements.amount) + max_fee_val
            if asset_balance < required_total:
                raise InsufficientGasFreeBalance(gasfree_address, required_total, asset_balance)

        deadline = (extensions or {}).get("paymentPermitContext", {}).get("meta", {}).get(
            "validBefore"
        ) or int(time.time()) + 3600

        self._logger.debug(f"[GASFREE] User Wallet: {user_address}")
        self._logger.debug(f"[GASFREE] GasFree Address: {gasfree_address}")
        self._logger.debug(f"[GASFREE] Token: {requirements.asset}")
        self._logger.debug(f"[GASFREE] Amount: {requirements.amount}")
        self._logger.debug(f"[GASFREE] Max Fee: {max_fee}")

        # 5. Sign TIP-712 Message
        self._logger.debug("Signing GasFree transaction with TIP-712...")
        chain_id = NetworkConfig.get_chain_id(network)
        controller = NetworkConfig.get_gasfree_controller_address(network)
        domain = get_gasfree_domain(chain_id, controller)

        signature = await self._signer.sign_typed_data(
            domain=domain,
            types=GASFREE_PERMIT_TRANSFER_TYPES,
            message={
                "token": self._address_converter.to_evm_format(requirements.asset),
                "serviceProvider": self._address_converter.to_evm_format(requirements.pay_to),
                "user": self._address_converter.to_evm_format(user_address),
                "receiver": self._address_converter.to_evm_format(requirements.pay_to),
                "value": int(requirements.amount),
                "maxFee": max_fee_val,
                "deadline": int(deadline),
                "version": 1,
                "nonce": nonce,
            },
        )

        # 6. Pack into PaymentPayload
        permit = PaymentPermit(
            meta=PermitMeta(
                kind=PAYMENT_ONLY,
                paymentId=(extensions or {})
                .get("paymentPermitContext", {})
                .get("meta", {})
                .get("paymentId", ""),
                nonce=str(nonce),
                validAfter=(extensions or {})
                .get("paymentPermitContext", {})
                .get("meta", {})
                .get("validAfter", 0),
                validBefore=int(deadline),
            ),
            buyer=user_address,
            caller=controller,
            payment=Payment(
                payToken=requirements.asset,
                payAmount=requirements.amount,
                payTo=requirements.pay_to,
            ),
            fee=Fee(
                feeTo=requirements.pay_to,
                feeAmount=max_fee,
            ),
        )

        return PaymentPayload(
            x402Version=2,
            resource=ResourceInfo(url=resource, mimeType="application/json"),
            accepted=requirements,
            payload=PaymentPayloadData(
                signature=signature,
                merchantSignature=None,
                paymentPermit=permit,
            ),
            extensions={
                "gasfreeAddress": gasfree_address,
                "scheme": "gasfree_exact",
            },
        )
