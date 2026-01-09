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

/** EIP-712 domain for EVM payment permit */
const PAYMENT_PERMIT_DOMAIN = {
  name: 'PaymentPermit',
  version: '1',
};

/** EIP-712 types for payment permit */
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
  PaymentPermit: [
    { name: 'meta', type: 'PermitMeta' },
    { name: 'buyer', type: 'address' },
    { name: 'caller', type: 'address' },
    { name: 'payment', type: 'Payment' },
    { name: 'fee', type: 'Fee' },
    { name: 'delivery', type: 'Delivery' },
  ],
};

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
        feeTo: requirements.extra?.fee?.feeTo || '0x0000000000000000000000000000000000000000',
        feeAmount: requirements.extra?.fee?.feeAmount || '0',
      },
      delivery: {
        receiveToken: context.delivery.receiveToken,
        miniReceiveAmount: context.delivery.miniReceiveAmount,
        tokenId: context.delivery.tokenId,
      },
    };

    const totalAmount = BigInt(permit.payment.maxPayAmount) + BigInt(permit.fee.feeAmount);
    await this.signer.ensureAllowance(
      permit.payment.payToken,
      totalAmount,
      requirements.network
    );

    const signature = await this.signer.signTypedData(
      PAYMENT_PERMIT_DOMAIN,
      PAYMENT_PERMIT_TYPES,
      permit as unknown as Record<string, unknown>
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
