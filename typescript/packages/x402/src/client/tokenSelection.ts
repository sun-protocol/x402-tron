/**
 * Token selection strategies for choosing which token to pay with.
 *
 * All tokens are assumed to be stablecoins, so selection normalizes raw amounts
 * by token decimals to compare real value (lower is better for the payer).
 */

import { findByAddress } from '../tokens.js';
import type { PaymentRequirements } from '../types/index.js';
import type { ClientSigner, PaymentPolicy } from './x402Client.js';

/** Strategy for selecting which payment option to use */
export interface TokenSelectionStrategy {
  select(accepts: PaymentRequirements[]): PaymentRequirements;
}

function getDecimals(req: PaymentRequirements): number {
  const token = findByAddress(req.network, req.asset);
  return token?.decimals ?? 6;
}

function normalizedCost(req: PaymentRequirements): number {
  const decimals = getDecimals(req);
  return Number(BigInt(req.amount)) / 10 ** decimals;
}

/**
 * Create a policy that filters out tokens with insufficient balance.
 *
 * When the server accepts multiple tokens (e.g. USDT and USDD),
 * this policy checks the user's on-chain balance for each token
 * and removes options the user cannot afford.
 *
 * This ensures that if USDT balance is insufficient but USDD has
 * enough balance, the client will fall back to USDD even if it
 * costs more.
 *
 * @param signer - ClientSigner with checkBalance capability
 * @returns Async policy function for use with X402Client.registerPolicy()
 */
export function sufficientBalancePolicy(signer: ClientSigner): PaymentPolicy {
  return async (requirements: PaymentRequirements[]): Promise<PaymentRequirements[]> => {
    const affordable: PaymentRequirements[] = [];
    for (const req of requirements) {
      const balance = await signer.checkBalance(req.asset, req.network);
      let needed = BigInt(req.amount);
      if (req.extra?.fee?.feeAmount) {
        needed += BigInt(req.extra.fee.feeAmount);
      }
      if (balance >= needed) {
        console.debug(`[x402] Balance OK: ${req.asset} on ${req.network}: ${balance} >= ${needed}`);
        affordable.push(req);
      } else {
        console.debug(`[x402] Balance insufficient: ${req.asset} on ${req.network}: ${balance} < ${needed}, skipped`);
      }
    }
    return affordable.length > 0 ? affordable : requirements;
  };
}

/**
 * Default strategy: normalize by token decimals, pick cheapest.
 *
 * Compares real value (amount / 10^decimals) so that tokens with
 * different precisions (e.g. USDT 6, USDD 18) are ranked fairly.
 */
export class DefaultTokenSelectionStrategy implements TokenSelectionStrategy {
  select(accepts: PaymentRequirements[]): PaymentRequirements {
    if (accepts.length === 0) {
      throw new Error('No payment options available');
    }

    let best = accepts[0];
    let bestCost = normalizedCost(best);

    for (let i = 1; i < accepts.length; i++) {
      const cost = normalizedCost(accepts[i]);
      if (cost < bestCost) {
        best = accepts[i];
        bestCost = cost;
      }
    }

    return best;
  }
}
