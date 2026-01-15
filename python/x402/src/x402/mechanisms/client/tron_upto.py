"""
UptoTronClientMechanism - "upto" 支付方案的 TRON 客户端机制
"""

import logging
from typing import Any, TYPE_CHECKING
import base58

from x402.abi import get_payment_permit_eip712_types
from x402.mechanisms.client.base import ClientMechanism
from x402.types import (
    PaymentPayload,
    PaymentPayloadData,
    PaymentPermit,
    PaymentRequirements,
    PermitMeta,
    Payment,
    Fee,
    Delivery,
    ResourceInfo,
)

if TYPE_CHECKING:
    from x402.signers.client import ClientSigner

logger = logging.getLogger(__name__)

# Kind mapping for EIP-712
KIND_MAP = {
    "PAYMENT_ONLY": 0,
    "PAYMENT_AND_DELIVERY": 1,
}


def normalize_tron_address(tron_addr: str) -> str:
    """Normalize TRON address, converting invalid placeholders to valid zero address"""
    # Handle zero address placeholder (T0000... or similar)
    if tron_addr.startswith("T") and all(c in "0T" for c in tron_addr):
        # Return valid TRON zero address with correct checksum
        return "T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuWwb"
    return tron_addr


def tron_address_to_evm(tron_addr: str) -> str:
    """Convert TRON Base58Check address to EVM hex format (0x...)"""
    # Normalize address first
    tron_addr = normalize_tron_address(tron_addr)
    
    # If already in EVM format, return as-is
    if tron_addr.startswith("0x"):
        return tron_addr
    
    # If it's a hex string (with or without 0x prefix), normalize to 0x format
    # Check if it looks like a hex address (40 or 42 chars of hex digits, possibly with 0x or 41 prefix)
    hex_str = tron_addr
    if tron_addr.startswith("41"):
        # Remove TRON version prefix
        hex_str = tron_addr[2:]
    
    if len(hex_str) == 40 and all(c in "0123456789abcdefABCDEF" for c in hex_str):
        return "0x" + hex_str
    
    try:
        # Decode Base58Check (for TRON addresses like TLBaRhANhwgZyUk6Z1ynCn1Ld7BRH1jBjZ)
        decoded = base58.b58decode(tron_addr)
        # TRON address is 25 bytes: 1 byte version + 20 bytes address + 4 bytes checksum
        # Extract the 20-byte address (skip first byte, take next 20)
        address_bytes = decoded[1:21]
        # Convert to hex with 0x prefix
        return "0x" + address_bytes.hex()
    except Exception as e:
        logger.warning(f"Failed to convert TRON address {tron_addr}: {e}, using as-is")
        return tron_addr


class UptoTronClientMechanism(ClientMechanism):
    """"upto" 支付方案的 TRON 客户端机制"""

    def __init__(self, signer: "ClientSigner") -> None:
        self._signer = signer
        logger.info("UptoTronClientMechanism initialized")

    def scheme(self) -> str:
        return "exact"

    async def create_payment_payload(
        self,
        requirements: PaymentRequirements,
        resource: str,
        extensions: dict[str, Any] | None = None,
    ) -> PaymentPayload:
        """使用 EIP-712 签名创建支付载荷"""
        logger.info(f"Creating payment payload: network={requirements.network}, amount={requirements.amount}, asset={requirements.asset}")
        context = extensions.get("paymentPermitContext") if extensions else None
        if context is None:
            raise ValueError("paymentPermitContext is required")

        buyer_address = self._signer.get_address()
        meta = context.get("meta", {})
        delivery = context.get("delivery", {})
        logger.debug(f"Buyer address: {buyer_address}, paymentId: {meta.get('paymentId')}")

        # Use zero address in TRON format as default
        fee_to = "T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuWwb"
        fee_amount = "0"
        if requirements.extra and requirements.extra.fee:
            fee_to = requirements.extra.fee.fee_to
            fee_amount = requirements.extra.fee.fee_amount

        kind_str = meta.get("kind", "PAYMENT_ONLY")
        kind_num = KIND_MAP.get(kind_str, 0)
        
        permit = PaymentPermit(
            meta=PermitMeta(
                kind=kind_str,
                paymentId=meta.get("paymentId", ""),
                nonce=str(meta.get("nonce", "0")),
                validAfter=meta.get("validAfter", 0),
                validBefore=meta.get("validBefore", 0),
            ),
            buyer=buyer_address,
            caller=fee_to,
            payment=Payment(
                payToken=normalize_tron_address(requirements.asset),
                maxPayAmount=requirements.amount,
                payTo=normalize_tron_address(requirements.pay_to),
            ),
            fee=Fee(
                feeTo=fee_to,
                feeAmount=fee_amount,
            ),
            delivery=Delivery(
                receiveToken=normalize_tron_address(delivery.get("receiveToken", "T0000000000000000000000000000000")),
                miniReceiveAmount=str(delivery.get("miniReceiveAmount", "0")),
                tokenId=str(delivery.get("tokenId", "0")),
            ),
        )

        total_amount = int(permit.payment.max_pay_amount) + int(permit.fee.fee_amount)
        logger.info(f"Total amount (payment + fee): {total_amount} = {permit.payment.max_pay_amount} + {permit.fee.fee_amount}")
        
        await self._signer.ensure_allowance(
            permit.payment.pay_token,
            total_amount,
            requirements.network,
        )

        logger.info("Signing payment permit with EIP-712...")
        # Convert permit to dict and replace kind string with numeric value for EIP-712
        message = permit.model_dump(by_alias=True)
        message["meta"]["kind"] = kind_num
        
        # Convert TRON addresses to EVM format for EIP-712 compatibility
        message["buyer"] = tron_address_to_evm(message["buyer"])
        message["caller"] = tron_address_to_evm(message["caller"])
        message["payment"]["payToken"] = tron_address_to_evm(message["payment"]["payToken"])
        message["payment"]["payTo"] = tron_address_to_evm(message["payment"]["payTo"])
        message["fee"]["feeTo"] = tron_address_to_evm(message["fee"]["feeTo"])
        message["delivery"]["receiveToken"] = tron_address_to_evm(message["delivery"]["receiveToken"])
        
        # Get payment permit contract address and chain ID for domain
        from x402.config import NetworkConfig
        permit_address = NetworkConfig.get_payment_permit_address(requirements.network)
        permit_address_evm = tron_address_to_evm(permit_address)
        chain_id = NetworkConfig.get_chain_id(requirements.network)
        
        # Note: Contract EIP712Domain only has (name, chainId, verifyingContract) - NO version!
        signature = await self._signer.sign_typed_data(
            domain={
                "name": "PaymentPermit",
                "chainId": chain_id,
                "verifyingContract": permit_address_evm,
            },
            types=get_payment_permit_eip712_types(),
            message=message,
        )

        logger.info(f"Payment payload created successfully: signature={signature[:10]}...")
        return PaymentPayload(
            x402Version=2,
            resource=ResourceInfo(url=resource),
            accepted=requirements,
            payload=PaymentPayloadData(
                signature=signature,
                paymentPermit=permit,
            ),
            extensions={},
        )
