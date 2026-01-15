"""
EvmFacilitatorSigner - EVM facilitator 签名器实现
"""

import json
from typing import Any

from x402.abi import PAYMENT_PERMIT_PRIMARY_TYPE, EIP712_DOMAIN_TYPE
from x402.signers.facilitator.base import FacilitatorSigner


class EvmFacilitatorSigner(FacilitatorSigner):
    """EVM facilitator 签名器实现"""

    def __init__(self, private_key: str, rpc_url: str | None = None) -> None:
        clean_key = private_key if private_key.startswith("0x") else f"0x{private_key}"
        self._private_key = clean_key
        self._address = self._derive_address(clean_key)
        self._rpc_url = rpc_url
        self._web3: Any = None

    @classmethod
    def from_private_key(cls, private_key: str, rpc_url: str | None = None) -> "EvmFacilitatorSigner":
        """从私钥创建签名器"""
        return cls(private_key, rpc_url)

    def _ensure_web3(self) -> Any:
        """延迟初始化 web3 客户端"""
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

    async def verify_typed_data(
        self,
        address: str,
        domain: dict[str, Any],
        types: dict[str, Any],
        message: dict[str, Any],
        signature: str,
    ) -> bool:
        """验证 EIP-712 签名"""
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
            
            sig_bytes = bytes.fromhex(signature[2:] if signature.startswith("0x") else signature)
            recovered = Account.recover_message(signable, signature=sig_bytes)

            return recovered.lower() == address.lower()
        except Exception:
            return False

    async def write_contract(
        self,
        contract_address: str,
        abi: str,
        method: str,
        args: list[Any],
    ) -> str | None:
        """在 EVM 上执行合约交易"""
        web3 = self._ensure_web3()
        if web3 is None:
            raise RuntimeError("web3 instance required for contract calls")

        try:
            from eth_account import Account

            abi_list = json.loads(abi) if isinstance(abi, str) else abi
            contract = web3.eth.contract(
                address=web3.to_checksum_address(contract_address),
                abi=abi_list,
            )

            func = getattr(contract.functions, method)
            tx = func(*args).build_transaction({
                "from": self._address,
                "nonce": web3.eth.get_transaction_count(self._address),
                "gas": 500000,
            })

            account = Account.from_key(self._private_key)
            signed = account.sign_transaction(tx)
            tx_hash = web3.eth.send_raw_transaction(signed.rawTransaction)

            return tx_hash.hex()
        except Exception as e:
            print(f"Contract call failed: {e}")
            return None

    async def wait_for_transaction_receipt(
        self,
        tx_hash: str,
        timeout: int = 120,
    ) -> dict[str, Any]:
        """等待 EVM 交易确认"""
        web3 = self._ensure_web3()
        if web3 is None:
            raise RuntimeError("web3 instance required")

        receipt = web3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout)

        return {
            "hash": tx_hash,
            "blockNumber": str(receipt.blockNumber),
            "status": "confirmed" if receipt.status == 1 else "failed",
        }
