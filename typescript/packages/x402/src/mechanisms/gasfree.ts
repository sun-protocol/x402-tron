import { TronGasFree } from '@gasfree/gasfree-sdk';
import {
  PaymentPayload,
  PaymentRequirements,
  PaymentPermit,
  DeliveryKind,
  ClientMechanism,
  ClientSigner,
  toEvmHex,
} from '../index.js';
import { getChainId, getGasFreeApiBaseUrl } from '../config.js';
import { GasFreeAPIClient } from '../utils/gasfree.js';

/**
 * GasFreeTronClientMechanism - GasFree payment mechanism for TRON.
 * 
 * Supports USDT and USDD payments without TRX gas fees.
 * Based on the @gasfree/gasfree-sdk.
 */
export class GasFreeTronClientMechanism implements ClientMechanism {
  private signer: ClientSigner;

  constructor(signer: ClientSigner) {
    this.signer = signer;
  }

  scheme(): string {
    return 'gasfree_exact';
  }

  async createPaymentPayload(
    requirements: PaymentRequirements,
    resource: string,
    extensions?: Record<string, unknown>
  ): Promise<PaymentPayload> {
    const network = requirements.network;
    const chainId = getChainId(network);
    const userAddress = this.signer.getAddress();
    const apiBaseUrl = getGasFreeApiBaseUrl(network);
    const apiClient = new GasFreeAPIClient(apiBaseUrl);

    // 1. Fetch account info from GasFree API
    // This replaces local address calculation and provides activation/balance status
    console.info(`Fetching account info for ${userAddress} from GasFree API...`);
    const accountInfo = await apiClient.getAddressInfo(userAddress);
    
    const gasfreeAddress = accountInfo.gasFreeAddress;
    const isActive = accountInfo.active;
    const nonce = accountInfo.nonce;

    if (!gasfreeAddress) {
      throw new Error(`Could not retrieve GasFree address for ${userAddress}`);
    }

    // 2. Check activation status (Requirement 3.3.2)
    if (!isActive) {
      throw new Error(`GasFree account for ${userAddress} (${gasfreeAddress}) is not activated. Please activate your GasFree wallet before making payments.`);
    }

    // 3. Assemble parameters
    const context = (extensions?.paymentPermitContext as any) || {};
    const meta = context.meta || {};
    
    // Default maxFee to 0.1 USDT/USDD (10^5) if not provided
    let maxFee = requirements.extra?.fee?.feeAmount || '100000';

    // 4. Check balance and transfer fee (Requirement 3.3.3)
    // Find the asset in the account info to get balance and protocol transfer fee
    // Note: API returns tokenAddress in Base58 format
    const asset = accountInfo.assets.find((a: any) => 
      a.tokenAddress === requirements.asset
    );

    let transferFee = BigInt(0);
    if (asset) {
      transferFee = BigInt(asset.transferFee || '0');
    }

    // Ensure maxFee is at least the protocol's transferFee
    let maxFeeBig = BigInt(maxFee);
    if (maxFeeBig < transferFee) {
      console.info(`Increasing maxFee from ${maxFeeBig} to ${transferFee} to meet GasFree protocol requirement`);
      maxFeeBig = transferFee;
      maxFee = maxFeeBig.toString();
    }

    const skipBalanceCheck = (extensions as any)?.skipBalanceCheck || false;
    if (!skipBalanceCheck) {
      console.info(`Verifying balance for ${gasfreeAddress}...`);
      
      if (asset) {
          // Use balance from API if available
          const assetBalance = BigInt(asset.balance || '0');
          const requiredTotal = BigInt(requirements.amount) + maxFeeBig;
          if (assetBalance < requiredTotal) {
            throw new Error(`Insufficient balance in GasFree wallet ${gasfreeAddress}. Required: ${requiredTotal}, Current: ${assetBalance}. Please top up.`);
          }
      } else {
        // Asset not found in GasFree account at all
        throw new Error(`Asset ${requirements.asset} not found in GasFree account ${gasfreeAddress}. Please top up.`);
      }
    }

    const deadline = meta.validBefore || Math.floor(Date.now() / 1000) + 3600;
    
    // Initialize GasFree SDK for signing
    const gasFree = new TronGasFree({
      chainId,
    });

    const params = {
      token: requirements.asset,
      serviceProvider: requirements.payTo,
      user: userAddress,
      receiver: requirements.payTo,
      value: requirements.amount,
      maxFee: maxFee,
      deadline: deadline.toString(),
      version: '1',
      nonce: nonce.toString(),
    };

    // 5. Get TIP-712 typed data

    const { domain, types, message } = gasFree.assembleGasFreeTransactionJson(params);

    // 5. Sign
    const signature = await this.signer.signTypedData(domain, types, message);

    // 6. Build PaymentPermit structure for compatibility
    // We map GasFree parameters to PaymentPermit fields
    const paymentPermit: PaymentPermit = {
      meta: {
        kind: 'PAYMENT_ONLY' as DeliveryKind,
        paymentId: meta.paymentId || '',
        nonce: nonce.toString(),
        validAfter: meta.validAfter || 0,
        validBefore: Number(deadline),
      },
      buyer: userAddress,
      caller: domain.verifyingContract, // The GasFreeController
      payment: {
        payToken: requirements.asset,
        payAmount: requirements.amount,
        payTo: requirements.payTo,
      },
      fee: {
        feeTo: requirements.payTo,
        feeAmount: maxFee,
      },
      delivery: {
        receiveToken: 'T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuWwb',
        miniReceiveAmount: '0',
        tokenId: '0',
      },
    };

    return {
      x402Version: 2,
      resource: { url: resource },
      accepted: requirements,
      payload: {
        signature,
        paymentPermit,
      },
      extensions: {
        ...extensions,
        gasfreeAddress,
        scheme: 'gasfree_exact',
      },
    };
  }
}
