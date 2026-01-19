# AGENTS.md

## Project overview

x402 is a decentralized pay-per-request protocol.

- Client signs `PaymentPermit`
- Server validates
- Facilitator settles

Supported chains: EVM, TRON

## Working style

- ALWAYS USE PARALLEL TOOLS WHEN APPLICABLE.

## Repo structure

- Python SDK: `python/x402/src/x402/` (Client + Server + Facilitator)
- TypeScript SDK: `typescript/packages/` (Client only)
- Architecture: SDK → Mechanisms/Signers → Utils

## Naming conventions

- Mechanisms: `Upto{Chain}{Role}Mechanism` (e.g., `UptoEvmClientMechanism`)
- Signers: `{Chain}{Role}Signer` (e.g., `TronClientSigner`)
- SDK: `X402{Role}` (e.g., `X402Client`)
- Files: `snake_case.py` (Python), `camelCase.ts` (TypeScript)

## Security considerations

- Do not commit private keys, seed phrases, API keys, or signing secrets
- Use environment variables (or local config files) for secrets; keep examples sanitized
- Avoid printing sensitive data (e.g., raw signatures, permits) in logs and tests

## PR checklist

- Run `ruff format .` and `pytest` before committing
- Update tests and docs
- Title: `[x402] <description>`
- Write tests first
