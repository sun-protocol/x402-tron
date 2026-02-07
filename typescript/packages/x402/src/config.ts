/**
 * Network configuration for x402 protocol
 * Centralized configuration for contract addresses and chain IDs
 */

/** Chain IDs for supported networks */
export const CHAIN_IDS: Record<string, number> = {
  // TRON networks
  'tron:mainnet': 728126428,   // 0x2b6653dc
  'tron:shasta': 2494104990,   // 0x94a9059e
  'tron:nile': 3448148188,     // 0xcd8690dc
};

/** PaymentPermit contract addresses */
export const PAYMENT_PERMIT_ADDRESSES: Record<string, string> = {
  'tron:mainnet': 'THnW1E6yQWgx9P3QtSqWw2t3qGwH35jARg',
  'tron:shasta': 'TVjYLoXatyMkemxzeB9M8ZE3uGttR9QZJ8',
  'tron:nile': 'TLEwy4d8oh5gTGUiwWcNUBSzppRNfaWymc',
};

/** Zero address for TRON */
export const TRON_ZERO_ADDRESS = 'T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuWwb';

/**
 * Get chain ID for network
 */
export function getChainId(network: string): number {
  const chainId = CHAIN_IDS[network];
  if (chainId === undefined) {
    throw new Error(`Unsupported network: ${network}`);
  }
  return chainId;
}

/**
 * Get PaymentPermit contract address for network
 */
export function getPaymentPermitAddress(network: string): string {
  return PAYMENT_PERMIT_ADDRESSES[network] ?? TRON_ZERO_ADDRESS;
}

/**
 * Check if network is TRON
 */
export function isTronNetwork(network: string): boolean {
  return network.startsWith('tron:');
}

/**
 * Get zero address for TRON network
 */
export function getZeroAddress(network: string): string {
  if (!isTronNetwork(network)) {
    throw new Error(`Unsupported network: ${network}`);
  }
  return TRON_ZERO_ADDRESS;
}
