"""
GasFreeFacilitatorMechanism - GasFree payment scheme facilitator mechanism for TRON.
"""

import time
from typing import Optional

from bankofai.x402.abi import GASFREE_PRIMARY_TYPE
from bankofai.x402.address.converter import AddressConverter, TronAddressConverter
from bankofai.x402.config import NetworkConfig
from bankofai.x402.mechanisms._exact_permit_base.facilitator import (
    BaseExactPermitFacilitatorMechanism,
)
from bankofai.x402.types import (
    PaymentPayload,
    PaymentPermit,
    PaymentRequirements,
    SettleResponse,
    VerifyResponse,
)
from bankofai.x402.utils.gasfree import (
    GASFREE_TYPES,
    GasFreeAPIClient,
    get_gasfree_domain,
)


class GasFreeFacilitatorMechanism(BaseExactPermitFacilitatorMechanism):
    """GasFree facilitator mechanism for TRON (API Proxy mode)"""

    def scheme(self) -> str:
        return "gasfree_exact"

    def _get_address_converter(self) -> AddressConverter:
        return TronAddressConverter()

    async def _validate_permit_async(
        self, permit: PaymentPermit, requirements: PaymentRequirements
    ) -> str | None:
        """
        Specialized validation for GasFree:
        1. receiver (permit.pay_to) must match merchant (requirements.pay_to)
        2. serviceProvider (permit.fee_to) must be a valid GasFree provider
        """
        norm = self._address_converter.normalize

        # Business Logic Validation (Amount and Asset)
        if int(permit.payment.pay_amount) < int(requirements.amount):
            return "amount_mismatch"

        if norm(permit.payment.pay_token) != norm(requirements.asset):
            return "token_mismatch"

        # PayTo (Merchant) validation
        if norm(permit.payment.pay_to) != norm(requirements.pay_to):
            self._logger.warning(
                f"Merchant mismatch: {permit.payment.pay_to} != {requirements.pay_to}"
            )
            return "payto_mismatch"

        # Provider validation: The serviceProvider in GasFree permit must be valid
        network = requirements.network
        api_base_url = NetworkConfig.get_gasfree_api_base_url(network)
        api_key = NetworkConfig.get_gasfree_api_key(network)
        api_secret = NetworkConfig.get_gasfree_api_secret(network)
        api_client = GasFreeAPIClient(api_base_url, api_key, api_secret)

        try:
            providers = await api_client.get_providers()
            allowed_providers = {norm(p["address"]) for p in providers}

            fee_to_norm = norm(permit.fee.fee_to)
            if fee_to_norm not in allowed_providers:
                self._logger.warning(f"Provider {permit.fee.fee_to} is not in allowed list")
                return "fee_to_mismatch"
        except Exception as e:
            self._logger.error(f"Failed to fetch providers for validation: {e}")
            # Fallback to self._fee_to if API fails
            if norm(permit.fee.fee_to) != norm(self._fee_to):
                return "fee_to_mismatch"

        # Date validation
        now = int(time.time())
        if permit.meta.valid_before < now:
            return "expired"

        return None

    async def verify(
        self, payload: PaymentPayload, requirements: PaymentRequirements
    ) -> VerifyResponse:
        """Override verify to use async validation"""
        permit = payload.payload.payment_permit
        if not permit:
            return VerifyResponse(isValid=False, invalidReason="missing_permit")

        reason = await self._validate_permit_async(permit, requirements)
        if reason:
            return VerifyResponse(isValid=False, invalidReason=reason)

        # Signature verification
        is_valid_sig = await self._verify_signature(
            permit, payload.payload.signature, requirements.network
        )
        if not is_valid_sig:
            return VerifyResponse(isValid=False, invalidReason="invalid_signature")

        return VerifyResponse(isValid=True)

    async def _verify_signature(
        self,
        permit: PaymentPermit,
        signature: str,
        network: str,
    ) -> bool:
        """Verify GasFree TIP-712 signature locally before forwarding"""
        controller = NetworkConfig.get_gasfree_controller_address(network)
        chain_id = NetworkConfig.get_chain_id(network)
        converter = self._address_converter

        # Reconstruct GasFree message from the mapped permit
        message = {
            "token": converter.to_evm_format(permit.payment.pay_token),
            "serviceProvider": converter.to_evm_format(permit.fee.fee_to),
            "user": converter.to_evm_format(permit.buyer),
            "receiver": converter.to_evm_format(permit.payment.pay_to),
            "value": int(permit.payment.pay_amount),
            "maxFee": int(permit.fee.fee_amount),
            "deadline": int(permit.meta.valid_before),
            "version": 1,
            "nonce": int(permit.meta.nonce),
        }

        domain = get_gasfree_domain(chain_id, controller)

        self._logger.debug(f"[VERIFY GASFREE] Domain: {domain}")
        self._logger.debug(f"[VERIFY GASFREE] Message: {message}")

        return await self._signer.verify_typed_data(
            address=permit.buyer,
            domain=domain,
            types=GASFREE_TYPES,
            message=message,
            signature=signature,
            primary_type=GASFREE_PRIMARY_TYPE,
        )

    async def settle(
        self,
        payload: PaymentPayload,
        requirements: PaymentRequirements,
    ) -> SettleResponse:
        """
        Specialized settle for GasFree: Settle via API and wait for result.
        """
        # 1. Validation (re-run verify to ensure consistency)
        verify_result = await self.verify(payload, requirements)
        if not verify_result.is_valid:
            return SettleResponse(
                success=False,
                errorReason=verify_result.invalid_reason or "verification_failed",
                network=requirements.network,
            )

        # 2. Extract permit and signature
        permit = payload.payload.payment_permit
        signature = payload.payload.signature

        if not permit or not signature:
            return SettleResponse(
                success=False,
                errorReason="missing_payload_data",
                network=requirements.network,
            )

        self._logger.info(f"Starting GasFree API settlement: paymentId={permit.meta.payment_id}")

        # 3. Call API Proxy and Wait
        network = requirements.network
        api_base_url = NetworkConfig.get_gasfree_api_base_url(network)
        api_key = NetworkConfig.get_gasfree_api_key(network)
        api_secret = NetworkConfig.get_gasfree_api_secret(network)
        api_client = GasFreeAPIClient(api_base_url, api_key, api_secret)

        try:
            # Submit
            trace_id = await self._settle_payment_only(permit, signature, requirements)
            if not trace_id:
                return SettleResponse(
                    success=False,
                    errorReason="api_no_response",
                    network=requirements.network,
                )

            self._logger.info(f"GasFree submitted. Trace ID: {trace_id}. Polling for result...")

            # Wait for success (like wait_for_transaction_receipt)
            result_data = await api_client.wait_for_success(trace_id)

            self._logger.info(f"GasFree settlement successful. State: {result_data.get('state')}")
            return SettleResponse(
                success=True,
                transaction=trace_id,
                network=requirements.network,
            )
        except Exception as e:
            self._logger.error(f"GasFree settlement or wait failed: {e}")
            return SettleResponse(
                success=False,
                errorReason=str(e),
                network=requirements.network,
            )

    async def _settle_payment_only(
        self,
        permit: PaymentPermit,
        signature: str,
        requirements: PaymentRequirements,
    ) -> Optional[str]:
        """Internal helper for API submission"""
        network = requirements.network
        controller = NetworkConfig.get_gasfree_controller_address(network)
        chain_id = NetworkConfig.get_chain_id(network)
        api_base_url = NetworkConfig.get_gasfree_api_base_url(network)
        api_key = NetworkConfig.get_gasfree_api_key(network)
        api_secret = NetworkConfig.get_gasfree_api_secret(network)
        api_client = GasFreeAPIClient(api_base_url, api_key, api_secret)

        # Build the message for the API.
        # Note: GasFree API requires TRON Base58 addresses in the payload body,
        # while the signature (TIP-712) uses EVM hex format.
        message = {
            "token": permit.payment.pay_token,
            "serviceProvider": permit.fee.fee_to,
            "user": permit.buyer,
            "receiver": permit.payment.pay_to,
            "value": str(permit.payment.pay_amount),
            "maxFee": str(permit.fee.fee_amount),
            "deadline": str(permit.meta.valid_before),
            "version": 1,
            "nonce": int(permit.meta.nonce),
        }

        domain = get_gasfree_domain(chain_id, controller)

        self._logger.debug("Settling GasFree via Official HTTP API Proxy...")

        return await api_client.submit(domain=domain, message=message, signature=signature)
