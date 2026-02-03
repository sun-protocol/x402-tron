"""
E2E 端到端测试模块

使用真实测试网数据测试以下场景:
- 支付失效: 签名过期、金额/币种不符、Nonce 重放
- 交付模式: PAYMENT_ONLY
- 支付币: TRX
- 异常场景: RPC 超时、Facilitator 服务中断、网络抖动
- 链上限制: 余额/Gas 不足、合约执行回滚、授权失败

运行前需要配置环境变量:
- TRON_PRIVATE_KEY: TRON 测试网私钥
- MERCHANT_CONTRACT_ADDRESS: 商户合约地址
- USDT_TOKEN_ADDRESS: USDT 代币地址

运行命令:
    pytest tests/e2e/ -v --tb=short
"""
