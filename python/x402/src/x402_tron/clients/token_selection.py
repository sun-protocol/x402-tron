"""
Token selection strategies for choosing which token to pay with.

When a server accepts multiple tokens, the client needs a strategy to pick one.
All tokens are assumed to be stablecoins, so selection normalizes raw amounts
by token decimals to compare real value (lower is better for the payer).
"""

import logging
from decimal import Decimal
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from x402_tron.tokens import TokenRegistry
from x402_tron.types import PaymentRequirements

if TYPE_CHECKING:
    from x402_tron.signers.client.base import ClientSigner

logger = logging.getLogger(__name__)


@runtime_checkable
class TokenSelectionStrategy(Protocol):
    """Strategy for selecting which payment option to use.

    Implementations receive the list of accepted payment requirements
    (already filtered to those the client has a mechanism for)
    and return the best one.
    """

    async def select(
        self,
        accepts: list[PaymentRequirements],
    ) -> PaymentRequirements:
        """Select the best payment requirement from available options.

        Args:
            accepts: Available payment requirements.

        Returns:
            The selected PaymentRequirements.

        Raises:
            ValueError: If no suitable option is found.
        """
        ...


def _get_decimals(req: PaymentRequirements) -> int:
    """Look up token decimals from the registry, default to 6."""
    token = TokenRegistry.find_by_address(req.network, req.asset)
    return token.decimals if token else 6


def _normalized_cost(req: PaymentRequirements) -> Decimal:
    """Calculate total cost normalized to human-readable units.

    e.g. 1_000_000 raw with 6 decimals  -> 1.0
         1_000_000_000_000_000_000 raw with 18 decimals -> 1.0
    """
    decimals = _get_decimals(req)
    return Decimal(str(req.amount)) / Decimal(10) ** decimals


def sufficient_balance_policy(signer: "ClientSigner"):
    """Create a policy that filters out tokens with insufficient balance.

    When the server accepts multiple tokens (e.g. USDT and USDD),
    this policy checks the user's on-chain balance for each token
    and removes options the user cannot afford.

    This ensures that if USDT balance is insufficient but USDD has
    enough balance, the client will fall back to USDD even if it
    costs more.

    Args:
        signer: ClientSigner with check_balance capability

    Returns:
        Async policy function for use with X402Client.register_policy()
    """

    async def policy(
        requirements: list[PaymentRequirements],
    ) -> list[PaymentRequirements]:
        affordable: list[PaymentRequirements] = []
        for req in requirements:
            balance = await signer.check_balance(req.asset, req.network)
            needed = int(req.amount)
            if hasattr(req, "extra") and req.extra and hasattr(req.extra, "fee"):
                fee = req.extra.fee
                if fee and hasattr(fee, "fee_amount"):
                    needed += int(fee.fee_amount)
            if balance >= needed:
                logger.info(
                    "Token %s on %s: balance=%d >= needed=%d (OK)",
                    req.asset, req.network, balance, needed,
                )
                affordable.append(req)
            else:
                logger.info(
                    "Token %s on %s: balance=%d < needed=%d (skipped)",
                    req.asset, req.network, balance, needed,
                )
        return affordable if affordable else requirements

    return policy


class DefaultTokenSelectionStrategy:
    """Default strategy: normalize by token decimals, pick cheapest.

    Compares real value (amount / 10^decimals) so that tokens with
    different precisions (e.g. USDT 6, USDD 18) are ranked fairly.
    """

    async def select(
        self,
        accepts: list[PaymentRequirements],
    ) -> PaymentRequirements:
        if not accepts:
            raise ValueError("No payment options available")

        selected = min(accepts, key=_normalized_cost)
        logger.info(
            "Selected token %s on %s (normalized_cost=%.6f)",
            selected.asset,
            selected.network,
            _normalized_cost(selected),
        )
        return selected
