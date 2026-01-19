"""
UptoEvmClientMechanism - "upto" 支付方案的 EVM 客户端机制
"""

from x402.address import AddressConverter, EvmAddressConverter
from x402.mechanisms.client.base_upto import BaseUptoClientMechanism


class UptoEvmClientMechanism(BaseUptoClientMechanism):
    """upto 支付方案的 EVM 客户端机制"""

    def _get_address_converter(self) -> AddressConverter:
        return EvmAddressConverter()
