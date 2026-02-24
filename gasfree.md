# GasFree Protocol Specification

GasFree 是一个基于 TRON 网络的分散式免 Gas 转账协议，旨在解决用户在转账 TRC20 代币时因缺少原生 TRX 而无法支付手续费的问题。

## 1. 核心机制

GasFree 通过以下机制实现免 Gas 转账：

*   **GasFree 地址 (Counterfactual Address)**：基于用户的 TRON 钱包地址，通过确定性算法生成的合约地址。用户可以将代币发送到该地址，甚至在合约实际部署之前。
*   **TIP-712 签名授权**：用户对转账信息进行结构化签名（TIP-712），授权 Service Provider 执行转账。
*   **服务提供商 (Service Provider)**：代付 TRX 手续费并将交易提交到链上的实体。作为回报，Service Provider 可以从用户的转账金额中扣除一定比例的代币作为手续费（不超过 `maxFee`）。
*   **GasFreeController**：链上合约，负责验证用户签名并执行转账逻辑。

## 2. 核心参数说明

在组装 GasFree 交易时，需要以下参数：

| 参数 | 说明 |
| :--- | :--- |
| `token` | 转账的 TRC20 代币合约地址 |
| `serviceProvider` | 指定的服务提供商地址（Relayer） |
| `user` | 用户的原始 TRON 钱包地址（非 GasFree 地址） |
| `receiver` | 接收者地址（可以是钱包地址或 GasFree 地址） |
| `value` | 转账金额（不含手续费，raw amount） |
| `maxFee` | 愿意支付给 Service Provider 的最大手续费金额 |
| `deadline` | 交易截止时间戳（秒） |
| `nonce` | 用户的 GasFree 交易流水号，用于防止重放攻击 |
| `version` | 签名算法版本，当前为 `1` |

## 3. SDK 使用指南

### 3.1 安装

```bash
npm install @gasfree/gasfree-sdk
```

### 3.2 初始化

根据网络选择对应的 `chainId`：

```typescript
import { TronGasFree } from '@gasfree/gasfree-sdk';

// 主网 (Mainnet)
const tronGasFree = new TronGasFree({
  chainId: Number('0x2b6653dc'),
});

// Nile 测试网
// chainId: Number('0xcd8690dc')

// Shasta 测试网
// chainId: Number('0x94a9059e')
```

### 3.3 生成 GasFree 地址

用户的代币应存放在此地址中：

```typescript
const userAddress = 'T...'; // 用户的 TRON 钱包地址
const gasFreeAddress = tronGasFree.generateGasFreeAddress(userAddress);
console.log('GasFree Address:', gasFreeAddress);
```

### 3.4 组装并签署交易

#### 标准钱包签名 (TIP-712)

```typescript
import TronWeb from 'tronweb';

const txParams = {
  token: 'TR7NHqjeKQxGChJ8V7AR1z4PDPrgZ5GT7m', // USDT
  serviceProvider: 'T...', // 服务商地址
  user: userAddress,
  receiver: 'T...', // 接收者
  value: '1000000', // 1 USDT (6位小数)
  maxFee: '100000',  // 最高 0.1 USDT 手续费
  deadline: Math.floor(Date.now() / 1000) + 3600,
  version: '1',
  nonce: '0',
};

const { domain, types, message } = tronGasFree.assembleGasFreeTransactionJson(txParams);

// 使用 TronWeb 进行签名
const signature = await TronWeb.Trx._signTypedData(domain, types, message, PRIVATE_KEY);
```

#### Ledger 硬件钱包签名

```typescript
const { permitTransferMessageHash } = tronGasFree.getGasFreeLedgerRawHash({
  message: txParams
});

// 使用 Ledger SDK 签署哈希
const res = await app.signTransactionHash(path, permitTransferMessageHash);
```

## 4. 流程演示

1.  **准备**：用户计算自己的 GasFree 地址并向其充值代币（如 USDT）。
2.  **签名**：用户在前端通过 SDK 生成签名，发送给 Service Provider。
3.  **结算**：Service Provider 调用 `GasFreeController` 合约。
4.  **执行**：合约验证签名有效性，将 `value` 发给接收者，将实际消耗的手续费（不超过 `maxFee`）发给 Service Provider。

## 5. 更多资源

*   官网: [https://gasfree.io](https://gasfree.io)
*   GitHub: [https://github.com/gasfreeio/gasfree-sdk-js](https://github.com/gasfreeio/gasfree-sdk-js)
