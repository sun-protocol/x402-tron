"""
Environment Variable Validation

Validates required environment variables for e2e testing.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


@dataclass
class EnvConfig:
    """Environment configuration for e2e tests"""

    # Client keys
    client_evm_private_key: Optional[str] = None
    client_tron_private_key: Optional[str] = None

    # Server addresses
    server_evm_address: Optional[str] = None
    server_tron_address: Optional[str] = None

    # Facilitator keys
    facilitator_evm_private_key: Optional[str] = None
    facilitator_tron_private_key: Optional[str] = None

    # Contract addresses
    merchant_contract_address: Optional[str] = None
    usdt_token_address: Optional[str] = None

    # Service URLs (optional, can be auto-discovered)
    facilitator_url: Optional[str] = None
    server_url: Optional[str] = None

    @property
    def has_tron_config(self) -> bool:
        """Check if TRON configuration is available"""
        return bool(self.client_tron_private_key and self.merchant_contract_address)

    @property
    def has_evm_config(self) -> bool:
        """Check if EVM configuration is available"""
        return bool(self.client_evm_private_key and self.server_evm_address)

    def to_env_dict(self) -> dict[str, str]:
        """Convert to environment variable dict"""
        env = {}

        if self.client_tron_private_key:
            env["TRON_PRIVATE_KEY"] = self.client_tron_private_key
        if self.merchant_contract_address:
            env["MERCHANT_CONTRACT_ADDRESS"] = self.merchant_contract_address
        if self.usdt_token_address:
            env["USDT_TOKEN_ADDRESS"] = self.usdt_token_address
        if self.facilitator_url:
            env["FACILITATOR_URL"] = self.facilitator_url
        if self.server_url:
            env["SERVER_URL"] = self.server_url

        return env


def load_env_config(env_paths: Optional[list[Path]] = None) -> EnvConfig:
    """
    Load environment configuration from .env files.

    Args:
        env_paths: List of .env file paths to load (in order)

    Returns:
        EnvConfig with loaded values
    """
    if env_paths is None:
        # Default paths
        e2e_dir = Path(__file__).parent.parent
        project_root = e2e_dir.parent
        env_paths = [
            e2e_dir / ".env",
            project_root / ".env",
        ]

    # Load .env files
    for path in env_paths:
        if path.exists():
            load_dotenv(path)

    return EnvConfig(
        client_evm_private_key=os.getenv("CLIENT_EVM_PRIVATE_KEY"),
        client_tron_private_key=os.getenv("TRON_PRIVATE_KEY"),
        server_evm_address=os.getenv("SERVER_EVM_ADDRESS"),
        server_tron_address=os.getenv("SERVER_TRON_ADDRESS"),
        facilitator_evm_private_key=os.getenv("FACILITATOR_EVM_PRIVATE_KEY"),
        facilitator_tron_private_key=os.getenv("TRON_PRIVATE_KEY"),  # Same key for now
        merchant_contract_address=os.getenv("MERCHANT_CONTRACT_ADDRESS"),
        usdt_token_address=os.getenv(
            "USDT_TOKEN_ADDRESS", "TXYZopYRdj2D9XRtbG411XZZ3kM5VkAeBf"
        ),
        facilitator_url=os.getenv("FACILITATOR_URL"),
        server_url=os.getenv("SERVER_URL"),
    )


def validate_env_config(config: EnvConfig) -> tuple[bool, list[str]]:
    """
    Validate environment configuration.

    Args:
        config: Environment configuration

    Returns:
        Tuple of (is_valid, list of missing/invalid items)
    """
    issues = []

    # Check for at least one chain configuration
    if not config.has_tron_config and not config.has_evm_config:
        issues.append("No chain configuration found (need TRON or EVM)")

    # TRON specific checks
    if config.client_tron_private_key:
        if len(config.client_tron_private_key) != 64:
            issues.append("TRON_PRIVATE_KEY should be 64 hex characters")
        if not config.merchant_contract_address:
            issues.append("MERCHANT_CONTRACT_ADDRESS required for TRON")

    # EVM specific checks
    if config.client_evm_private_key:
        key = config.client_evm_private_key
        if key.startswith("0x"):
            key = key[2:]
        if len(key) != 64:
            issues.append("CLIENT_EVM_PRIVATE_KEY should be 64 hex characters")

    return len(issues) == 0, issues


def print_env_status(config: EnvConfig):
    """Print environment configuration status"""
    print("\n" + "=" * 60)
    print("E2E Environment Configuration")
    print("=" * 60)

    # TRON
    print("\nTRON Configuration:")
    print(
        f"  Private Key: {'✓ Set' if config.client_tron_private_key else '✗ Missing'}"
    )
    print(
        f"  Merchant Contract: {'✓ ' + config.merchant_contract_address if config.merchant_contract_address else '✗ Missing'}"
    )
    print(
        f"  USDT Token: {'✓ ' + config.usdt_token_address if config.usdt_token_address else '✗ Missing'}"
    )

    # EVM
    print("\nEVM Configuration:")
    print(f"  Private Key: {'✓ Set' if config.client_evm_private_key else '✗ Missing'}")
    print(
        f"  Server Address: {'✓ ' + config.server_evm_address if config.server_evm_address else '✗ Missing'}"
    )

    # Services
    print("\nService URLs:")
    print(f"  Facilitator: {config.facilitator_url or '(auto-discover)'}")
    print(f"  Server: {config.server_url or '(auto-discover)'}")

    print("=" * 60 + "\n")
