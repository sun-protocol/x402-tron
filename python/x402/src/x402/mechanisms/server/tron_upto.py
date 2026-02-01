"""
UptoTronServerMechanism - "upto" 支付方案的 TRON 服务器机制
"""

from x402.mechanisms.server.base_upto import BaseUptoServerMechanism


class UptoTronServerMechanism(BaseUptoServerMechanism):
    """upto 支付方案的 TRON 服务器机制"""

    def _get_network_prefix(self) -> str:
        return "tron:"

    def _validate_address_format(self, address: str) -> bool:
        """验证 TRON 地址格式 (以 T 开头)"""
        return address.startswith("T")
