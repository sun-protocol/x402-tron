"""
Transaction Verification Utilities

Provides generic functionality to verify blockchain transaction results,
ensuring contract transfers and deliveries match expected parameters.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Protocol

from x402.types import PaymentPayload, PaymentRequirements


@dataclass
class TransferEvent:
    """Represents a token transfer event from a transaction"""
    
    token: str          # Token contract address
    from_addr: str      # Sender address
    to_addr: str        # Recipient address
    amount: int         # Transfer amount


@dataclass
class TransactionVerificationResult:
    """Result of transaction verification"""
    
    success: bool
    tx_hash: str
    block_number: str | None = None
    error_reason: str | None = None
    transfers: list[TransferEvent] | None = None
    
    # Detailed verification flags
    status_verified: bool = False      # Transaction executed successfully
    payment_verified: bool = False     # Payment amount/recipient verified
    fee_verified: bool = False         # Fee payment verified
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "success": self.success,
            "txHash": self.tx_hash,
            "blockNumber": self.block_number,
            "errorReason": self.error_reason,
            "statusVerified": self.status_verified,
            "paymentVerified": self.payment_verified,
            "feeVerified": self.fee_verified,
        }


class TransactionVerifier(Protocol):
    """Protocol for transaction verification implementations"""
    
    async def verify_transaction(
        self,
        tx_hash: str,
        payload: PaymentPayload,
        requirements: PaymentRequirements,
    ) -> TransactionVerificationResult:
        """Verify a transaction matches expected payment parameters"""
        ...

    async def get_transaction_transfers(
        self,
        tx_hash: str,
        token_address: str,
    ) -> list[TransferEvent]:
        """Get token transfer events from a transaction"""
        ...


class BaseTransactionVerifier(ABC):
    """Base class for transaction verification implementations"""
    
    def __init__(self) -> None:
        self._logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    async def get_transaction_info(self, tx_hash: str) -> dict[str, Any]:
        """Get transaction information from blockchain"""
        pass
    
    @abstractmethod
    async def get_transaction_transfers(
        self,
        tx_hash: str,
        token_address: str,
    ) -> list[TransferEvent]:
        """Get token transfer events from a transaction"""
        pass
    
    @abstractmethod
    def normalize_address(self, address: str) -> str:
        """Normalize address to standard format for comparison"""
        pass
    
    async def verify_transaction(
        self,
        tx_hash: str,
        payload: PaymentPayload,
        requirements: PaymentRequirements,
    ) -> TransactionVerificationResult:
        """
        Verify a transaction matches expected payment parameters.
        
        This method checks:
        1. Transaction status (success/failed)
        2. Payment transfer (correct amount to payTo address)
        3. Fee transfer (correct fee amount to feeTo address)
        
        Args:
            tx_hash: Transaction hash to verify
            payload: Original payment payload
            requirements: Payment requirements
            
        Returns:
            TransactionVerificationResult with detailed verification status
        """
        permit = payload.payload.payment_permit
        
        self._logger.info(f"=" * 60)
        self._logger.info(f"Verifying transaction: {tx_hash}")
        
        # Log expected transfers from payload and requirements
        expected_from = self.normalize_address(permit.buyer)
        expected_pay_to = self.normalize_address(requirements.pay_to)
        expected_amount = int(requirements.amount)
        token_address = requirements.asset
        fee_amount = 0
        expected_fee_to = None
        
        if requirements.extra and requirements.extra.fee:
            fee_amount = int(requirements.extra.fee.fee_amount)
            expected_fee_to = self.normalize_address(requirements.extra.fee.fee_to)
        
        self._logger.info(f"[EXPECTED] Payment: {expected_from} → {expected_pay_to} | {expected_amount} {token_address}")
        if fee_amount > 0 and expected_fee_to:
            self._logger.info(f"[EXPECTED] Fee: {expected_from} → {expected_fee_to} | {fee_amount} {token_address}")
        else:
            self._logger.info(f"[EXPECTED] Fee: None")
        
        try:
            # Step 1: Get transaction info and verify status
            tx_info = await self.get_transaction_info(tx_hash)
            
            status = tx_info.get("status", "").lower()
            if status == "failed" or status == "0" or status == 0:
                self._logger.error(f"[FAILED] Transaction failed on-chain: {tx_hash}")
                self._logger.info(f"=" * 60)
                return TransactionVerificationResult(
                    success=False,
                    tx_hash=tx_hash,
                    block_number=tx_info.get("blockNumber"),
                    error_reason="transaction_failed_on_chain",
                    status_verified=False,
                )
            
            self._logger.info(f"[OK] Transaction status: {status}")
            
            # Step 2: Get and verify transfer events
            transfers = await self.get_transaction_transfers(tx_hash, token_address)
            
            if not transfers:
                self._logger.warning(f"[FAILED] No transfer events found for tx: {tx_hash}")
                self._logger.info(f"=" * 60)
                return TransactionVerificationResult(
                    success=False,
                    tx_hash=tx_hash,
                    block_number=tx_info.get("blockNumber"),
                    error_reason="no_transfer_events",
                    status_verified=True,
                    transfers=[],
                )
            
            # Log actual transfers (one line per transfer)
            self._logger.info(f"[ACTUAL] Found {len(transfers)} transfer(s):")
            for i, transfer in enumerate(transfers, 1):
                self._logger.info(f"[ACTUAL] #{i}: {transfer.from_addr} → {transfer.to_addr} | {transfer.amount} {transfer.token}")
            
            # Step 3: Verify payment transfer
            payment_verified = False
            fee_verified = fee_amount == 0  # If no fee, consider it verified
            
            for transfer in transfers:
                normalized_to = self.normalize_address(transfer.to_addr)
                
                # Check payment transfer
                if normalized_to == expected_pay_to:
                    if transfer.amount >= expected_amount:
                        payment_verified = True
                        self._logger.info(f"[COMPARE] ✓ Payment matched: {transfer.from_addr} → {transfer.to_addr} | {transfer.amount} (expected: {expected_amount})")
                    else:
                        self._logger.warning(f"[COMPARE] ✗ Payment MISMATCH: got {transfer.amount}, expected {expected_amount}")
                
                # Check fee transfer
                if expected_fee_to and normalized_to == expected_fee_to:
                    if transfer.amount >= fee_amount:
                        fee_verified = True
                        self._logger.info(f"[COMPARE] ✓ Fee matched: {transfer.from_addr} → {transfer.to_addr} | {transfer.amount} (expected: {fee_amount})")
                    else:
                        self._logger.warning(f"[COMPARE] ✗ Fee MISMATCH: got {transfer.amount}, expected {fee_amount}")
            
            if not payment_verified:
                self._logger.error(f"[COMPARE] ✗ Payment NOT FOUND: expected {expected_from} → {expected_pay_to} | {expected_amount}")
                self._logger.info(f"=" * 60)
                return TransactionVerificationResult(
                    success=False,
                    tx_hash=tx_hash,
                    block_number=tx_info.get("blockNumber"),
                    error_reason="payment_not_verified",
                    status_verified=True,
                    payment_verified=False,
                    fee_verified=fee_verified,
                    transfers=transfers,
                )
            
            if not fee_verified:
                self._logger.error(f"[COMPARE] ✗ Fee NOT FOUND: expected {expected_from} → {expected_fee_to} | {fee_amount}")
                self._logger.info(f"=" * 60)
                return TransactionVerificationResult(
                    success=False,
                    tx_hash=tx_hash,
                    block_number=tx_info.get("blockNumber"),
                    error_reason="fee_not_verified",
                    status_verified=True,
                    payment_verified=True,
                    fee_verified=False,
                    transfers=transfers,
                )
            
            self._logger.info(f"[SUCCESS] Transaction verification passed: {tx_hash}")
            self._logger.info(f"=" * 60)
            return TransactionVerificationResult(
                success=True,
                tx_hash=tx_hash,
                block_number=tx_info.get("blockNumber"),
                status_verified=True,
                payment_verified=True,
                fee_verified=True,
                transfers=transfers,
            )
            
        except Exception as e:
            self._logger.error(f"Transaction verification error: {e}", exc_info=True)
            return TransactionVerificationResult(
                success=False,
                tx_hash=tx_hash,
                error_reason=f"verification_error: {str(e)}",
            )


def get_verifier_for_network(network: str, rpc_url: str | None = None) -> BaseTransactionVerifier:
    """
    Factory function to get appropriate transaction verifier for a network.
    
    Automatically detects network type (TRON or EVM) and returns the appropriate verifier.
    
    Args:
        network: Network identifier (e.g., "tron:nile", "eip155:8453")
        rpc_url: Optional custom RPC URL for EVM networks
        
    Returns:
        Transaction verifier instance
        
    Examples:
        >>> verifier = get_verifier_for_network("tron:nile")
        >>> verifier = get_verifier_for_network("eip155:8453")  # Base Mainnet
        >>> verifier = get_verifier_for_network("eip155:1", rpc_url="https://my-node.com")
    """
    if network.startswith("tron:"):
        from x402.utils.tron_verification import TronTransactionVerifier
        tron_network = network.split(":")[1] if ":" in network else "nile"
        return TronTransactionVerifier(network=tron_network)
    
    if network.startswith("eip155:"):
        from x402.utils.evm_verification import EvmTransactionVerifier
        return EvmTransactionVerifier(network=network, rpc_url=rpc_url)
    
    raise ValueError(f"No transaction verifier available for network: {network}")
