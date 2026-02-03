"""
E2E Test Configuration with Real Service Management

This module provides:
- Environment configuration loading and validation
- Component discovery (clients, servers, facilitators)
- Service lifecycle management (start/stop)
- Async health checks
- Pytest fixtures for real service testing
"""

import asyncio
import os
import sys
import time
from pathlib import Path
from typing import Optional

import httpx
import pytest
from dotenv import load_dotenv

# Add e2e dir and x402 src to path before importing framework
_e2e_dir = Path(__file__).parent
_project_root = _e2e_dir.parent
sys.path.insert(0, str(_e2e_dir))
sys.path.insert(0, str(_project_root / "python" / "x402" / "src"))

from framework.discovery import (  # noqa: E402
    discover_clients,
    discover_servers,
    discover_facilitators,
)
from framework.env import (  # noqa: E402
    load_env_config,
    validate_env_config,
    print_env_status,
)
from framework.manager import (  # noqa: E402
    FacilitatorManager,
    ServerManager,
    ServiceOrchestrator,
)
from framework.scenarios import generate_test_scenarios  # noqa: E402

# =============================================================================
# Environment Configuration
# =============================================================================

_examples_dir = _project_root / "examples"

# Load environment
for env_path in [_e2e_dir / ".env", _project_root / ".env"]:
    if env_path.exists():
        load_dotenv(env_path)
        break

# Load and validate config
ENV_CONFIG = load_env_config()
ENV_VALID, ENV_ISSUES = validate_env_config(ENV_CONFIG)

# =============================================================================
# Network Configuration
# =============================================================================

TRON_NETWORK = "tron:nile"
TRON_PRIVATE_KEY = os.getenv("TRON_PRIVATE_KEY", "")
USDT_TOKEN_ADDRESS = os.getenv(
    "USDT_TOKEN_ADDRESS", "TXYZopYRdj2D9XRtbG411XZZ3kM5VkAeBf"
)
MERCHANT_CONTRACT_ADDRESS = os.getenv("MERCHANT_CONTRACT_ADDRESS", "")
FACILITATOR_ADDRESS = os.getenv("FACILITATOR_ADDRESS", "")

# Default service ports
DEFAULT_FACILITATOR_PORT = 8001
DEFAULT_SERVER_PORT = 8000

# =============================================================================
# Skip Conditions
# =============================================================================

SKIP_E2E = not TRON_PRIVATE_KEY or not MERCHANT_CONTRACT_ADDRESS
SKIP_REASON = "E2E tests require TRON_PRIVATE_KEY and MERCHANT_CONTRACT_ADDRESS"

# =============================================================================
# Global Service State
# =============================================================================

_orchestrator: Optional[ServiceOrchestrator] = None
_facilitator_manager: Optional[FacilitatorManager] = None
_server_manager: Optional[ServerManager] = None


# =============================================================================
# Pytest Hooks
# =============================================================================


def pytest_configure(config):
    """Register custom markers and print configuration."""
    config.addinivalue_line("markers", "e2e: end-to-end tests requiring testnet")


def pytest_collection_modifyitems(config, items):
    """Print test discovery summary and environment status."""
    e2e_count = sum(
        1 for item in items if "e2e" in [m.name for m in item.iter_markers()]
    )

    if items:
        print_env_status(ENV_CONFIG)

        print(f"\n{'=' * 60}")
        print("X402 E2E Test Suite")
        print(f"{'=' * 60}")
        print(f"Network: {TRON_NETWORK}")
        print(f"Tests discovered: {len(items)}")
        print(f"  - e2e: {e2e_count}")

        # Discover components
        clients = discover_clients(_examples_dir)
        servers = discover_servers(_examples_dir)
        facilitators = discover_facilitators(_examples_dir)

        print("\nDiscovered Components:")
        print(f"  - Clients: {[c.name for c in clients]}")
        print(f"  - Servers: {[s.name for s in servers]}")
        print(f"  - Facilitators: {[f.name for f in facilitators]}")

        if SKIP_E2E:
            print(f"\n⚠️  E2E tests will be skipped: {SKIP_REASON}")
        if ENV_ISSUES:
            print(f"\n⚠️  Environment issues: {ENV_ISSUES}")

        print(f"{'=' * 60}\n")


# =============================================================================
# Service Lifecycle Fixtures
# =============================================================================


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async fixtures."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def env_config():
    """Get environment configuration."""
    return ENV_CONFIG


@pytest.fixture(scope="session")
def discovered_components():
    """Discover all available components."""
    return {
        "clients": discover_clients(_examples_dir),
        "servers": discover_servers(_examples_dir),
        "facilitators": discover_facilitators(_examples_dir),
    }


@pytest.fixture(scope="session")
async def orchestrator():
    """
    Create and manage service orchestrator for the test session.

    Starts services at session start, stops at session end.
    """
    global _orchestrator

    if SKIP_E2E:
        pytest.skip(SKIP_REASON)

    _orchestrator = ServiceOrchestrator()
    yield _orchestrator

    # Cleanup
    await _orchestrator.stop_all()


