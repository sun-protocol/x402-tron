/**
 * Tests for core types
 */

import { describe, it, expect } from 'vitest';
import type {
  PaymentPermit,
  PaymentRequirements,
  PaymentPayload,
} from '../types';

describe('PaymentPermit', () => {
  it('should create a valid payment permit', () => {
    const permit: PaymentPermit = {
      meta: {
        kind: 'PAYMENT_ONLY',
        paymentId: 'test_id',
        nonce: '12345',
        validAfter: 1000,
        validBefore: 2000,
      },
      buyer: 'TTestBuyerAddress',
      caller: 'TTestCallerAddress',
      payment: {
        payToken: 'TTestTokenAddress',
        maxPayAmount: '1000000',
        payTo: 'TTestPayToAddress',
      },
      fee: {
        feeTo: 'TTestFeeAddress',
        feeAmount: '10000',
      },
      delivery: {
        receiveToken: 'T0000000000000000000000000000000',
        miniReceiveAmount: '0',
        tokenId: '0',
      },
    };

    expect(permit.buyer).toBe('TTestBuyerAddress');
    expect(permit.payment.maxPayAmount).toBe('1000000');
    expect(permit.meta.kind).toBe('PAYMENT_ONLY');
  });
});

describe('PaymentRequirements', () => {
  it('should create valid payment requirements', () => {
    const requirements: PaymentRequirements = {
      scheme: 'exact',
      network: 'tron:shasta',
      amount: '1000000',
      asset: 'TTestUSDTAddress',
      payTo: 'TTestMerchantAddress',
      maxTimeoutSeconds: 3600,
    };

    expect(requirements.scheme).toBe('exact');
    expect(requirements.network).toBe('tron:shasta');
    expect(requirements.amount).toBe('1000000');
  });
});

describe('PaymentPayload', () => {
  it('should create valid payment payload', () => {
    const payload: PaymentPayload = {
      x402Version: 2,
      accepted: {
        scheme: 'exact',
        network: 'tron:shasta',
        amount: '1000000',
        asset: 'TTestUSDT',
        payTo: 'TTestMerchant',
      },
      payload: {
        signature: '0xTestSignature',
        paymentPermit: {
          meta: {
            kind: 'PAYMENT_ONLY',
            paymentId: 'test_id',
            nonce: '12345',
            validAfter: 1000,
            validBefore: 2000,
          },
          buyer: 'TTestBuyer',
          caller: 'TTestCaller',
          payment: {
            payToken: 'TTestToken',
            maxPayAmount: '1000000',
            payTo: 'TTestPayTo',
          },
          fee: {
            feeTo: 'TTestFee',
            feeAmount: '10000',
          },
          delivery: {
            receiveToken: 'T0000000000000000000000000000000',
            miniReceiveAmount: '0',
            tokenId: '0',
          },
        },
      },
    };

    expect(payload.x402Version).toBe(2);
    expect(payload.payload.signature).toBe('0xTestSignature');
  });
});
