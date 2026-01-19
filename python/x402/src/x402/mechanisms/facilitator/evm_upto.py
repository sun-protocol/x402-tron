"""
UptoEvmFacilitatorMechanism - "upto" 支付方案的 EVM facilitator 机制
"""

from typing import Any

from x402.abi import PAYMENT_PERMIT_ABI, MERCHANT_ABI, get_abi_json
from x402.address import AddressConverter, EvmAddressConverter
from x402.config import NetworkConfig
from x402.mechanisms.facilitator.base_upto import BaseUptoFacilitatorMechanism
from x402.types import PaymentRequirements


class UptoEvmFacilitatorMechanism(BaseUptoFacilitatorMechanism):
    """upto 支付方案的 EVM facilitator 机制"""

    def _get_address_converter(self) -> AddressConverter:
        return EvmAddressConverter()

    async def _settle_payment_only(
        self,
        permit: Any,
        signature: str,
        requirements: PaymentRequirements,
    ) -> str | None:
        """仅支付结算（无链上交付）"""
        contract_address = NetworkConfig.get_payment_permit_address(requirements.network)
        self._logger.info(f"Calling permitTransferFrom on contract={contract_address}")

        return await self._signer.write_contract(
            contract_address=contract_address,
            abi=get_abi_json(PAYMENT_PERMIT_ABI),
            method="permitTransferFrom",
            args=[
                permit.model_dump(by_alias=True),
                permit.buyer,
                signature,
                "0x0000000000000000000000000000000000000000",
                "0x" + "00" * 32,
                "0x",
            ],
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

        return await self._signer.write_contract(
            contract_address=merchant_address,
            abi=get_abi_json(MERCHANT_ABI),
            method="settle",
            args=[permit.model_dump(by_alias=True), signature],
        )
