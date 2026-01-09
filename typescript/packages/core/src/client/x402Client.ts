/**
 * X402Client - x402 协议的核心支付客户端
 * 
 * 管理支付机制注册表并协调支付流程。
 */

import type {
  PaymentRequirements,
  PaymentPayload,
  PaymentPermitContext,
} from '../types/index.js';

/** 客户端机制接口 */
export interface ClientMechanism {
  /** 获取支付方案名称 */
  scheme(): string;
  
  /** 创建支付载荷 */
  createPaymentPayload(
    requirements: PaymentRequirements,
    resource: string,
    extensions?: { paymentPermitContext?: PaymentPermitContext }
  ): Promise<PaymentPayload>;
}

/** 客户端签名器接口 */
export interface ClientSigner {
  /** 获取签名器地址 */
  getAddress(): string;
  
  /** 签名原始消息 */
  signMessage(message: Uint8Array): Promise<string>;
  
  /** 签名类型化数据 (EIP-712) */
  signTypedData(
    domain: Record<string, unknown>,
    types: Record<string, unknown>,
    message: Record<string, unknown>
  ): Promise<string>;
  
  /** 检查代币授权 */
  checkAllowance(token: string, amount: bigint, network: string): Promise<bigint>;
  
  /** 确保足够的授权 */
  ensureAllowance(
    token: string,
    amount: bigint,
    network: string,
    mode?: 'auto' | 'interactive' | 'skip'
  ): Promise<boolean>;
}

/** 支付要求选择器函数 */
export type PaymentRequirementsSelector = (
  requirements: PaymentRequirements[]
) => PaymentRequirements;

/** 选择支付要求的过滤选项 */
export interface PaymentRequirementsFilter {
  scheme?: string;
  network?: string;
  maxAmount?: string;
}

/** 已注册的机制条目 */
interface MechanismEntry {
  pattern: string;
  mechanism: ClientMechanism;
  priority: number;
}

/**
 * X402Client - 核心支付客户端
 * 
 * 管理支付机制并协调支付流程。
 */
export class X402Client {
  private mechanisms: MechanismEntry[] = [];

  /**
   * 为网络模式注册支付机制
   * 
   * @param networkPattern - 网络模式（例如 "eip155:*", "tron:shasta"）
   * @param mechanism - 支付机制实例
   * @returns this 以支持链式调用
   */
  register(networkPattern: string, mechanism: ClientMechanism): X402Client {
    const priority = this.calculatePriority(networkPattern);
    this.mechanisms.push({
      pattern: networkPattern,
      mechanism,
      priority,
    });
    this.mechanisms.sort((a, b) => b.priority - a.priority);
    return this;
  }

  /**
   * 从可用选项中选择支付要求
   * 
   * @param accepts - 可用的支付要求
   * @param filters - 可选过滤器
   * @returns 选定的支付要求
   */
  selectPaymentRequirements(
    accepts: PaymentRequirements[],
    filters?: PaymentRequirementsFilter
  ): PaymentRequirements {
    let candidates = accepts;

    if (filters?.scheme) {
      candidates = candidates.filter(r => r.scheme === filters.scheme);
    }

    if (filters?.network) {
      candidates = candidates.filter(r => r.network === filters.network);
    }

    if (filters?.maxAmount) {
      const max = BigInt(filters.maxAmount);
      candidates = candidates.filter(r => BigInt(r.amount) <= max);
    }

    candidates = candidates.filter(r => this.findMechanism(r.network) !== null);

    if (candidates.length === 0) {
      throw new Error('No supported payment requirements found');
    }

    return candidates[0];
  }

  /**
   * 为给定要求创建支付载荷
   * 
   * @param requirements - 选定的支付要求
   * @param resource - 资源 URL
   * @param extensions - 可选扩展
   * @returns 支付载荷
   */
  async createPaymentPayload(
    requirements: PaymentRequirements,
    resource: string,
    extensions?: { paymentPermitContext?: PaymentPermitContext }
  ): Promise<PaymentPayload> {
    const mechanism = this.findMechanism(requirements.network);
    if (!mechanism) {
      throw new Error(`No mechanism registered for network: ${requirements.network}`);
    }

    return mechanism.createPaymentPayload(requirements, resource, extensions);
  }

  /**
   * 处理需要支付的响应
   * 
   * @param accepts - 可用的支付要求
   * @param resource - 资源 URL
   * @param extensions - 可选扩展
   * @param selector - 可选自定义选择器
   * @returns 支付载荷
   */
  async handlePayment(
    accepts: PaymentRequirements[],
    resource: string,
    extensions?: { paymentPermitContext?: PaymentPermitContext },
    selector?: PaymentRequirementsSelector
  ): Promise<PaymentPayload> {
    const requirements = selector
      ? selector(accepts)
      : this.selectPaymentRequirements(accepts);

    return this.createPaymentPayload(requirements, resource, extensions);
  }

  /**
   * 查找网络的机制
   */
  private findMechanism(network: string): ClientMechanism | null {
    for (const entry of this.mechanisms) {
      if (this.matchPattern(entry.pattern, network)) {
        return entry.mechanism;
      }
    }
    return null;
  }

  /**
   * 将网络与模式匹配
   */
  private matchPattern(pattern: string, network: string): boolean {
    if (pattern === network) return true;
    if (pattern.endsWith(':*')) {
      const prefix = pattern.slice(0, -1);
      return network.startsWith(prefix);
    }
    return false;
  }

  /**
   * 计算模式的优先级（更具体 = 更高优先级）
   */
  private calculatePriority(pattern: string): number {
    if (pattern.endsWith(':*')) return 1;
    return 10;
  }
}
