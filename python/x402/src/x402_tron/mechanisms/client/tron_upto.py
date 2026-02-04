"""
UptoTronClientMechanism - "upto" 支付方案的 TRON 客户端机制
"""

from x402_tron.address import AddressConverter, TronAddressConverter
from x402_tron.mechanisms.client.base_upto import BaseUptoClientMechanism


class UptoTronClientMechanism(BaseUptoClientMechanism):
    """upto 支付方案的 TRON 客户端机制"""

    def _get_address_converter(self) -> AddressConverter:
        return TronAddressConverter()
