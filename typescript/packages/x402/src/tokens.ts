/**
 * Token registry - Centralized management of token configurations for all networks
 */

export interface TokenInfo {
  address: string;
  decimals: number;
  name: string;
  symbol: string;
}

const TOKENS: Record<string, Record<string, TokenInfo>> = {
  'tron:mainnet': {
    USDT: {
      address: 'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t',
      decimals: 6,
      name: 'Tether USD',
      symbol: 'USDT',
    },
    USDD: {
      address: 'TXDk8mbtRbXeYuMNS83CfKPaYYT8XWv9Hz',
      decimals: 18,
      name: 'Decentralized USD',
      symbol: 'USDD',
    },
  },
  'tron:shasta': {
    USDT: {
      address: 'TG3XXyExBkPp9nzdajDZsozEu4BkaSJozs',
      decimals: 6,
      name: 'Tether USD',
      symbol: 'USDT',
    },
  },
  'tron:nile': {
    USDT: {
      address: 'TXYZopYRdj2D9XRtbG411XZZ3kM5VkAeBf',
      decimals: 6,
      name: 'Tether USD',
      symbol: 'USDT',
    },
    USDD: {
      address: 'TGjgvdTWWrybVLaVeFqSyVqJQWjxqRYbaK',
      decimals: 18,
      name: 'Decentralized USD',
      symbol: 'USDD',
    },
  },
};

/** Get token info by network and symbol */
export function getToken(network: string, symbol: string): TokenInfo | undefined {
  return TOKENS[network]?.[symbol.toUpperCase()];
}

/** Find token info by network and contract address */
export function findByAddress(network: string, address: string): TokenInfo | undefined {
  const tokens = TOKENS[network];
  if (!tokens) return undefined;
  const lower = address.toLowerCase();
  return Object.values(tokens).find(t => t.address.toLowerCase() === lower);
}

/** Get all tokens for a network */
export function getNetworkTokens(network: string): Record<string, TokenInfo> {
  return TOKENS[network] ?? {};
}

/** Register a custom token */
export function registerToken(network: string, token: TokenInfo): void {
  if (!TOKENS[network]) {
    TOKENS[network] = {};
  }
  TOKENS[network][token.symbol.toUpperCase()] = token;
}
