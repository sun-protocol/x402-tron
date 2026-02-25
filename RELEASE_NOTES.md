# v0.4.0 - GasFree Support & Signer Standardization

Release date: February 25, 2026

## Highlights

- **Full GasFree Integration**: Pay-per-request using TRC20 tokens (USDT/USDD) without requiring TRX for gas.
- **Domain Neutral Signers**: Core signers now support arbitrary EIP-712 / TIP-712 domains and primary types.
- **Enhanced Reliability**: New transaction polling mechanism with 3-minute timeout and "Confirmed on Chain" grace success detection.

## New Features

### GasFree Scheme (TRON)
- Automatic discovery of GasFree service providers.
- Asynchronous settlement via official HTTP Proxy.
- Real-time status tracking and polling.
- Transparent fee handling based on provider quotes.

### Standardized Signers
- Unified `sign_typed_data` and `verify_typed_data` interfaces across TRON and EVM.
- Explicit `primary_type` passing to ensure signature consistency.
- Pure passthrough mode for EIP-712 definitions.

## Migration Guide

### Signer Interface Change
The `sign_typed_data` and `verify_typed_data` methods now require an additional `primary_type` argument.

**Python:**
```python
# Old
await signer.sign_typed_data(domain, types, message)
# New
await signer.sign_typed_data(domain, types, message, primary_type="YourType")
```

---

# v0.1.6 - TronGrid API Key support

Release date: February 6, 2026

## New Features

- Add TronGrid API key support to the tronpy client via `TRON_GRID_API_KEY`.

## Usage

Set the API key in your shell environment:

```bash
export TRON_GRID_API_KEY="your-api-key-here"
```