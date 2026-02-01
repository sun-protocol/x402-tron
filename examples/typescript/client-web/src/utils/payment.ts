import type { PaymentRequirements, PaymentPayload, PaymentPermit, PaymentPermitContext } from '../types';

/** Delivery kind type */
type DeliveryKind = 'PAYMENT_ONLY' | 'PAYMENT_AND_DELIVERY';

/** TronWeb instance type (injected by TronLink) */
interface TronWebInstance {
  trx: {
    signTypedData?: (
      domain: Record<string, unknown>,
      types: Record<string, unknown>,
      value: Record<string, unknown>
    ) => Promise<string>;
    _signTypedData?: (
      domain: Record<string, unknown>,
      types: Record<string, unknown>,
      value: Record<string, unknown>
    ) => Promise<string>;
  };
  address: {
    toHex(address: string): string;
    fromHex(address: string): string;
  };
}

/** Kind mapping for EIP-712 (string to numeric) */
const KIND_MAP: Record<DeliveryKind, number> = {
  PAYMENT_ONLY: 0,
  PAYMENT_AND_DELIVERY: 1,
};

/** Base58 alphabet for TRON addresses */
const BASE58_ALPHABET = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz';

/**
 * Convert TRON address to EVM hex format (0x...)
 * Handles: Base58 (T...), hex with 41 prefix, and 0x format
 */
function toEvmHex(addr: string): `0x${string}` {
  console.log(`[toEvmHex] Input: "${addr}"`);
  
  // Handle null/undefined/empty
  if (!addr) {
    console.log('[toEvmHex] Empty address, returning zero address');
    return '0x0000000000000000000000000000000000000000';
  }

  // Already 0x hex format
  if (addr.startsWith('0x')) {
    console.log(`[toEvmHex] Already 0x format: ${addr}`);
    return addr as `0x${string}`;
  }

  // Handle special case: T followed by all zeros (invalid Base58 placeholder)
  // e.g., T000000000000000000000000000000000
  if (addr.startsWith('T') && /^T0+$/.test(addr)) {
    console.log(`[toEvmHex] Zero placeholder address: ${addr} -> zero address`);
    return '0x0000000000000000000000000000000000000000';
  }
  
  // Raw hex (all hex characters, no prefix) - check this BEFORE Base58
  if (/^[0-9a-fA-F]+$/.test(addr)) {
    // If starts with 41 and is 42 chars, it's TRON hex format
    if (addr.startsWith('41') && addr.length === 42) {
      const body = addr.slice(2);
      console.log(`[toEvmHex] TRON hex (41 prefix): ${addr} -> 0x${body}`);
      return `0x${body}` as `0x${string}`;
    }
    // Otherwise treat as raw hex
    const body = addr.slice(-40).padStart(40, '0');
    console.log(`[toEvmHex] Raw hex: ${addr} -> 0x${body}`);
    return `0x${body}` as `0x${string}`;
  }

  // Base58 format (starts with T)
  if (addr.startsWith('T')) {
    console.log(`[toEvmHex] Base58 format: ${addr}`);
    const alphabetMap: Record<string, number> = {};
    for (let i = 0; i < BASE58_ALPHABET.length; i++) {
      alphabetMap[BASE58_ALPHABET[i]] = i;
    }

    let num = BigInt(0);
    for (const char of addr) {
      const value = alphabetMap[char];
      if (value === undefined) {
        // If contains invalid Base58 chars, treat as zero address
        console.warn(`[toEvmHex] Invalid Base58 character: ${char} in address: ${addr}, returning zero address`);
        return '0x0000000000000000000000000000000000000000';
      }
      num = num * BigInt(58) + BigInt(value);
    }

    let hex = num.toString(16);
    if (hex.length % 2 !== 0) {
      hex = '0' + hex;
    }

    // Remove checksum (last 4 bytes = 8 hex chars) and 41 prefix
    const withoutChecksum = hex.slice(0, -8);
    const body = withoutChecksum.startsWith('41') ? withoutChecksum.slice(2) : withoutChecksum;
    const result = `0x${body.padStart(40, '0')}` as `0x${string}`;
    console.log(`[toEvmHex] Base58 converted: ${addr} -> ${result}`);
    return result;
  }

  console.warn(`[toEvmHex] Invalid address format: ${addr}, returning zero address`);
  return '0x0000000000000000000000000000000000000000';
}

