/**
 * TronClientSigner - TRON client signer for x402 protocol
 */

import type { ClientSigner } from '@x402/core';

/** TronWeb instance type (from tronweb package) */
interface TronWeb {
  address: {
    fromPrivateKey(privateKey: string): string;
    toHex(address: string): string;
  };
  trx: {
    sign(message: string, privateKey: string): Promise<string>;
    signMessageV2(message: string, privateKey: string): Promise<string>;
  };
  transactionBuilder: {
    triggerSmartContract(
      contractAddress: string,
      functionSelector: string,
      options: Record<string, unknown>,
      parameters: unknown[],
      issuerAddress: string
    ): Promise<{ transaction: unknown; result: { result: boolean } }>;
  };
  contract(): {
    at(address: string): Promise<unknown>;
  };
}

/**
 * TRON client signer implementation
 */
export class TronClientSigner implements ClientSigner {
  private privateKey: string;
  private address: string;
  private tronWeb: TronWeb | null = null;

  private constructor(privateKey: string, address: string) {
    this.privateKey = privateKey;
    this.address = address;
  }

  /**
   * Create signer from private key
   */
  static fromPrivateKey(privateKey: string): TronClientSigner {
    const cleanKey = privateKey.startsWith('0x') ? privateKey.slice(2) : privateKey;
    const address = TronClientSigner.deriveAddress(cleanKey);
    return new TronClientSigner(cleanKey, address);
  }

  /**
   * Create signer with TronWeb instance
   */
  static withTronWeb(privateKey: string, tronWeb: TronWeb): TronClientSigner {
    const signer = TronClientSigner.fromPrivateKey(privateKey);
    signer.tronWeb = tronWeb;
    return signer;
  }

  /**
   * Derive TRON address from private key
   */
  private static deriveAddress(privateKey: string): string {
    // This is a placeholder - actual implementation requires tronweb
    // In production, use: TronWeb.address.fromPrivateKey(privateKey)
    return `T${privateKey.slice(0, 33)}`;
  }

  getAddress(): string {
    return this.address;
  }

  async signMessage(message: Uint8Array): Promise<string> {
    if (!this.tronWeb) {
      throw new Error('TronWeb instance required for signing');
    }
    const messageHex = Array.from(message)
      .map(b => b.toString(16).padStart(2, '0'))
      .join('');
    return this.tronWeb.trx.signMessageV2(messageHex, this.privateKey);
  }

  async signTypedData(
    domain: Record<string, unknown>,
    types: Record<string, unknown>,
    message: Record<string, unknown>
  ): Promise<string> {
    // EIP-712 signing for TRON
    // TRON uses the same EIP-712 standard as EVM
    const typedData = {
      types: {
        EIP712Domain: [
          { name: 'name', type: 'string' },
          { name: 'version', type: 'string' },
        ],
        ...types,
      },
      primaryType: 'PaymentPermit',
      domain,
      message,
    };

    // Hash and sign the typed data
    // In production, use proper EIP-712 hashing library
    const dataString = JSON.stringify(typedData);
    const encoder = new TextEncoder();
    const dataBytes = encoder.encode(dataString);
    
    return this.signMessage(dataBytes);
  }

  async checkAllowance(
    token: string,
    _amount: bigint,
    _network: string
  ): Promise<bigint> {
    if (!this.tronWeb) {
      throw new Error('TronWeb instance required for checking allowance');
    }
    
    // Call token contract's allowance function
    // In production: contract.allowance(owner, spender).call()
    console.log(`Checking allowance for token ${token}`);
    return BigInt(0);
  }

  async ensureAllowance(
    token: string,
    amount: bigint,
    network: string,
    mode: 'auto' | 'interactive' | 'skip' = 'auto'
  ): Promise<boolean> {
    if (mode === 'skip') {
      return true;
    }

    const currentAllowance = await this.checkAllowance(token, amount, network);
    if (currentAllowance >= amount) {
      return true;
    }

    if (mode === 'interactive') {
      // In interactive mode, would prompt user
      throw new Error('Interactive approval not implemented');
    }

    // Auto mode: send approve transaction
    if (!this.tronWeb) {
      throw new Error('TronWeb instance required for approval');
    }

    // In production: call token.approve(spender, amount)
    console.log(`Approving ${amount} for token ${token}`);
    return true;
  }
}
