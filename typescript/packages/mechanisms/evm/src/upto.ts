/**
 * UptoEvmClientMechanism - EVM client mechanism for "upto" payment scheme
 */

import type {
  ClientMechanism,
  ClientSigner,
  PaymentRequirements,
  PaymentPayload,
  PaymentPermit,
  PaymentPermitContext,
} from '@x402/core';
import {
  KIND_MAP,
  PAYMENT_PERMIT_TYPES,
  PAYMENT_PERMIT_PRIMARY_TYPE,
  getChainId,
  getPaymentPermitAddress,
  ZERO_ADDRESSES,
} from '@x402/core';

/**
 * EVM client mechanism for "upto" payment scheme
 */
export class UptoEvmClientMechanism implements ClientMechanism {
  private signer: ClientSigner;

  constructor(signer: ClientSigner) {
    this.signer = signer;
  }

  scheme(): string {
    return 'exact';
  }

  async createPaymentPayload(
    requirements: PaymentRequirements,
    resource: string,
    extensions?: { paymentPermitContext?: PaymentPermitContext }
  ): Promise<PaymentPayload> {
    const context = extensions?.paymentPermitContext;
    if (!context) {
      throw new Error('paymentPermitContext is required');
    }

    const buyerAddress = this.signer.getAddress();
    const zeroAddress = ZERO_ADDRESSES.evm;

    const permit: PaymentPermit = {
      meta: {
        kind: context.meta.kind,
        paymentId: context.meta.paymentId,
        nonce: context.meta.nonce,
        validAfter: context.meta.validAfter,
        validBefore: context.meta.validBefore,
      },
      buyer: buyerAddress,
      caller: requirements.extra?.fee?.feeTo || buyerAddress,
      payment: {
        payToken: requirements.asset,
        maxPayAmount: requirements.amount,
        payTo: requirements.payTo,
      },
      fee: {
        feeTo: requirements.extra?.fee?.feeTo || zeroAddress,
        feeAmount: requirements.extra?.fee?.feeAmount || '0',
      },
      delivery: {
        receiveToken: context.delivery.receiveToken,
        miniReceiveAmount: context.delivery.miniReceiveAmount,
        tokenId: context.delivery.tokenId,
      },
    };

    // Ensure allowance
    const totalAmount = BigInt(permit.payment.maxPayAmount) + BigInt(permit.fee.feeAmount);
    await this.signer.ensureAllowance(
      permit.payment.payToken,
      totalAmount,
      requirements.network
    );

    // Build EIP-712 domain (no version field per contract spec)
    const domain = {
      name: 'PaymentPermit',
      chainId: getChainId(requirements.network),
      verifyingContract: getPaymentPermitAddress(requirements.network),
    };

    // Convert permit to EIP-712 compatible format (kind: string -> uint8)
    const permitForSigning = {
      ...permit,
      meta: {
        ...permit.meta,
        kind: KIND_MAP[permit.meta.kind],
      },
    };

    const signature = await this.signer.signTypedData(
      domain,
      PAYMENT_PERMIT_TYPES,
      permitForSigning as unknown as Record<string, unknown>
    );

    return {
      x402Version: 2,
      resource: { url: resource },
      accepted: requirements,
      payload: {
        signature,
        paymentPermit: permit,
      },
      extensions: {},
    };
  }
}
