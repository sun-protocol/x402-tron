"""
UptoTronFacilitatorMechanism - "upto" 支付方案的 TRON facilitator 机制
"""

from typing import Any

from x402.abi import PAYMENT_PERMIT_ABI, get_abi_json, get_payment_permit_eip712_types
from x402.address import AddressConverter, TronAddressConverter
from x402.config import NetworkConfig
from x402.mechanisms.facilitator.base_upto import BaseUptoFacilitatorMechanism
from x402.types import PaymentPermit, PaymentRequirements, KIND_MAP


class UptoTronFacilitatorMechanism(BaseUptoFacilitatorMechanism):
    """upto 支付方案的 TRON facilitator 机制"""

    def _get_address_converter(self) -> AddressConverter:
        return TronAddressConverter()

    async def _verify_signature(
        self,
        permit: PaymentPermit,
        signature: str,
        network: str,
    ) -> bool:
        """Verify EIP-712 signature with TronWeb format (hex string for paymentId)"""
        permit_address = NetworkConfig.get_payment_permit_address(network)
        chain_id = NetworkConfig.get_chain_id(network)
        converter = self._address_converter

        # Convert permit to EIP-712 message format WITHOUT converting paymentId to bytes
        # TronWeb signs with hex strings for bytes16 fields
        message = permit.model_dump(by_alias=True)
        
        # Convert kind string to numeric value
        message["meta"]["kind"] = KIND_MAP.get(message["meta"]["kind"], 0)
        
        # Convert string values to integers for EIP-712 compatibility
        message["meta"]["nonce"] = int(message["meta"]["nonce"])
        message["payment"]["maxPayAmount"] = int(message["payment"]["maxPayAmount"])
        message["fee"]["feeAmount"] = int(message["fee"]["feeAmount"])
        message["delivery"]["miniReceiveAmount"] = int(message["delivery"]["miniReceiveAmount"])
        message["delivery"]["tokenId"] = int(message["delivery"]["tokenId"])
        
        # Keep paymentId as hex string (TronWeb format) - do NOT convert to bytes
        # message["meta"]["paymentId"] remains as "0x..." string
        
        # Convert addresses to EVM format
        message = converter.convert_message_addresses(message)

        # Debug logging
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[VERIFY TRON] Domain: name=PaymentPermit, chainId={chain_id}, verifyingContract={converter.to_evm_format(permit_address)}")
        logger.info(f"[VERIFY TRON] Message: {message}")
        logger.info(f"[VERIFY TRON] Signature: {signature}")
        logger.info(f"[VERIFY TRON] Buyer address: {permit.buyer}")

        return await self._signer.verify_typed_data(
            address=permit.buyer,
            domain={
                "name": "PaymentPermit",
                "chainId": chain_id,
                "verifyingContract": converter.to_evm_format(permit_address),
            },
            types=get_payment_permit_eip712_types(),
            message=message,
            signature=signature,
        )

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

