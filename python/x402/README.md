# x402-tron

Python SDK for the x402 payment protocol (TRON-only).

## Installation

```bash
pip install x402-tron
```

Optional extras:

```bash
pip install "x402-tron[tron]"
pip install "x402-tron[fastapi]"
pip install "x402-tron[flask]"
pip install "x402-tron[all]"
```

## Quick Start

```python
from bankofai.x402.clients import X402Client

client = X402Client()
```

If you want automatic handling of HTTP 402 responses, use `X402HttpClient`:

```python
import httpx

from bankofai.x402.clients import X402Client, X402HttpClient

x402_client = X402Client()
http_client = httpx.AsyncClient()
client = X402HttpClient(http_client=http_client, x402_client=x402_client)
```

## Links

- Repository: https://github.com/bankofai/x402-tron
- Issues: https://github.com/bankofai/x402-tron/issues
- Contributing: https://github.com/bankofai/CONTRIBUTING.md
