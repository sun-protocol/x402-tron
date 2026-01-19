"""
UptoTronFacilitatorMechanism - "upto" 支付方案的 TRON facilitator 机制
"""

from typing import Any

from x402.abi import PAYMENT_PERMIT_ABI, MERCHANT_ABI, get_abi_json
from x402.address import AddressConverter, TronAddressConverter
from x402.config import NetworkConfig
from x402.mechanisms.facilitator.base_upto import BaseUptoFacilitatorMechanism
from x402.types import PaymentRequirements


class UptoTronFacilitatorMechanism(BaseUptoFacilitatorMechanism):
    """upto 支付方案的 TRON facilitator 机制"""

    def _get_address_converter(self) -> AddressConverter:
        return TronAddressConverter()

    async def _settle_payment_only(
        self,
        permit: Any,
        signature: str,
        requirements: PaymentRequirements,
    ) -> str | None:
        """仅支付结算（无链上交付）"""
        contract_address = NetworkConfig.get_payment_permit_address(requirements.network)
        self._logger.info(f"Calling permitTransferFrom on contract={contract_address}")

        permit_tuple = self._build_permit_tuple(permit)
        sig_bytes = bytes.fromhex(signature[2:] if signature.startswith("0x") else signature)
        transfer_details = (int(permit.payment.max_pay_amount),)
        buyer = self._address_converter.normalize(permit.buyer)

        args = [permit_tuple, transfer_details, buyer, sig_bytes]
        self._logger.info(f"Calling permitTransferFrom with {len(args)} arguments (PAYMENT_ONLY mode)")

        return await self._signer.write_contract(
            contract_address=contract_address,
            abi=get_abi_json(PAYMENT_PERMIT_ABI),
            method="permitTransferFrom",
            args=args,
        )

    async def _settle_with_delivery(
        self,
        permit: Any,
        signature: str,
        requirements: PaymentRequirements,
    ) -> str | None:
        """带链上交付的结算"""
        merchant_address = requirements.pay_to
        self._logger.info(f"Calling settle on merchant contract={merchant_address}")

        permit_tuple = self._build_permit_tuple(permit)
        sig_bytes = bytes.fromhex(signature[2:] if signature.startswith("0x") else signature)

        return await self._signer.write_contract(
            contract_address=merchant_address,
            abi=get_abi_json(MERCHANT_ABI),
            method="settle",
            args=[permit_tuple, sig_bytes],
        )
