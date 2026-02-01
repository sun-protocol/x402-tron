/**
 * @x402/signer-tron - TRON Client Signer for x402 protocol
 */

export { TronClientSigner } from './signer.js';
export type {
  TronWeb,
  TypedDataDomain,
  TypedDataField,
  TronNetwork,
} from './types.js';
export { TRON_CHAIN_IDS } from './types.js';

// Re-export address utilities from core
export { toEvmHex, toBase58, type Hex } from '@x402/core';
