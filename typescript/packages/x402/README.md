# @sun-protocol/tvm-x402

tvm-x402 TypeScript SDK (TRON-only).

## Install

```bash
npm i @sun-protocol/tvm-x402
```

## Peer dependencies

This package expects `tronweb` to be provided by the host app.

```bash
npm i tronweb
```

## Usage

```ts
import TronWeb from "tronweb";

// Provide your own TronWeb instance / configuration.
const tronWeb = new TronWeb({
  fullHost: "https://api.trongrid.io",
});

// TODO: Add usage examples once the public API is finalized.
console.log("tronWeb ready", !!tronWeb);
```

## Links

- Repository: https://github.com/sun-protocol/tvm-x402
- Issues: https://github.com/sun-protocol/tvm-x402/issues
