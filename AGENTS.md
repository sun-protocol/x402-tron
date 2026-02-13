# AGENTS.md

## Project Overview

x402 is a decentralized pay-per-request protocol leveraging the HTTP `402 Payment Required` status code.
- **Client**: Signs `PaymentPermit` (TIP-712 structured data).
- **Server**: Validates permits and provides resources.
- **Facilitator**: Verifies and settles payments on-chain (TRON).

Supported chains: EVM, TRON. This repository focuses on the TRON implementation.

## Working Style & Ethics

- **Parallelism**: ALWAYS use parallel tool calls for independent tasks (e.g., searching and reading).
- **Test-Driven**: Write a reproduction test case before fixing bugs or adding features.
- **Minimalism**: Focus on "why" in comments. Keep PRs small (one fix/feature per PR).
- **Proactiveness**: Fix small issues (linting, types) in touched files proactively.
- **No Auto-Commits**: NEVER proactively commit changes to the git repository. You must only commit when explicitly asked by the user.

## Repository Structure

- `python/x402/`: Python SDK source, tests, and tools.
  - `src/x402_tron/`: Core TRON implementation (Signers, Mechanisms, SDK).
  - `src/x402/`: Generic utilities and base classes.
  - `tests/`: Organized by component (client, server, facilitator, utils).
- `typescript/packages/x402/`: TypeScript Client SDK.
  - `src/`: Signers, Mechanisms, and Fetch Client implementation.
- `scripts/`: Shared maintenance and deployment scripts.

## Development Commands

### Python (`python/x402/`)
- **Setup**: `pip install -e .[all]` (Includes `tron`, `fastapi`, `flask`).
- **Test All**: `pytest`
- **Single Test**: `pytest tests/path/to/test_file.py`
- **Single Case**: `pytest tests/path/to/test_file.py::test_function_name`
- **Lint**: `ruff check .`
- **Format**: `ruff format .`
- **Type Check**: `mypy .` (Strict mode is enabled in `pyproject.toml`).

### TypeScript (`typescript/packages/x402/`)
- **Setup**: `pnpm install` (preferred) or `npm install`
- **Build**: `npm run build` (runs `tsc`).
- **Test All**: `npm test` (Verify if tests exist in the specific package).
- **Single Test**: Use `vitest` or `jest` flags if available (check `package.json`).
- **Lint**: `npm run lint` (if available) or `tsc --noEmit`.

## Code Style Guidelines

### General
- **Naming Patterns**:
  - Mechanisms: `Exact{Chain}{Role}Mechanism` (e.g., `ExactTronClientMechanism`).
  - Signers: `{Chain}{Role}Signer` (e.g., `TronClientSigner`).
  - SDK Entrypoints: `X402{Role}` (e.g., `X402Client`, `X402Server`).
- **Async**: Use `async`/`await` for all I/O bound operations and blockchain interactions.

### Python Specific
- **Imports**: 
  - Group standard library, third-party, and local imports.
  - Use absolute imports (e.g., `from x402_tron.utils import ...`).
- **Naming**: `snake_case` for files, variables, and functions; `PascalCase` for classes; `UPPER_CASE` for constants.
- **Types**: MANDATORY strict typing using the `typing` module. Use `Protocol` for interfaces.
- **Docstrings**: Google style (Args, Returns, Raises).
- **Error Handling**: Define custom exceptions in `src/x402_tron/exceptions.py`. Wrap low-level blockchain errors in domain-specific exceptions.
- **Logging**: Use `logger = logging.getLogger(__name__)`.

### TypeScript Specific
- **Imports**: **CRITICAL: Relative imports MUST include the `.js` extension** (e.g., `import { X } from './utils.js'`). This is required for ESM compatibility.
- **Naming**: `camelCase` for files, variables, and methods; `PascalCase` for classes and interfaces.
- **Types**: Explicit interfaces for all public APIs. Avoid `any` at all costs. Use `Unknown` if type is truly dynamic.
- **Error Handling**: Use custom Error classes. Provide descriptive error messages.

## Security Considerations

- **Secret Management**:
  - NEVER commit private keys, seed phrases, or API keys.
  - Use `.env` files (ignored by git) for development secrets.
  - Sanitize all logs and test outputs to prevent leaking signatures or permits.
- **Blockchain Safety**:
  - Use dedicated wallets for development.
  - Always verify addresses and network IDs (`tron:mainnet`, `tron:nile`, `tron:shasta`).
  - Ensure transaction simulation or dry-runs where applicable.

## PR Checklist

1. **Tests**: Ensure new code is covered and existing tests pass.
2. **Linting**: Run `ruff format .` (Python) and verify TS builds.
3. **Docs**: Update `README.md` or inline docs if public APIs change.
4. **Commits**: Use descriptive messages; prefix with `[x402]`.
5. **No Secrets**: Double-check that no sensitive data is staged.

## Agent Specific Instructions

- When exploring, start by listing the root and then drilling into `python/x402/src/x402_tron` or `typescript/packages/x402/src`.
- If a tool call fails, analyze the error and try an alternative approach before asking for help.
- Always check `pyproject.toml` or `package.json` to verify dependencies before suggesting new ones.
