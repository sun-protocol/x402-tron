import { TronGasFree } from '@gasfree/gasfree-sdk';
import {
  PaymentPayload,
  PaymentRequirements,
  PaymentPermit,
  DeliveryKind,
  ClientMechanism,
  ClientSigner,
} from '../index.js';
import { getChainId } from '../config.js';

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

    // 1. Initialize GasFree SDK
    const gasFree = new TronGasFree({
      chainId,
    });

    // 2. Calculate GasFree address
    const gasfreeAddress = gasFree.generateGasFreeAddress(userAddress);

    // 3. Assemble parameters
    const context = (extensions?.paymentPermitContext as any) || {};
    const meta = context.meta || {};
    
    // Default maxFee to 0.1 USDT/USDD (10^5) if not provided
    const maxFee = requirements.extra?.fee?.feeAmount || '100000';
    const deadline = meta.validBefore || Math.floor(Date.now() / 1000) + 3600;
    
    // Nonce should ideally come from GasFree API if not provided
    // For now we use extensions or default to '0'
    const nonce = meta.nonce || '0';

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

    // 4. Get TIP-712 typed data
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
