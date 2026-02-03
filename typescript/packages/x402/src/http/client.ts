/**
 * X402FetchClient - 基于 Fetch 的具有自动 402 支付处理的 HTTP 客户端
 */

import {
  X402Client,
  PaymentRequired,
  PaymentPayload,
  PaymentRequirementsSelector,
  encodePaymentPayload,
  decodePaymentPayload,
} from '../index.js';

/** x402 协议的 HTTP 头 */
const PAYMENT_SIGNATURE_HEADER = 'PAYMENT-SIGNATURE';
const PAYMENT_REQUIRED_HEADER = 'PAYMENT-REQUIRED';
const PAYMENT_RESPONSE_HEADER = 'PAYMENT-RESPONSE';

/**
 * 基于 Fetch 的具有自动 402 支付处理的 HTTP 客户端
 */
export class X402FetchClient {
  private x402Client: X402Client;
  private selector?: PaymentRequirementsSelector;

  constructor(
    x402Client: X402Client,
    selector?: PaymentRequirementsSelector
  ) {
    this.x402Client = x402Client;
    this.selector = selector;
  }

  /**
   * 发起具有自动 402 支付处理的请求
   */
  async request(
    url: string,
    init?: RequestInit
  ): Promise<Response> {
    const response = await fetch(url, init);

    if (response.status !== 402) {
      return response;
    }

    const paymentRequired = await this.parsePaymentRequired(response);
    if (!paymentRequired) {
      return response;
    }

    const paymentPayload = await this.x402Client.handlePayment(
      paymentRequired.accepts,
      url,
      paymentRequired.extensions,
      this.selector
    );

    return this.retryWithPayment(url, init, paymentPayload);
  }

  /**
   * 带支付处理的 GET 请求
   */
  async get(url: string, init?: RequestInit): Promise<Response> {
    return this.request(url, { ...init, method: 'GET' });
  }

  /**
   * 带支付处理的 POST 请求
   */
  async post(url: string, body?: RequestInit['body'], init?: RequestInit): Promise<Response> {
    return this.request(url, { ...init, method: 'POST', body });
  }

  /**
   * 从 402 响应解析 PaymentRequired
   */
  private async parsePaymentRequired(response: Response): Promise<PaymentRequired | null> {
    const headerValue = response.headers.get(PAYMENT_REQUIRED_HEADER);
    if (headerValue) {
      try {
        return decodePaymentPayload<PaymentRequired>(headerValue);
      } catch {
        // 继续解析主体
      }
    }

    try {
      const body = await response.json() as Record<string, unknown>;
      if (body.accepts && Array.isArray(body.accepts)) {
        return body as unknown as PaymentRequired;
      }
    } catch {
      // 无法解析
    }

    return null;
  }

  /**
   * 使用支付载荷重试请求
   */
  private async retryWithPayment(
    url: string,
    init: RequestInit | undefined,
    paymentPayload: PaymentPayload
  ): Promise<Response> {
    const encodedPayload = encodePaymentPayload(paymentPayload);
    
    const headers = new Headers(init?.headers);
    headers.set(PAYMENT_SIGNATURE_HEADER, encodedPayload);

    return fetch(url, {
      ...init,
      headers,
    });
  }
}
