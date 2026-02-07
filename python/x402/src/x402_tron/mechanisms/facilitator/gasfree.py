"""
GasFreeFacilitatorMechanism - GasFree payment scheme facilitator mechanism for TRON.
"""

import logging
from typing import Any, Optional

from x402_tron.abi import get_abi_json
from x402_tron.address import AddressConverter, TronAddressConverter
from x402_tron.config import NetworkConfig
from x402_tron.mechanisms.facilitator.base_exact import BaseExactFacilitatorMechanism
from x402_tron.types import PaymentPermit, PaymentRequirements
from x402_tron.utils.gasfree import (
    GASFREE_PERMIT_TRANSFER_TYPES,
    GasFreeAPIClient,
    get_gasfree_domain,
)


# GasFreeController ABI (Subset for settlement)
GASFREE_CONTROLLER_ABI = [
    {
        "inputs": [
            {
                "components": [
                    {"internalType": "address", "name": "token", "type": "address"},
                    {"internalType": "address", "name": "serviceProvider", "type": "address"},
                    {"internalType": "address", "name": "user", "type": "address"},
                    {"internalType": "address", "name": "receiver", "type": "address"},
                    {"internalType": "uint256", "name": "value", "type": "uint256"},
                    {"internalType": "uint256", "name": "maxFee", "type": "uint256"},
                    {"internalType": "uint256", "name": "deadline", "type": "uint256"},
                    {"internalType": "uint256", "name": "version", "type": "uint256"},
                    {"internalType": "uint256", "name": "nonce", "type": "uint256"},
                ],
                "internalType": "struct GasFreeController.PermitTransfer",
                "name": "permit",
                "type": "tuple",
            },
            {"internalType": "bytes", "name": "sig", "type": "bytes"},
        ],
        "name": "transferFrom",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    }
]


class GasFreeFacilitatorMechanism(BaseExactFacilitatorMechanism):
    """GasFree facilitator mechanism for TRON"""

    def __init__(self, signer: Any) -> None:
        super().__init__(signer)
        self._api_client = GasFreeAPIClient()

    def _get_address_converter(self) -> AddressConverter:
        return TronAddressConverter()

    def scheme(self) -> str:
        return "gasfree_exact"

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
        controller = NetworkConfig.get_gasfree_controller_address(requirements.network)
        chain_id = NetworkConfig.get_chain_id(requirements.network)
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

        self._logger.info(f"Settling GasFree via Official HTTP API...")

        try:
            tx_hash = await self._api_client.submit(
                domain=domain, message=message, signature=signature
            )
            return tx_hash
        except Exception as e:
            self._logger.warning(
                f"Official API submission failed: {e}. Falling back to direct contract call..."
            )
            # Fallback to direct contract call if API fails
            permit_tuple = {
                "token": message["token"],
                "serviceProvider": message["serviceProvider"],
                "user": message["user"],
                "receiver": message["receiver"],
                "value": int(message["value"]),
                "maxFee": int(message["maxFee"]),
                "deadline": int(message["deadline"]),
                "version": 1,
                "nonce": int(message["nonce"]),
            }
            sig_bytes = bytes.fromhex(signature[2:] if signature.startswith("0x") else signature)

            return await self._signer.write_contract(
                contract_address=controller,
                abi=get_abi_json(GASFREE_CONTROLLER_ABI),
                method="transferFrom",
                args=[permit_tuple, sig_bytes],
            )
