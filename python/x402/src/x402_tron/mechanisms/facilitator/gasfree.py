"""
GasFreeFacilitatorMechanism - GasFree payment scheme facilitator mechanism for TRON.
"""

import logging
from typing import Any, Optional

from x402_tron.address import AddressConverter, TronAddressConverter
from x402_tron.config import NetworkConfig
from x402_tron.mechanisms.facilitator.base_exact import BaseExactFacilitatorMechanism
from x402_tron.types import PaymentPermit, PaymentRequirements
from x402_tron.utils.gasfree import (
    GASFREE_PERMIT_TRANSFER_TYPES,
    GasFreeAPIClient,
    get_gasfree_domain,
)


class GasFreeFacilitatorMechanism(BaseExactFacilitatorMechanism):
    """GasFree facilitator mechanism for TRON"""

    def scheme(self) -> str:
        return "gasfree_exact"

    def _get_address_converter(self) -> AddressConverter:
        return TronAddressConverter()

    async def _verify_signature(
        self,
        permit: PaymentPermit,
        signature: str,
        network: str,
    ) -> bool:
        """Verify GasFree TIP-712 signature"""
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

        self._logger.info(f"[VERIFY GASFREE] Domain: {domain}")
        self._logger.info(f"[VERIFY GASFREE] Message: {message}")

        return await self._signer.verify_typed_data(
            address=permit.buyer,
            domain=domain,
            types=GASFREE_PERMIT_TRANSFER_TYPES,
            message=message,
            signature=signature,
        )

    async def _settle_payment_only(
        self,
        permit: PaymentPermit,
        signature: str,
        requirements: PaymentRequirements,
    ) -> Optional[str]:
        """Settle GasFree transaction via official HTTP API"""
        network = requirements.network
        controller = NetworkConfig.get_gasfree_controller_address(network)
        chain_id = NetworkConfig.get_chain_id(network)
        api_base_url = NetworkConfig.get_gasfree_api_base_url(network)
        api_key = NetworkConfig.get_gasfree_api_key(network)
        api_secret = NetworkConfig.get_gasfree_api_secret(network)
        api_client = GasFreeAPIClient(api_base_url, api_key, api_secret)
        converter = self._address_converter

        # Build the message for the API
        message = {
            "token": converter.to_evm_format(permit.payment.pay_token),
            "serviceProvider": converter.to_evm_format(permit.fee.fee_to),
            "user": converter.to_evm_format(permit.buyer),
            "receiver": converter.to_evm_format(permit.payment.pay_to),
            "value": str(permit.payment.pay_amount),
            "maxFee": str(permit.fee.fee_amount),
            "deadline": str(permit.meta.valid_before),
            "version": 1,
            "nonce": int(permit.meta.nonce),
        }

        domain = get_gasfree_domain(chain_id, controller)

        self._logger.info(f"Settling GasFree via Official HTTP API Proxy...")

        try:
            tx_hash = await api_client.submit(domain=domain, message=message, signature=signature)
            return tx_hash
        except Exception as e:
            self._logger.error(f"GasFree API submission failed: {e}")
            raise
