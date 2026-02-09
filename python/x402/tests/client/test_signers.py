import pytest

from x402_tron.signers.client import TronClientSigner, EvmClientSigner


def test_tron_signer_from_private_key():
    """Test creating TRON signer from private key"""
    private_key = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    signer = TronClientSigner.from_private_key(private_key)

    assert signer is not None
    assert signer.get_address().startswith("T")


def test_tron_signer_with_0x_prefix():
    """Test TRON signer handling 0x prefix"""
    private_key = "0x0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    signer = TronClientSigner.from_private_key(private_key)

    assert signer is not None
    assert signer.get_address().startswith("T")


def test_evm_signer_from_private_key():
    """Test creating EVM signer from private key"""
    private_key = "0x0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    signer = EvmClientSigner.from_private_key(private_key)

    assert signer is not None
    assert signer.get_address().startswith("0x")
    assert len(signer.get_address()) == 42


def test_evm_signer_without_0x_prefix():
    """Test EVM signer adding 0x prefix when missing"""
    private_key = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    signer = EvmClientSigner.from_private_key(private_key)

    assert signer is not None
    assert signer.get_address().startswith("0x")


@pytest.mark.anyio
async def test_tron_signer_check_allowance():
    """Test TRON signer allowance check (without tronpy)"""
    private_key = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    signer = TronClientSigner.from_private_key(private_key)

    # Should return 0 when no tronpy client available
    allowance = await signer.check_allowance("TTestToken", 1000000, "tron:shasta")
    assert allowance == 0


@pytest.mark.anyio
async def test_evm_signer_check_allowance():
    """Test EVM signer allowance check (without web3)"""
    private_key = "0x0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    signer = EvmClientSigner.from_private_key(private_key)

    # Should return 0 when no web3 client available
    allowance = await signer.check_allowance(
        "0xTestToken", 1000000, "eip155:1"
    )
    assert allowance == 0
