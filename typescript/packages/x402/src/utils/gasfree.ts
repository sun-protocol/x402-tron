/**
 * GasFree utility functions for API interaction and domain helpers.
 */

const GASFREE_API_BASE_URL = 'https://api.gasfree.io/v1';

export interface GasFreeResponse<T> {
  code: number;
  reason: string | null;
  message: string | null;
  data: T;
}

export interface GasFreeAsset {
  tokenAddress: string;
  tokenSymbol: string;
  activateFee: number;
  transferFee: number;
  decimal: number;
  frozen: number;
  balance?: string | number;
}

export interface GasFreeAddressInfo {
  accountAddress: string;
  gasFreeAddress: string;
  active: boolean;
  nonce: number;
  allowSubmit: boolean;
  assets: GasFreeAsset[];
}

export interface GasFreeSubmitResponseData {
  id: string;
  state: string;
  // ... 其他字段
}

export class GasFreeAPIClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
  }

  /**
   * Get the current nonce and account info for a user
   * Official endpoint: GET /api/v1/address/{accountAddress}
   */
  async getNonce(user: string, _token: string, _chainId: number): Promise<number> {
    try {
      const data = await this.getAddressInfo(user);
      return data.nonce ?? 0;
    } catch (error) {
      console.warn(`Failed to get nonce from GasFree API: ${error}. Defaulting to 0.`);
      return 0;
    }
  }

  /**
   * Get full account info (activation, balance, nonce) for a user
   * Official endpoint: GET /api/v1/address/{accountAddress}
   */
  async getAddressInfo(user: string): Promise<GasFreeAddressInfo> {
    const url = `${this.baseUrl}/api/v1/address/${user}`;

    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    const result = (await response.json()) as GasFreeResponse<GasFreeAddressInfo>;
    if (result.code !== 200) {
      throw new Error(`API error: ${result.message || result.reason}`);
    }
    return result.data;
  }

  /**
   * Submit a signed GasFree transaction to the official relayer
   * Official endpoint: POST /api/v1/gasfree/submit
   */
  async submit(domain: any, message: any, signature: string): Promise<string> {
    const path = '/api/v1/gasfree/submit';
    const url = `${this.baseUrl}${path}`;
    
    // 官方 API 提交格式要求（基于文档 3.3 章节）
    const payload = {
      token: message.token,
      serviceProvider: message.serviceProvider,
      user: message.user,
      receiver: message.receiver,
      value: message.value.toString(),
      maxFee: message.maxFee.toString(),
      deadline: Number(message.deadline),
      version: Number(message.version),
      nonce: Number(message.nonce),
      sig: signature.startsWith('0x') ? signature.slice(2) : signature,
      requestId: `x402-${Date.now()}-${signature.slice(2, 10)}`,
    };

    try {
      // Note: TS SDK doesn't implement HMAC signing yet as it's primarily used in browser
      // where API Keys are not recommended. Facilitator (Python) handles the server-side signing.
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`HTTP error! status: ${response.status}, message: ${errorText}`);
      }

      const result = (await response.json()) as GasFreeResponse<GasFreeSubmitResponseData>;
      if (result.code !== 200) {
        throw new Error(`API error: ${result.message || result.reason}`);
      }
      // 返回 traceId (id)
      return result.data.id;
    } catch (error) {
      console.error(`Failed to submit GasFree transaction: ${error}`);
      throw error;
    }
  }
}
