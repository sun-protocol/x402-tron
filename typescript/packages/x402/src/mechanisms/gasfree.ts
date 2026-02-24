import { TronGasFree } from '@gasfree/gasfree-sdk';
import {
  PaymentPayload,
  PaymentRequirements,
  PaymentPermit,
  DeliveryKind,
  ClientMechanism,
  ClientSigner,
} from '../index.js';
import { getChainId, getGasFreeApiBaseUrl } from '../config.js';
import { GasFreeAPIClient } from '../utils/gasfree.js';

/**
 * GasFreeTronClientMechanism - GasFree payment mechanism for TRON (USDT/USDD).
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

    // 1. Fetch account info
    console.debug(`Fetching account info for ${userAddress} from GasFree API...`);
    const accountInfo = await apiClient.getAddressInfo(userAddress);
    const gasfreeAddress = accountInfo.gasFreeAddress;
    
    if (!gasfreeAddress) {
      throw new Error(`Could not retrieve GasFree address for ${userAddress}`);
    }

    // 2. Check activation status
    if (!accountInfo.active) {
      throw new Error(`GasFree account for ${userAddress} (${gasfreeAddress}) is not activated.`);
    }

    // 3. Prepare maxFee and validate against protocol transferFee
    const asset = accountInfo.assets.find((a: any) => a.tokenAddress === requirements.asset);
    const transferFee = BigInt(asset?.transferFee || '0');
    
    let maxFee = requirements.extra?.fee?.feeAmount;
    if (!maxFee) {
        // Default to transferFee from API, or 1 USDT (10^6) as a safe fallback
        maxFee = transferFee > 0n ? transferFee.toString() : '1000000';
    }

    let maxFeeBig = BigInt(maxFee);
    if (maxFeeBig < transferFee) {
      console.debug(`Increasing maxFee to ${transferFee} to meet protocol requirement`);
      maxFeeBig = transferFee;
      maxFee = maxFeeBig.toString();
    }

    // 4. Balance verification
    const skipBalanceCheck = (extensions as any)?.skipBalanceCheck || false;
    if (!skipBalanceCheck) {
      if (asset) {
          const assetBalance = BigInt(asset.balance || '0');
          const requiredTotal = BigInt(requirements.amount) + maxFeeBig;
          if (assetBalance < requiredTotal) {
            throw new Error(`Insufficient balance in GasFree wallet ${gasfreeAddress}.`);
          }
      } else {
        throw new Error(`Asset ${requirements.asset} not found in GasFree account ${gasfreeAddress}.`);
      }
    }

    const deadline = (extensions as any)?.paymentPermitContext?.meta?.validBefore || Math.floor(Date.now() / 1000) + 3600;
    
    const gasFree = new TronGasFree({ chainId });

    // 5. Sign TIP-712 typed data
    const { domain, types, message } = gasFree.assembleGasFreeTransactionJson({
      token: requirements.asset,
      serviceProvider: requirements.payTo,
      user: userAddress,
      receiver: requirements.payTo,
      value: requirements.amount,
      maxFee: maxFee,
      deadline: deadline.toString(),
      version: '1',
      nonce: accountInfo.nonce.toString(),
    });
    
    const signature = await this.signer.signTypedData(domain, types, message);

    // 6. Build PaymentPermit structure
    const paymentPermit: PaymentPermit = {
      meta: {
        kind: 'PAYMENT_ONLY' as DeliveryKind,
        paymentId: (extensions as any)?.paymentPermitContext?.meta?.paymentId || '',
        nonce: accountInfo.nonce.toString(),
        validAfter: (extensions as any)?.paymentPermitContext?.meta?.validAfter || 0,
        validBefore: Number(deadline),
      },
      buyer: userAddress,
      caller: domain.verifyingContract, 
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
