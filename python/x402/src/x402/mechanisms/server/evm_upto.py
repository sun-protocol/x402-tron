"""
UptoEvmServerMechanism - "upto" 支付方案的 EVM 服务器机制
"""

from x402.mechanisms.server.base_upto import BaseUptoServerMechanism


class UptoEvmServerMechanism(BaseUptoServerMechanism):
    """upto 支付方案的 EVM 服务器机制"""

    def _get_network_prefix(self) -> str:
        return "eip155:"

    def _validate_address_format(self, address: str) -> bool:
        """验证 EVM 地址格式 (0x + 40 hex chars)"""
        return address.startswith("0x") and len(address) == 42
