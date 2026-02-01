"""
EVM Transaction Verification

Provides EVM-compatible chain transaction verification functionality.
"""

import logging
from typing import Any

from x402.utils.tx_verification import BaseTransactionVerifier, TransferEvent


class EvmTransactionVerifier(BaseTransactionVerifier):
    """EVM-compatible chain transaction verification implementation"""
    
    # Common EVM RPC endpoints
    RPC_ENDPOINTS: dict[str, str] = {
        "eip155:1": "https://eth.llamarpc.com",           # Ethereum Mainnet
        "eip155:8453": "https://mainnet.base.org",        # Base Mainnet
        "eip155:84532": "https://sepolia.base.org",       # Base Sepolia
        "eip155:11155111": "https://rpc.sepolia.org",     # Sepolia
        "eip155:137": "https://polygon-rpc.com",          # Polygon
        "eip155:42161": "https://arb1.arbitrum.io/rpc",   # Arbitrum
        "eip155:10": "https://mainnet.optimism.io",       # Optimism
    }
    
    def __init__(self, network: str, rpc_url: str | None = None) -> None:
        super().__init__()
        self._network = network
        self._rpc_url = rpc_url or self.RPC_ENDPOINTS.get(network)
        self._web3: Any = None
    
    def _ensure_web3(self) -> Any:
        """Lazy initialize web3 client"""
        if self._web3 is None:
            try:
                from web3 import Web3
                if not self._rpc_url:
                    raise ValueError(f"No RPC endpoint configured for network: {self._network}")
                self._web3 = Web3(Web3.HTTPProvider(self._rpc_url))
            except ImportError:
                raise RuntimeError("web3 is required for EVM transaction verification")
        return self._web3
    
    def normalize_address(self, address: str) -> str:
        """Normalize address to checksum format"""
        try:
            from web3 import Web3
            
            if address.startswith("0x") and len(address) == 42:
                return Web3.to_checksum_address(address)
            
            return address
        except Exception:
            return address
    
    async def get_transaction_info(self, tx_hash: str) -> dict[str, Any]:
        """Get EVM transaction information"""
        w3 = self._ensure_web3()
        
        try:
            # Get transaction receipt
            receipt = w3.eth.get_transaction_receipt(tx_hash)
            if receipt:
                # EVM uses status: 1 = success, 0 = failed
                status = "confirmed" if receipt.get("status") == 1 else "failed"
                return {
                    "hash": tx_hash,
                    "blockNumber": str(receipt.get("blockNumber", "")),
                    "status": status,
                    "logs": receipt.get("logs", []),
                    "gasUsed": receipt.get("gasUsed"),
                }
            return {"hash": tx_hash, "status": "pending"}
        except Exception as e:
            self._logger.error(f"Failed to get transaction info: {e}")
            raise
    
    async def get_transaction_transfers(
        self,
        tx_hash: str,
        token_address: str,
    ) -> list[TransferEvent]:
        """
        Get ERC20 token transfer events from an EVM transaction.
        
        Parses the transaction logs for Transfer(address,address,uint256) events.
        """
        w3 = self._ensure_web3()
        transfers: list[TransferEvent] = []
        
        try:
            receipt = w3.eth.get_transaction_receipt(tx_hash)
            if not receipt:
                return transfers
            
            logs = receipt.get("logs", [])
            
            # ERC20 Transfer event topic
            # keccak256("Transfer(address,address,uint256)")
            transfer_topic = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
            
            normalized_token = self.normalize_address(token_address).lower()
            
            for log in logs:
                log_address = log.get("address", "")
                topics = log.get("topics", [])
                data = log.get("data", b"")
                
                # Check if this is a Transfer event
                if not topics or topics[0].hex() != transfer_topic[2:]:
                    continue
                
                # Check if from expected token
                if log_address.lower() != normalized_token:
                    continue
                
                if len(topics) < 3:
                    continue
                
                # Parse Transfer event
                # topics[1] = from address (padded to 32 bytes)
                # topics[2] = to address (padded to 32 bytes)
                # data = amount (uint256)
                from_addr = self._parse_address_from_topic(topics[1])
                to_addr = self._parse_address_from_topic(topics[2])
                
                # Parse amount from data (handles both bytes and hex string)
                if isinstance(data, bytes):
                    amount = int.from_bytes(data, 'big') if data else 0
                else:
                    amount = int(data, 16) if data else 0
                
                transfers.append(TransferEvent(
                    token=self.normalize_address(log_address),
                    from_addr=from_addr,
                    to_addr=to_addr,
                    amount=amount,
                ))
                
                self._logger.debug(
                    f"Found transfer: {amount} from {from_addr} to {to_addr}"
                )
            
            return transfers
            
        except Exception as e:
            self._logger.error(f"Failed to parse transfer events: {e}", exc_info=True)
            return transfers
    
    def _parse_address_from_topic(self, topic: Any) -> str:
        """Parse address from 32-byte padded topic"""
        try:
            from web3 import Web3
            
            # Handle bytes or HexBytes
            if hasattr(topic, 'hex'):
                topic_hex = topic.hex()
            elif isinstance(topic, bytes):
                topic_hex = topic.hex()
            else:
                topic_hex = str(topic)
            
            # Remove 0x prefix if present
            if topic_hex.startswith("0x"):
                topic_hex = topic_hex[2:]
            
            # Address is last 40 characters (20 bytes)
            if len(topic_hex) >= 40:
                addr_hex = "0x" + topic_hex[-40:]
                return Web3.to_checksum_address(addr_hex)
            return topic_hex
        except Exception:
            return str(topic)