/** EIP-712 domain for TRON payment permit */
// Note: NO version field! Based on contract's EIP712Domain definition
const PAYMENT_PERMIT_DOMAIN = {
  name: 'PaymentPermit',
};

/** EIP-712 types for payment permit */
// Primary type is "PaymentPermitDetails" to match the contract's typehash
const PAYMENT_PERMIT_TYPES = {
  PermitMeta: [
    { name: 'kind', type: 'uint8' },
    { name: 'paymentId', type: 'bytes16' },
    { name: 'nonce', type: 'uint256' },
    { name: 'validAfter', type: 'uint256' },
    { name: 'validBefore', type: 'uint256' },
  ],
  Payment: [
    { name: 'payToken', type: 'address' },
    { name: 'maxPayAmount', type: 'uint256' },
    { name: 'payTo', type: 'address' },
  ],
  Fee: [
    { name: 'feeTo', type: 'address' },
    { name: 'feeAmount', type: 'uint256' },
  ],
  Delivery: [
    { name: 'receiveToken', type: 'address' },
    { name: 'miniReceiveAmount', type: 'uint256' },
    { name: 'tokenId', type: 'uint256' },
  ],
  PaymentPermitDetails: [
    { name: 'meta', type: 'PermitMeta' },
    { name: 'buyer', type: 'address' },
    { name: 'caller', type: 'address' },
    { name: 'payment', type: 'Payment' },
    { name: 'fee', type: 'Fee' },
    { name: 'delivery', type: 'Delivery' },
  ],
};

/** Generate a random payment ID */
function generatePaymentId(): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return '0x' + Array.from(bytes).map(b => b.toString(16).padStart(2, '0')).join('');
}

/** Generate a random nonce */
function generateNonce(): string {
  return Math.floor(Math.random() * 1000000000).toString();
}

