/**
 * Tests for X402Client
 */

import { describe, it, expect, vi } from 'vitest';
import { X402Client } from '../client';
import type { ClientMechanism } from '../client';
import type { PaymentRequirements } from '../types';

class MockClientMechanism implements ClientMechanism {
  scheme(): string {
    return 'exact';
  }

  async createPaymentPayload(): Promise<any> {
    return { mock: 'payload' };
  }
}

describe('X402Client', () => {
  it('should create client instance', () => {
    const client = new X402Client();
    expect(client).toBeDefined();
  });

  it('should register mechanism', () => {
    const client = new X402Client();
    const mechanism = new MockClientMechanism();

    const result = client.register('tron:shasta', mechanism);
    expect(result).toBe(client); // Should return self for chaining
  });

  it('should select payment requirements from multiple networks', () => {
    const client = new X402Client();

    const accepts: PaymentRequirements[] = [
      {
        scheme: 'exact',
        network: 'tron:shasta',
        amount: '1000000',
        asset: 'TTestUSDT',
        payTo: 'TTestMerchant',
      },
      {
        scheme: 'exact',
        network: 'eip155:8453',
        amount: '1000000',
        asset: '0xTestUSDC',
        payTo: '0xTestMerchant',
      },
    ];

    const selected = client.selectPaymentRequirements(accepts);
    expect(['tron:shasta', 'eip155:8453']).toContain(selected.network);
  });

  it('should select TRON payment requirements with filter', () => {
    const client = new X402Client();

    const accepts: PaymentRequirements[] = [
      {
        scheme: 'exact',
        network: 'tron:shasta',
        amount: '1000000',
        asset: 'TTestUSDT',
        payTo: 'TTestMerchant',
      },
      {
        scheme: 'exact',
        network: 'eip155:8453',
        amount: '1000000',
        asset: '0xTestUSDC',
        payTo: '0xTestMerchant',
      },
    ];

    const selected = client.selectPaymentRequirements(accepts, {
      network: 'tron:shasta',
    });
    expect(selected.network).toBe('tron:shasta');
  });

  it('should select EVM payment requirements with filter', () => {
    const client = new X402Client();

    const accepts: PaymentRequirements[] = [
      {
        scheme: 'exact',
        network: 'tron:shasta',
        amount: '1000000',
        asset: 'TTestUSDT',
        payTo: 'TTestMerchant',
      },
      {
        scheme: 'exact',
        network: 'eip155:8453',
        amount: '1000000',
        asset: '0xTestUSDC',
        payTo: '0xTestMerchant',
      },
    ];

    const selected = client.selectPaymentRequirements(accepts, {
      network: 'eip155:8453',
    });
    expect(selected.network).toBe('eip155:8453');
  });

  it('should create payment payload', async () => {
    const client = new X402Client();
    const mechanism = new MockClientMechanism();
    client.register('tron:shasta', mechanism);

    const requirements: PaymentRequirements = {
      scheme: 'exact',
      network: 'tron:shasta',
      amount: '1000000',
      asset: 'TTestUSDT',
      payTo: 'TTestMerchant',
    };

    const payload = await client.createPaymentPayload(
      requirements,
      'https://example.com/resource'
    );
    expect(payload).toEqual({ mock: 'payload' });
  });
});
