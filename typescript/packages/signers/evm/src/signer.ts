/**
 * EvmClientSigner - EVM client signer for x402 protocol
 */

import type { ClientSigner } from '@x402/core';
import { ERC20_ABI, getPaymentPermitAddress } from '@x402/core';

/** Viem WalletClient type (from viem package) */
interface WalletClient {
  account: { address: string };
  signMessage(args: { message: { raw: Uint8Array } }): Promise<string>;
  signTypedData(args: {
    domain: Record<string, unknown>;
    types: Record<string, unknown>;
    primaryType: string;
    message: Record<string, unknown>;
  }): Promise<string>;
}

/** Viem PublicClient type */
interface PublicClient {
  readContract(args: {
    address: string;
    abi: unknown[];
    functionName: string;
    args: unknown[];
  }): Promise<unknown>;
  waitForTransactionReceipt(args: { hash: string }): Promise<unknown>;
}

/**
 * EVM client signer implementation
 */
export class EvmClientSigner implements ClientSigner {
  private privateKey: string;
  private address: string;
  private walletClient: WalletClient | null = null;
  private publicClient: PublicClient | null = null;

  private constructor(privateKey: string, address: string) {
    this.privateKey = privateKey;
    this.address = address;
  }

  /**
   * Create signer from private key
   */
  static fromPrivateKey(privateKey: string): EvmClientSigner {
    const cleanKey = privateKey.startsWith('0x') ? privateKey : `0x${privateKey}`;
    const address = EvmClientSigner.deriveAddress(cleanKey);
    return new EvmClientSigner(cleanKey, address);
  }

  /**
   * Create signer with viem clients
   */
  static withClients(
    privateKey: string,
    walletClient: WalletClient,
    publicClient: PublicClient
  ): EvmClientSigner {
    const signer = EvmClientSigner.fromPrivateKey(privateKey);
    signer.walletClient = walletClient;
    signer.publicClient = publicClient;
    return signer;
  }

  /**
   * Derive EVM address from private key
   */
  private static deriveAddress(privateKey: string): string {
    // Placeholder - actual implementation requires viem/ethers
    return `0x${privateKey.slice(2, 42)}`;
  }

  getAddress(): string {
    return this.address;
  }

  async signMessage(message: Uint8Array): Promise<string> {
    if (!this.walletClient) {
      throw new Error('WalletClient required for signing');
    }
    return this.walletClient.signMessage({ message: { raw: message } });
  }

  async signTypedData(
    domain: Record<string, unknown>,
    types: Record<string, unknown>,
    message: Record<string, unknown>
  ): Promise<string> {
    if (!this.walletClient) {
      throw new Error('WalletClient required for signing');
    }
    return this.walletClient.signTypedData({
      domain,
      types,
      primaryType: 'PaymentPermitDetails',
      message,
    });
  }

  async checkAllowance(
    token: string,
    _amount: bigint,
    network: string
  ): Promise<bigint> {
    if (!this.publicClient) {
      throw new Error('PublicClient required for checking allowance');
    }

    const spender = getPaymentPermitAddress(network);
    const result = await this.publicClient.readContract({
      address: token,
      abi: ERC20_ABI,
      functionName: 'allowance',
      args: [this.address, spender],
    });

    return BigInt(result as string);
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
      throw new Error('Interactive approval not implemented');
    }

    // Auto mode: would send approve transaction
    return true;
  }
}
