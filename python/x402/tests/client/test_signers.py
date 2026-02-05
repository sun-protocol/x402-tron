import pytest

from x402_tron.signers.client import TronClientSigner


def test_tron_signer_from_private_key():
    """测试从私钥创建 TRON 签名器"""
    private_key = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    signer = TronClientSigner.from_private_key(private_key)

    assert signer is not None
    assert signer.get_address().startswith("T")


def test_tron_signer_with_0x_prefix():
    """测试 TRON 签名器处理 0x 前缀"""
    private_key = "0x0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    signer = TronClientSigner.from_private_key(private_key)

    assert signer is not None
    assert signer.get_address().startswith("T")


'''
def test_evm_signer_from_private_key():
    """测试从私钥创建 EVM 签名器"""
    private_key = "0x0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    signer = EvmClientSigner.from_private_key(private_key)

    assert signer is not None
    assert signer.get_address().startswith("0x")
    assert len(signer.get_address()) == 42
'''

'''
def test_evm_signer_without_0x_prefix():
    """测试 EVM 签名器在缺少时添加 0x 前缀"""
    private_key = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    signer = EvmClientSigner.from_private_key(private_key)

    assert signer is not None
    assert signer.get_address().startswith("0x")
'''


@pytest.mark.anyio
async def test_tron_signer_check_allowance():
    """测试 TRON 签名器授权检查（无 tronpy）"""
    private_key = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    signer = TronClientSigner.from_private_key(private_key)

    # 没有 tronpy 客户端时，应该返回 0
    allowance = await signer.check_allowance("TTestToken", 1000000, "tron:shasta")
    assert allowance == 0


'''
@pytest.mark.asyncio
async def test_evm_signer_check_allowance():
    """测试 EVM 签名器授权检查（无 web3）"""
    private_key = "0x0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    signer = EvmClientSigner.from_private_key(private_key)

    # 没有 web3 客户端时，应该返回 0
    allowance = await signer.check_allowance(
        "0xTestToken", 1000000, "eip155:1"
    )
    assert allowance == 0
'''
