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
  'tron:nile': 'TQr1nSWDLWgmJ3tkbFZANnaFcB5ci7Hvxa',
};

/** GasFreeController contract addresses */
export const GASFREE_CONTROLLER_ADDRESSES: Record<string, string> = {
  'tron:mainnet': 'TFFAMLQZybALab4uxHA9RBE7pxhUAjfF3U',
  'tron:shasta': 'TQghdCeVDA6CnuNVTUhfaAyPfTetqZWNpm',
  'tron:nile': 'THQGuFzL87ZqhxkgqYEryRAd7gqFqL5rdc',
};

/** GasFree beacon addresses */
export const GASFREE_BEACON_ADDRESSES: Record<string, string> = {
  'tron:mainnet': 'TSP9UW6FQhT76XD2jWA6ipGMx3yGbjDffP',
  'tron:shasta': 'TQ1jvA3nLDMDNbJoMPLzTPoqAg8NvZ5CCW',
  'tron:nile': 'TLtCGmaxH3PbuaF6kbybwteZcHptEdgQGC',
};

/** GasFree API Base URLs */
export const GASFREE_API_BASE_URLS: Record<string, string> = {
  'tron:mainnet': 'https://open.gasfree.io/tron',
  'tron:shasta': 'https://open-test.gasfree.io/shasta', // 按官方规律推测
  'tron:nile': 'https://open-test.gasfree.io/nile',
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
 * Get GasFreeController contract address for network
 */
export function getGasFreeControllerAddress(network: string): string {
  return GASFREE_CONTROLLER_ADDRESSES[network] ?? TRON_ZERO_ADDRESS;
}

/**
 * Get GasFree beacon address for network
 */
export function getGasFreeBeaconAddress(network: string): string {
  return GASFREE_BEACON_ADDRESSES[network] ?? TRON_ZERO_ADDRESS;
}

/**
 * Get GasFree API Base URL for network
 */
export function getGasFreeApiBaseUrl(network: string): string {
  return GASFREE_API_BASE_URLS[network] ?? 'https://api.gasfree.io/v1';
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
