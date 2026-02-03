/**
 * TronClientSigner - TRON client signer for x402 protocol
 *
 * Uses TronWeb's signTypedData (TIP-712) for EIP-712 compatible signing.
 */

import type { ClientSigner } from '../index.js';
import { getChainId, getPaymentPermitAddress, toEvmHex, type Hex } from '../index.js';
import type { TronWeb, TypedDataDomain, TypedDataField, TronNetwork } from './types.js';

/** ERC20 function selectors */
const ERC20_ALLOWANCE_SELECTOR = 'allowance(address,address)';
const ERC20_APPROVE_SELECTOR = 'approve(address,uint256)';

/**
 * TRON client signer implementation using TronWeb's signTypedData
 */
export class TronClientSigner implements ClientSigner {
  private tronWeb: TronWeb;
  private privateKey: string | undefined;
  private address: string; // Base58 format
  private network: TronNetwork;

  private constructor(
    tronWeb: TronWeb,
    address: string,
    network: TronNetwork,
    privateKey?: string
  ) {
    this.tronWeb = tronWeb;
    this.address = address;
    this.network = network;
    this.privateKey = privateKey;
  }

  /**
   * Create signer from TronWeb instance (browser wallet mode)
   */
  static fromTronWeb(tronWeb: TronWeb, network: TronNetwork = 'mainnet'): TronClientSigner {
    const privateKey = tronWeb.defaultPrivateKey;
    if (!privateKey) {
      throw new Error('TronWeb instance must have a default private key or be connected to a wallet');
    }
    const address = tronWeb.address.fromPrivateKey(privateKey);
    return new TronClientSigner(tronWeb, address, network);
  }

  /**
   * Create signer with explicit private key
   */
  static withPrivateKey(
    tronWeb: TronWeb,
    privateKey: string,
    network: TronNetwork = 'mainnet'
  ): TronClientSigner {
    const cleanKey = privateKey.startsWith('0x') ? privateKey.slice(2) : privateKey;
    const address = tronWeb.address.fromPrivateKey(cleanKey);
    return new TronClientSigner(tronWeb, address, network, cleanKey);
  }

  getAddress(): string {
    return this.address;
  }

  getEvmAddress(): Hex {
    return toEvmHex(this.address);
  }

  async signMessage(message: Uint8Array): Promise<string> {
    const messageHex = Array.from(message)
      .map(b => b.toString(16).padStart(2, '0'))
      .join('');
    return this.tronWeb.trx.signMessageV2(messageHex, this.privateKey);
  }

  /**
   * Sign EIP-712 typed data using TronWeb's signTypedData (TIP-712)
   */
  async signTypedData(
    domain: Record<string, unknown>,
    types: Record<string, unknown>,
    message: Record<string, unknown>
  ): Promise<string> {
    // Prepare domain
    const typedDomain: TypedDataDomain = {
      name: domain.name as string,
      chainId: domain.chainId as number,
      verifyingContract: domain.verifyingContract as string,
    };

    // Use signTypedData (stable API) or fall back to _signTypedData (legacy)
    const signFn = this.tronWeb.trx.signTypedData || this.tronWeb.trx._signTypedData;
    if (!signFn) {
      throw new Error('TronWeb does not support signTypedData. Please upgrade to TronWeb >= 5.0');
    }

    return signFn.call(
      this.tronWeb.trx,
      typedDomain,
      types as Record<string, TypedDataField[]>,
      message,
      this.privateKey
    );
  }

  async checkAllowance(token: string, _amount: bigint, network: string): Promise<bigint> {
    const spender = getPaymentPermitAddress(`tron:${this.network}`);
    
    try {
      const ownerHex = toEvmHex(this.address);
      const spenderHex = toEvmHex(spender);

      const result = await this.tronWeb.transactionBuilder.triggerConstantContract(
        token,
        ERC20_ALLOWANCE_SELECTOR,
        {},
        [
          { type: 'address', value: ownerHex },
          { type: 'address', value: spenderHex },
        ],
        this.address
      );

      if (result.result?.result && result.constant_result?.length) {
        return BigInt('0x' + result.constant_result[0]);
      }
    } catch (error) {
      console.error(`[TronClientSigner] Failed to check allowance: ${error}`);
    }

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
      console.log(`[ALLOWANCE] Sufficient allowance: ${currentAllowance} >= ${amount}`);
      return true;
    }

    if (mode === 'interactive') {
      throw new Error('Interactive approval not implemented - use wallet UI');
    }

    // Auto mode: send approve transaction
    console.log(`[ALLOWANCE] Insufficient allowance: ${currentAllowance} < ${amount}, sending approve...`);
    
    const spender = getPaymentPermitAddress(`tron:${this.network}`);
    const spenderHex = toEvmHex(spender);
    
    try {
      // Build approve transaction
      const tx = await this.tronWeb.transactionBuilder.triggerSmartContract(
        token,
        ERC20_APPROVE_SELECTOR,
        {
          feeLimit: 100_000_000,
          callValue: 0,
        },
        [
          { type: 'address', value: spenderHex },
          { type: 'uint256', value: amount.toString() },
        ],
        this.address
      );

      if (!tx.result?.result) {
        console.error('[ALLOWANCE] Failed to build approve transaction');
        return false;
      }

      // Sign transaction
      const signedTx = await this.tronWeb.trx.sign(tx.transaction, this.privateKey);

      // Broadcast transaction
      const broadcast = await this.tronWeb.trx.sendRawTransaction(signedTx);
      
      if (!broadcast.result) {
        console.error('[ALLOWANCE] Failed to broadcast approve transaction:', broadcast);
        return false;
      }

      console.log(`[ALLOWANCE] Approve transaction sent: ${broadcast.txid}`);
      
      // Wait for confirmation (poll for ~30 seconds)
      const txid = broadcast.txid;
      for (let i = 0; i < 10; i++) {
        await new Promise(resolve => setTimeout(resolve, 3000));
        try {
          const info = await this.tronWeb.trx.getTransactionInfo(txid);
          if (info && info.blockNumber) {
            const success = info.receipt?.result === 'SUCCESS';
            console.log(`[ALLOWANCE] Approve confirmed: ${success ? 'SUCCESS' : 'FAILED'}`);
            return success;
          }
        } catch {
          // Not confirmed yet, continue polling
        }
      }

      console.log('[ALLOWANCE] Approve transaction not confirmed within timeout, assuming success');
      return true;
    } catch (error) {
      console.error('[ALLOWANCE] Approve transaction failed:', error);
      return false;
    }
  }
}