/** Create payment payload for x402 protocol */
export async function createPaymentPayload(
  requirements: PaymentRequirements,
  extensions: { paymentPermitContext?: PaymentPermitContext } | undefined,
  buyerAddress: string,
  _wallet: unknown // Not used - we use window.tronWeb directly
): Promise<PaymentPayload> {
  const now = Math.floor(Date.now() / 1000);
  const validBefore = now + (requirements.maxTimeoutSeconds || 300);

  // Use context from server or generate defaults
  const context = extensions?.paymentPermitContext;
  const meta = {
    kind: context?.meta.kind || 'PAYMENT_ONLY' as const,
    paymentId: context?.meta.paymentId || generatePaymentId(),
    nonce: context?.meta.nonce || generateNonce(),
    validAfter: context?.meta.validAfter || now,
    validBefore: context?.meta.validBefore || validBefore,
  };

  const delivery = {
    receiveToken: context?.delivery.receiveToken || '0x0000000000000000000000000000000000000000',
    miniReceiveAmount: context?.delivery.miniReceiveAmount || '0',
    tokenId: context?.delivery.tokenId || '0',
  };

  const feeTo = requirements.extra?.fee?.feeTo || '0x0000000000000000000000000000000000000000';
  const feeAmount = requirements.extra?.fee?.feeAmount || '0';

  const permit: PaymentPermit = {
    meta,
    buyer: buyerAddress,
    caller: feeTo,
    payment: {
      payToken: requirements.asset,
      maxPayAmount: requirements.amount,
      payTo: requirements.payTo,
    },
    fee: {
      feeTo,
      feeAmount,
    },
    delivery,
  };

  // Sign using TronWeb's signTypedData (TIP-712)
  try {
    console.log('=== Creating Payment Payload ===');
    console.log('Requirements:', JSON.stringify(requirements, null, 2));
    console.log('Extensions:', JSON.stringify(extensions, null, 2));
    console.log('Buyer address:', buyerAddress);
    console.log('Permit (before conversion):', JSON.stringify(permit, null, 2));

    // Get TronWeb from window (injected by TronLink)
    const tronWeb = (window as unknown as { tronWeb?: TronWebInstance }).tronWeb;
    if (!tronWeb) {
      throw new Error('TronWeb not found. Please install TronLink wallet.');
    }
    console.log('TronWeb found:', !!tronWeb);

    // Check for signTypedData support
    const signTypedData = tronWeb.trx.signTypedData || tronWeb.trx._signTypedData;
    if (!signTypedData) {
      throw new Error('TronWeb does not support signTypedData. Please upgrade TronLink.');
    }
    console.log('signTypedData method available');

    console.log('=== Converting addresses ===');
    // Convert permit to EIP-712 compatible format:
    // 1. kind: string -> uint8
    // 2. All addresses: TRON Base58 -> EVM hex (0x...)
    const permitForSigning = {
      meta: {
        kind: KIND_MAP[permit.meta.kind],
        paymentId: permit.meta.paymentId,
        nonce: permit.meta.nonce,
        validAfter: permit.meta.validAfter,
        validBefore: permit.meta.validBefore,
      },
      buyer: toEvmHex(permit.buyer),
      caller: toEvmHex(permit.caller),
      payment: {
        payToken: toEvmHex(permit.payment.payToken),
        maxPayAmount: permit.payment.maxPayAmount,
        payTo: toEvmHex(permit.payment.payTo),
      },
      fee: {
        feeTo: toEvmHex(permit.fee.feeTo),
        feeAmount: permit.fee.feeAmount,
      },
      delivery: {
        receiveToken: toEvmHex(permit.delivery.receiveToken),
        miniReceiveAmount: permit.delivery.miniReceiveAmount,
        tokenId: permit.delivery.tokenId,
      },
    };

    // Build domain with chainId and verifyingContract
    // TRON Nile testnet chainId: 3448148188
    // TRON Mainnet chainId: 728126428
    const chainId = requirements.network.includes('nile') ? 3448148188 :
                    requirements.network.includes('shasta') ? 2494104990 : 728126428;

    // PaymentPermit contract addresses (Base58 format)
    const PAYMENT_PERMIT_CONTRACTS: Record<string, string> = {
      'tron:nile': 'TCgKLk57cH8U99kfx3rmiZL5wCc3q5Wdz4',
      'tron:mainnet': 'T0000000000000000000000000000000', // TODO: Deploy
      'tron:shasta': 'T0000000000000000000000000000000', // TODO: Deploy
    };

    const contractBase58 = PAYMENT_PERMIT_CONTRACTS[requirements.network];
    const verifyingContract = contractBase58 ? toEvmHex(contractBase58) : '0x' + '0'.repeat(40);

    const domain = {
      name: PAYMENT_PERMIT_DOMAIN.name,
      chainId,
      verifyingContract,
    };

    console.log('=== Signing Data ===');
    console.log('Domain:', JSON.stringify(domain, null, 2));
    console.log('Types:', JSON.stringify(PAYMENT_PERMIT_TYPES, null, 2));
    console.log('Permit for signing:', JSON.stringify(permitForSigning, null, 2));

    // Call TronWeb's signTypedData (TIP-712)
    console.log('Calling signTypedData...');
    const signature = await signTypedData.call(
      tronWeb.trx,
      domain,
      PAYMENT_PERMIT_TYPES,
      permitForSigning
    );

    console.log('=== Signature Result ===');
    console.log('Signature:', signature);

    const payload = {
      x402Version: 2,
      resource: { url: '' },
      accepted: requirements,
      payload: {
        signature,
        paymentPermit: permit,
      },
      extensions: {},
    };

    console.log('=== Final Payload ===');
    console.log('Payload:', JSON.stringify(payload, null, 2));

    return payload;
  } catch (error) {
    console.error('Signature error:', error);
    throw new Error('Failed to sign payment permit: ' + (error instanceof Error ? error.message : 'Unknown error'));
  }
}

/** Encode payment payload to base64 */
export function encodePaymentPayload(payload: PaymentPayload): string {
  const jsonString = JSON.stringify(payload);
  // Use btoa for browser environment
  return btoa(jsonString);
}

/** Decode payment payload from base64 */
export function decodePaymentPayload<T>(encoded: string): T {
  const jsonString = atob(encoded);
  return JSON.parse(jsonString) as T;
}
