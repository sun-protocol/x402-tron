# x402 TypeScript Client SDK

TypeScript Client SDK for x402 Payment Protocol.

## Packages

- `@x402/core` - Core client SDK with types and utilities
- `@x402/mechanism-tron` - TRON client mechanism
- `@x402/mechanism-evm` - EVM client mechanism
- `@x402/signer-tron` - TRON client signer
- `@x402/signer-evm` - EVM client signer
- `@x402/http-fetch` - Fetch-based HTTP client adapter

## Installation

```bash
# Install core package
pnpm add @x402/core

# Install chain-specific packages
pnpm add @x402/mechanism-tron @x402/signer-tron
# or
pnpm add @x402/mechanism-evm @x402/signer-evm

# Install HTTP adapter
pnpm add @x402/http-fetch
```

## Quick Start

```typescript
import { X402Client } from '@x402/core';
import { UptoTronClientMechanism } from '@x402/mechanism-tron';
import { TronClientSigner } from '@x402/signer-tron';
import { X402FetchClient } from '@x402/http-fetch';

// 1. Create signer
const signer = TronClientSigner.fromPrivateKey('your_private_key');

// 2. Create X402Client and register mechanisms
const x402Client = new X402Client()
  .register('tron:*', new UptoTronClientMechanism(signer));

// 3. Create HTTP client with automatic 402 handling
const client = new X402FetchClient(x402Client);

// 4. Make requests - 402 payments handled automatically
const response = await client.get('https://api.example.com/premium-data');
console.log(await response.json());
```

## Development

```bash
# Install dependencies
pnpm install

# Build all packages
pnpm build

# Run tests
pnpm test
```

## License

MIT License
