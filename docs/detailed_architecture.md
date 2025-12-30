# Tron x402 架构设计文档

## 概述

Tron x402 是一个支付协议实现，支持多链（EVM、TRON、Solana）的去中心化支付系统。本文档描述了整体架构设计、代码组织结构和核心设计原则。

---

## 代码目录结构

```
tron-x402/
├── typescript/                      # TypeScript Client SDK
│   ├── packages/
│   │   ├── core/                   # 核心包
│   │   │   └── src/
│   │   │       ├── client/
│   │   │       │   ├── index.ts
│   │   │       │   └── x402Client.ts        # X402Client 核心类
│   │   │       ├── types/                   # 类型定义
│   │   │       │   ├── payment.ts           # PaymentPayload, PaymentRequirements
│   │   │       │   └── responses.ts         # PaymentRequired, VerifyResponse
│   │   │       ├── utils/                   # 工具函数
│   │   │       └── index.ts
│   │   │
│   │   ├── mechanisms/             # 基础组件：Client Mechanisms
│   │   │   ├── evm/                # EVM 链支持
│   │   │   │   └── src/
│   │   │   │       └── upto.ts     # UptoEvmClientMechanism
│   │   │   ├── tron/               # TRON 链支持
│   │   │   │   └── src/
│   │   │   │       └── upto.ts     # UptoTronClientMechanism
│   │   │   └── svm/                # Solana 链支持
│   │   │       └── src/
│   │   │           └── upto.ts     # UptoSolanaClientMechanism
│   │   │
│   │   ├── signers/                # 基础组件：Client Signers
│   │   │   ├── evm/                # EVM 链签名器
│   │   │   │   └── src/
│   │   │   │       └── signer.ts   # EvmClientSigner
│   │   │   ├── tron/               # TRON 链签名器
│   │   │   │   └── src/
│   │   │   │       └── signer.ts   # TronClientSigner
│   │   │   └── svm/                # Solana 链签名器
│   │   │       └── src/
│   │   │           └── signer.ts   # SolanaClientSigner
│   │   │
│   │   └── http/                   # HTTP 适配层
│   │       ├── axios/              # Axios 客户端适配
│   │       ├── fetch/              # Fetch API 适配
│   │       └── paywall/            # Paywall 组件
│   │
│   ├── package.json
│   ├── pnpm-workspace.yaml
│   └── tsconfig.base.json
│
├── python/                          # Python SDK (Client + Server + Facilitator)
│   └── x402/
│       ├── src/
│       │   └── x402/
│       │       ├── __init__.py
│       │       │
│       │       ├── clients/        # Client SDK
│       │       │   ├── __init__.py
│       │       │   ├── x402_client.py       # X402Client 核心类
│       │       │   └── x402_http_client.py  # X402HttpClient HTTP 适配器
│       │       │
│       │       ├── server/          # Server SDK (Python only)
│       │       │   ├── __init__.py
│       │       │   ├── x402_server.py       # X402Server 核心类
│       │       │   └── facilitator_client.py # FacilitatorClient
│       │       │
│       │       ├── facilitator/     # Facilitator SDK (Python only)
│       │       │   ├── __init__.py
│       │       │   └── x402_facilitator.py  # X402Facilitator 核心类
│       │       │
│       │       ├── mechanisms/      # 基础组件：Mechanisms（跨 SDK 共享）
│       │       │   ├── __init__.py
│       │       │   ├── client/      # Client Mechanisms
│       │       │   │   ├── __init__.py
│       │       │   │   ├── base.py          # ClientMechanism 接口
│       │       │   │   ├── evm_upto.py      # UptoEvmClientMechanism
│       │       │   │   ├── tron_upto.py     # UptoTronClientMechanism
│       │       │   │   └── solana_upto.py   # UptoSolanaClientMechanism
│       │       │   ├── server/      # Server Mechanisms
│       │       │   │   ├── __init__.py
│       │       │   │   ├── base.py          # ServerMechanism 接口
│       │       │   │   ├── evm_upto.py      # UptoEvmServerMechanism
│       │       │   │   ├── tron_upto.py     # UptoTronServerMechanism
│       │       │   │   └── solana_upto.py   # UptoSolanaServerMechanism
│       │       │   └── facilitator/ # Facilitator Mechanisms
│       │       │       ├── __init__.py
│       │       │       ├── base.py          # FacilitatorMechanism 接口
│       │       │       ├── evm_upto.py      # UptoEvmFacilitatorMechanism
│       │       │       ├── tron_upto.py     # UptoTronFacilitatorMechanism
│       │       │       └── solana_upto.py   # UptoSolanaFacilitatorMechanism
│       │       │
│       │       ├── signers/         # 基础组件：Signers（跨 SDK 共享）
│       │       │   ├── __init__.py
│       │       │   ├── client/      # Client Signers
│       │       │   │   ├── __init__.py
│       │       │   │   ├── base.py          # ClientSigner 接口
│       │       │   │   ├── evm_signer.py    # EvmClientSigner
│       │       │   │   ├── tron_signer.py   # TronClientSigner
│       │       │   │   └── solana_signer.py # SolanaClientSigner
│       │       │   └── facilitator/ # Facilitator Signers
│       │       │       ├── __init__.py
│       │       │       ├── base.py          # FacilitatorSigner 接口
│       │       │       ├── evm_signer.py    # EvmFacilitatorSigner
│       │       │       ├── tron_signer.py   # TronFacilitatorSigner
│       │       │       └── solana_signer.py # SolanaFacilitatorSigner
│       │       │
│       │       ├── fastapi/         # FastAPI 中间件
│       │       │   ├── __init__.py
│       │       │   └── middleware.py
│       │       │
│       │       ├── flask/           # Flask 扩展
│       │       │   ├── __init__.py
│       │       │   └── extension.py
│       │       │
│       │       ├── types.py         # 类型定义
│       │       ├── common.py        # 通用工具
│       │       ├── encoding.py      # 编解码工具
│       │       ├── chains.py        # 链配置
│       │       └── networks.py      # 网络定义
│       │
│       ├── tests/                   # 测试代码
│       ├── pyproject.toml           # Python 项目配置
│       └── README.md
│
└── README.md
```

### 目录结构说明

#### 基础组件架构（Mechanisms & Signers）

**设计原则：**
- `mechanisms/` 和 `signers/` 作为**基础组件**，与 `clients/`、`server/`、`facilitator/` 平级
- 按角色分类：`mechanisms/client/`、`mechanisms/server/`、`mechanisms/facilitator/`
- 按角色分类：`signers/client/`、`signers/facilitator/`（Server 不需要 signer）
- **优势**：
  - 避免代码重复，提高复用性
  - 清晰的分层架构：基础组件 + 应用层
  - 便于跨 SDK 共享和维护

#### TypeScript Client SDK (`typescript/`)
- **范围**：仅包含 Client 功能
- **架构**：使用 monorepo 结构（pnpm workspace）
- **HTTP 适配**：支持多种客户端（axios、fetch、paywall）
- **区块链支持**：EVM、TRON 和 Solana 链
- **基础组件**：`mechanisms/` 和 `signers/` 按链分包（evm、tron、svm）

#### Python SDK (`python/x402/`)
- **范围**：包含 Client、Server、Facilitator 三个完整 SDK
- **Client**：与 TypeScript 版本功能对等
- **Server/Facilitator**：仅提供 Python 版本
- **框架集成**：支持 FastAPI 和 Flask

#### 跨语言协作
- TypeScript Client ↔ Python Server/Facilitator
- Python Client ↔ 任何语言的 Server/Facilitator
- 所有实现遵循统一的 x402 协议规范

---