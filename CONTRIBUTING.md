# Contributing to x402

First off, thank you for considering contributing to x402! It's people like you who make x402 such a great tool.

## Code of Conduct

By participating in this project, you agree to abide by our Code of Conduct. We expect all contributors to maintain a professional and respectful environment.

## How Can I Contribute?

### Reporting Bugs

- Use a clear and descriptive title for the issue to identify the problem.
- Describe the exact steps which reproduce the problem in as many details as possible.
- Provide specific examples to demonstrate the steps.
- Describe the behavior you observed after following the steps and point out what exactly is the problem with that behavior.
- Explain which behavior you expected to see instead and why.

### Suggesting Enhancements

- Use a clear and descriptive title for the issue to identify the suggestion.
- Provide a step-by-step description of the suggested enhancement in as many details as possible.
- Explain why this enhancement would be useful to most x402 users.

### Pull Requests

- Fill in the required template (if available).
- Do not include more than one fix/feature per pull request.
- Ensure that the tests pass and the code adheres to the project's coding standards.
- Update the documentation if you've made changes to the API or added new features.

---

## Development Setup

### Prerequisites

- **Python**: 3.10+
- **Node.js**: 18+
- **pnpm**: Recommended for TypeScript development.
- **A TRON Wallet**: (e.g., TronLink) with TRX for gas/energy on Nile or Shasta testnets.

### Repository Structure

- **Python SDK**: `python/x402/`
- **TypeScript SDK**: `typescript/packages/x402/`

---

## Python Development (`python/x402/`)

### Setup

```bash
cd python/x402
pip install -e .[all]
```

### Development Commands

- **Test**:
  - Run all tests: `pytest`
  - Run single test file: `pytest tests/client/test_tron_client.py`
- **Lint & Format**:
  - Check: `ruff check .`
  - Format: `ruff format .`

### Coding Standards

- **Naming**: Use `snake_case` for files, variables, and functions. Use `PascalCase` for classes and `UPPER_CASE` for constants.
- **Typing**: Use strict typing with the `typing` module (`Protocol`, `list[...]`, `str | None`).
- **Docstrings**: Use Google style docstrings (Args, Returns, Raises).
- **Async**: Use `async`/`await` for I/O bound operations.
- **Logging**: Use `logger = logging.getLogger(__name__)`.

---

## TypeScript Development (`typescript/packages/x402/`)

### Setup

```bash
cd typescript/packages/x402
npm install
```

### Development Commands

- **Build**: `npm run build`
- **Test**: `npm test`
- **Lint**: Use `tsc` during build or any project-specific lint scripts in `package.json`.

### Coding Standards

- **Naming**: Use `camelCase` for files, variables, and methods. Use `PascalCase` for classes and interfaces.
- **Imports**: **Always include `.js` extension** for relative imports (e.g., `import { Foo } from './foo.js';`).
- **Typing**: Use explicit interfaces for all public APIs. Avoid `any`.
- **Async**: Use `Promise<T>` and `async`/`await`.

---

## Testing Guidelines

1. **Write Tests First**: Create a reproduction test case before fixing bugs.
2. **Mocking**: Mock external network calls (RPC, HTTP). Do not make real chain requests in unit tests.
3. **Safety**: Never print or log private keys or secrets in test output.

## Security

- **Secrets**: Never commit `.env` files or hardcode secrets.
- **Logging**: Sanitize logs. Do not log raw private keys or sensitive payloads.
- **Vulnerabilities**: If you find a security vulnerability, please do not open a public issue. Instead, contact the maintainers directly.

## License

By contributing, you agree that your contributions will be licensed under its [MIT License](./LICENSE).