@pytest.fixture(scope="module")
async def facilitator_service(orchestrator, discovered_components):
    """
    Start facilitator service for the test module.

    Returns:
        FacilitatorManager instance
    """
    global _facilitator_manager

    facilitators = discovered_components["facilitators"]
    if not facilitators:
        pytest.skip("No facilitator found")

    # Use first available facilitator
    component = facilitators[0]
    component.port = DEFAULT_FACILITATOR_PORT

    env = ENV_CONFIG.to_env_dict()
    _facilitator_manager = FacilitatorManager(component, env)

    success = await _facilitator_manager.start()
    if not success:
        pytest.skip(f"Failed to start facilitator: {component.name}")

    yield _facilitator_manager

    await _facilitator_manager.stop()


@pytest.fixture(scope="module")
async def server_service(orchestrator, discovered_components, facilitator_service):
    """
    Start server service for the test module.

    Depends on facilitator_service to ensure facilitator starts first.

    Returns:
        ServerManager instance
    """
    global _server_manager

    servers = discovered_components["servers"]
    if not servers:
        pytest.skip("No server found")

    # Use first available server
    component = servers[0]
    component.port = DEFAULT_SERVER_PORT

    env = ENV_CONFIG.to_env_dict()
    env["FACILITATOR_URL"] = facilitator_service.base_url

    _server_manager = ServerManager(component, env)

    success = await _server_manager.start()
    if not success:
        pytest.skip(f"Failed to start server: {component.name}")

    yield _server_manager

    await _server_manager.stop()


# =============================================================================
# HTTP Client Fixtures
# =============================================================================


@pytest.fixture(scope="module")
def http_client():
    """Create async HTTP client for API calls."""
    return httpx.AsyncClient(timeout=60.0)


@pytest.fixture
def facilitator_url(facilitator_service):
    """Get facilitator service URL."""
    return facilitator_service.base_url


@pytest.fixture
def server_url(server_service):
    """Get server service URL."""
    return server_service.base_url


# =============================================================================
# Signer Fixtures
# =============================================================================


@pytest.fixture(scope="module")
def tron_client_signer():
    """Create TRON client signer for payment signing."""
    if SKIP_E2E:
        pytest.skip(SKIP_REASON)

    from x402.signers.client import TronClientSigner

    return TronClientSigner.from_private_key(
        TRON_PRIVATE_KEY, network=TRON_NETWORK.split(":")[-1]
    )


@pytest.fixture(scope="module")
def tron_facilitator_signer():
    """Create TRON facilitator signer for verification and settlement."""
    if SKIP_E2E:
        pytest.skip(SKIP_REASON)

    from x402.signers.facilitator import TronFacilitatorSigner

    return TronFacilitatorSigner.from_private_key(
        TRON_PRIVATE_KEY, network=TRON_NETWORK.split(":")[-1]
    )


# =============================================================================
# Mechanism Fixtures
# =============================================================================


@pytest.fixture(scope="module")
def tron_client_mechanism(tron_client_signer):
    """Create TRON client mechanism for payment payload creation."""
    from x402.mechanisms.client import UptoTronClientMechanism

    return UptoTronClientMechanism(tron_client_signer)


@pytest.fixture(scope="module")
def tron_facilitator_mechanism(tron_facilitator_signer):
    """Create TRON facilitator mechanism for verification and settlement."""
    from x402.mechanisms.facilitator import UptoTronFacilitatorMechanism

    return UptoTronFacilitatorMechanism(
        tron_facilitator_signer,
        fee_to=tron_facilitator_signer.get_address(),
        base_fee=0,
    )


# =============================================================================
# Payment Fixtures
# =============================================================================


@pytest.fixture
def payment_requirements(tron_facilitator_signer):
    """Create standard payment requirements for testing."""
    from x402.types import FeeInfo, PaymentRequirements, PaymentRequirementsExtra

    return PaymentRequirements(
        scheme="exact",
        network=TRON_NETWORK,
        amount="1000000",  # 1 USDT (6 decimals)
        asset=USDT_TOKEN_ADDRESS,
        payTo=MERCHANT_CONTRACT_ADDRESS,
        extra=PaymentRequirementsExtra(
            fee=FeeInfo(feeTo=tron_facilitator_signer.get_address(), feeAmount="0")
        ),
    )


# =============================================================================
# Context Factory Fixtures
# =============================================================================


@pytest.fixture
def generate_permit_context():
    """Factory function for generating payment permit context."""
    from x402.types import PAYMENT_ONLY
    from x402.utils import generate_payment_id

    def _generate(
        kind: str = PAYMENT_ONLY,
        valid_before_offset_ms: int = 3600000,
        valid_after: int = 0,
        nonce: str | None = None,
        caller: str | None = None,
        receive_token: str = "T" + "0" * 33,
        mini_receive_amount: str = "0",
    ) -> dict:
        current_time_ms = int(time.time()) * 1000
        return {
            "paymentPermitContext": {
                "meta": {
                    "kind": kind,
                    "paymentId": generate_payment_id(),
                    "nonce": nonce or str(int(time.time())),
                    "validAfter": valid_after,
                    "validBefore": current_time_ms + valid_before_offset_ms,
                },
                "caller": caller,
                "delivery": {
                    "receiveToken": receive_token,
                    "miniReceiveAmount": mini_receive_amount,
                    "tokenId": "0",
                },
            }
        }

    return _generate


# =============================================================================
# Test Scenario Fixtures
# =============================================================================


@pytest.fixture(scope="session")
def test_scenarios(discovered_components):
    """Generate test scenarios from discovered components."""
    return generate_test_scenarios(
        clients=discovered_components["clients"],
        servers=discovered_components["servers"],
        facilitators=discovered_components["facilitators"],
        network_filter=TRON_NETWORK,
    )
