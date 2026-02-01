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
  // EVM networks
  'eip155:1': 1,               // Ethereum Mainnet
  'eip155:8453': 8453,         // Base
  'eip155:84532': 84532,       // Base Sepolia
};

/** PaymentPermit contract addresses */
export const PAYMENT_PERMIT_ADDRESSES: Record<string, string> = {
  'tron:mainnet': 'T...',  // TODO: Deploy
  'tron:shasta': 'T...',   // TODO: Deploy
  'tron:nile': 'TCgKLk57cH8U99kfx3rmiZL5wCc3q5Wdz4',
  // EVM addresses would be 0x format
};

/** Zero addresses for different network types */
export const ZERO_ADDRESSES = {
  evm: '0x0000000000000000000000000000000000000000',
  tron: 'T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuWwb',
} as const;

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
  return PAYMENT_PERMIT_ADDRESSES[network] ?? ZERO_ADDRESSES.evm;
}

/**
 * Check if network is TRON
 */
export function isTronNetwork(network: string): boolean {
  return network.startsWith('tron:');
}

/**
 * Check if network is EVM
 */
export function isEvmNetwork(network: string): boolean {
  return network.startsWith('eip155:');
}

/**
 * Get zero address for network type
 */
export function getZeroAddress(network: string): string {
  return isTronNetwork(network) ? ZERO_ADDRESSES.tron : ZERO_ADDRESSES.evm;
}
