"""
EvmClientSigner - EVM 客户端签名器实现
"""

from typing import Any

from x402.abi import ERC20_ABI, PAYMENT_PERMIT_PRIMARY_TYPE, EIP712_DOMAIN_TYPE
from x402.signers.client.base import ClientSigner


class EvmClientSigner(ClientSigner):
    """EVM 客户端签名器实现"""

    def __init__(self, private_key: str, rpc_url: str | None = None) -> None:
        clean_key = private_key if private_key.startswith("0x") else f"0x{private_key}"
        self._private_key = clean_key
        self._address = self._derive_address(clean_key)
        self._rpc_url = rpc_url
        self._web3: Any = None

    @classmethod
    def from_private_key(cls, private_key: str, rpc_url: str | None = None) -> "EvmClientSigner":
        """从私钥创建签名器

        Args:
            private_key: EVM 私钥（十六进制字符串）
            rpc_url: 可选的 RPC 端点 URL，用于延迟初始化 web3

        Returns:
            EvmClientSigner 实例
        """
        return cls(private_key, rpc_url)

    def _ensure_web3(self) -> Any:
        """延迟初始化 web3 客户端

        Returns:
            web3.Web3 实例或 None
        """
        if self._web3 is None and self._rpc_url:
            try:
                from web3 import Web3
                self._web3 = Web3(Web3.HTTPProvider(self._rpc_url))
            except ImportError:
                pass
        return self._web3

    @staticmethod
    def _derive_address(private_key: str) -> str:
        """从私钥派生 EVM 地址"""
        try:
            from eth_account import Account
            account = Account.from_key(private_key)
            return account.address
        except ImportError:
            return f"0x{private_key[2:42]}"

    def get_address(self) -> str:
        return self._address

    async def sign_message(self, message: bytes) -> str:
        """使用 ECDSA 签名原始消息"""
        try:
            from eth_account import Account
            from eth_account.messages import encode_defunct

            signable = encode_defunct(primitive=message)
            signed = Account.sign_message(signable, self._private_key)
            return signed.signature.hex()
        except ImportError:
            raise RuntimeError("eth_account is required for signing")

    async def sign_typed_data(
        self,
        domain: dict[str, Any],
        types: dict[str, Any],
        message: dict[str, Any],
    ) -> str:
        """签名 EIP-712 类型化数据"""
        try:
            from eth_account import Account
            from eth_account.messages import encode_typed_data

            # Note: PaymentPermit contract uses EIP712Domain WITHOUT version field
            # Contract: keccak256("EIP712Domain(string name,uint256 chainId,address verifyingContract)")
            full_types = {
                "EIP712Domain": EIP712_DOMAIN_TYPE,
                **types,
            }

            typed_data = {
                "types": full_types,
                "primaryType": PAYMENT_PERMIT_PRIMARY_TYPE,
                "domain": domain,
                "message": message,
            }

            signable = encode_typed_data(full_data=typed_data)
            signed = Account.sign_message(signable, self._private_key)
            return signed.signature.hex()
        except ImportError:
            raise RuntimeError("eth_account is required for EIP-712 signing")

    async def check_allowance(
        self,
        token: str,
        amount: int,
        network: str,
    ) -> int:
        """Check token allowance on EVM"""
        web3 = self._ensure_web3()
        if web3 is None:
            return 0

        try:
            contract = web3.eth.contract(
                address=web3.to_checksum_address(token),
                abi=ERC20_ABI,
            )
            allowance = contract.functions.allowance(
                self._address,
                self._get_spender_address(network),
            ).call()
            return int(allowance)
        except Exception:
            return 0

    async def ensure_allowance(
        self,
        token: str,
        amount: int,
        network: str,
        mode: str = "auto",
    ) -> bool:
        """Ensure sufficient allowance"""
        if mode == "skip":
            return True

        current = await self.check_allowance(token, amount, network)
        if current >= amount:
            return True

        if mode == "interactive":
            raise NotImplementedError("Interactive approval not implemented")

        web3 = self._ensure_web3()
        if web3 is None:
            raise RuntimeError("web3 instance required for approval")

        try:
            contract = web3.eth.contract(
                address=web3.to_checksum_address(token),
                abi=ERC20_ABI,
            )

            from eth_account import Account
            account = Account.from_key(self._private_key)

            tx = contract.functions.approve(
                self._get_spender_address(network),
                amount,
            ).build_transaction({
                "from": self._address,
                "nonce": web3.eth.get_transaction_count(self._address),
            })

            signed = account.sign_transaction(tx)
            tx_hash = web3.eth.send_raw_transaction(signed.rawTransaction)
            receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
            return receipt.status == 1
        except Exception:
            return False

    def _get_spender_address(self, network: str) -> str:
        """Get payment permit contract address (spender)"""
        addresses = {
            "eip155:1": "0x...",
            "eip155:8453": "0x...",
            "eip155:11155111": "0x...",
        }
        return addresses.get(network, "0x0000000000000000000000000000000000000000")
