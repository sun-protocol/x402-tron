import { describe, it, expect, vi, beforeEach } from 'vitest';
import { GasFreeAPIClient } from './gasfree.js';

describe('GasFreeAPIClient', () => {
  const baseUrl = 'https://api.example.com';
  let client: GasFreeAPIClient;

  beforeEach(() => {
    client = new GasFreeAPIClient(baseUrl);
    vi.stubGlobal('fetch', vi.fn());
  });

  it('should get address info', async () => {
    const mockResponse = {
      code: 200,
      data: {
        accountAddress: '0x123',
        gasFreeAddress: '0x456',
        active: true,
        nonce: 5,
        assets: [],
      },
    };

    (fetch as any).mockResolvedValue({
      ok: true,
      json: async () => mockResponse,
    });

    const info = await client.getAddressInfo('0x123');
    expect(info.gasFreeAddress).toBe('0x456');
    expect(info.nonce).toBe(5);
    expect(fetch).toHaveBeenCalledWith(`${baseUrl}/api/v1/address/0x123`);
  });

  it('should submit transaction', async () => {
    const mockResponse = {
      code: 200,
      data: { id: 'trace-123' },
    };

    (fetch as any).mockResolvedValue({
      ok: true,
      json: async () => mockResponse,
    });

    const message = {
      token: '0xtoken',
      serviceProvider: '0xprovider',
      user: '0xuser',
      receiver: '0xreceiver',
      value: 100,
      maxFee: 10,
      deadline: 1000,
      version: 1,
      nonce: 1,
    };

    const traceId = await client.submit({}, message, '0xabc');
    expect(traceId).toBe('trace-123');
    expect(fetch).toHaveBeenCalledWith(
      `${baseUrl}/api/v1/gasfree/submit`,
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      })
    );
  });

  it('should get nonce', async () => {
    vi.spyOn(client, 'getAddressInfo').mockResolvedValue({
      nonce: 42,
    } as any);

    const nonce = await client.getNonce('0x123');
    expect(nonce).toBe(42);
  });
});
