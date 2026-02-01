/**
 * UptoTronClientMechanism - TRON client mechanism for "upto" payment scheme
 *
 * Uses TIP-712 (TRON's EIP-712 implementation) for signing PaymentPermit.
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
  getChainId,
  getPaymentPermitAddress,
  TronAddressConverter,
  ZERO_ADDRESSES,
} from '@x402/core';

/**
 * TRON client mechanism for "upto" payment scheme
 */
export class UptoTronClientMechanism implements ClientMechanism {
  private signer: ClientSigner;
  private addressConverter = new TronAddressConverter();

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
    const zeroAddress = ZERO_ADDRESSES.evm; // Use EVM zero for signing

    const permit: PaymentPermit = {
      meta: {
        kind: context.meta.kind,
        paymentId: context.meta.paymentId,
        nonce: context.meta.nonce,
        validAfter: context.meta.validAfter,
        validBefore: context.meta.validBefore,
      },
      buyer: buyerAddress,
      caller: requirements.extra?.fee?.feeTo || zeroAddress,
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
        receiveToken: context.delivery.receiveToken || zeroAddress,
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
    const permitAddress = getPaymentPermitAddress(requirements.network);
    const domain = {
      name: 'PaymentPermit',
      chainId: getChainId(requirements.network),
      verifyingContract: this.addressConverter.toEvmFormat(permitAddress),
    };

    // Convert permit to EIP-712 compatible format:
    // 1. kind: string -> uint8
    // 2. All addresses: TRON Base58 -> EVM hex
    const permitForSigning = {
      meta: {
        kind: KIND_MAP[permit.meta.kind],
        paymentId: permit.meta.paymentId,
        nonce: permit.meta.nonce,
        validAfter: permit.meta.validAfter,
        validBefore: permit.meta.validBefore,
      },
      buyer: this.addressConverter.toEvmFormat(permit.buyer),
      caller: this.addressConverter.toEvmFormat(permit.caller),
      payment: {
        payToken: this.addressConverter.toEvmFormat(permit.payment.payToken),
        maxPayAmount: permit.payment.maxPayAmount,
        payTo: this.addressConverter.toEvmFormat(permit.payment.payTo),
      },
      fee: {
        feeTo: this.addressConverter.toEvmFormat(permit.fee.feeTo),
        feeAmount: permit.fee.feeAmount,
      },
      delivery: {
        receiveToken: this.addressConverter.toEvmFormat(permit.delivery.receiveToken),
        miniReceiveAmount: permit.delivery.miniReceiveAmount,
        tokenId: permit.delivery.tokenId,
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
