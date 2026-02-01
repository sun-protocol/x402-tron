"""
E2E Test Framework

Provides infrastructure for running end-to-end tests with real services:
- Process management (BaseProxy)
- Service discovery
- Scenario generation
- Health checks
- Environment validation
"""

from .proxy import BaseProxy, ProcessConfig, PythonServiceProxy
from .discovery import (
    discover_clients,
    discover_servers,
    discover_facilitators,
    discover_all,
    ComponentInfo,
)
from .manager import (
    FacilitatorManager,
    ServerManager,
    ServiceManager,
    ServiceOrchestrator,
)
from .scenarios import (
    TestScenario,
    generate_test_scenarios,
    minimize_scenarios,
    filter_scenarios_by_tag,
)
from .env import (
    EnvConfig,
    load_env_config,
    validate_env_config,
    print_env_status,
)

__all__ = [
    # Proxy
    "BaseProxy",
    "ProcessConfig",
    "PythonServiceProxy",
    # Discovery
    "discover_clients",
    "discover_servers",
    "discover_facilitators",
    "discover_all",
    "ComponentInfo",
    # Manager
    "FacilitatorManager",
    "ServerManager",
    "ServiceManager",
    "ServiceOrchestrator",
    # Scenarios
    "TestScenario",
    "generate_test_scenarios",
    "minimize_scenarios",
    "filter_scenarios_by_tag",
    # Environment
    "EnvConfig",
    "load_env_config",
    "validate_env_config",
    "print_env_status",
]
