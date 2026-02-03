"""
Test Scenario Generation

Generates test scenarios from discovered components.
"""

from dataclasses import dataclass, field
from typing import Optional

from .discovery import ComponentInfo


@dataclass
class TestScenario:
    """A test scenario combining client, server, and facilitator"""

    name: str
    client: ComponentInfo
    server: ComponentInfo
    facilitator: ComponentInfo
    network: str = "tron:nile"
    description: str = ""
    tags: list[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        """Unique scenario identifier"""
        return f"{self.client.name}_{self.server.name}_{self.facilitator.name}"


def generate_test_scenarios(
    clients: list[ComponentInfo],
    servers: list[ComponentInfo],
    facilitators: list[ComponentInfo],
    network_filter: Optional[str] = None,
) -> list[TestScenario]:
    """
    Generate all valid test scenarios from components.

    Args:
        clients: Available clients
        servers: Available servers
        facilitators: Available facilitators
        network_filter: Filter by network (e.g., "tron:nile")

    Returns:
        List of test scenarios
    """
    scenarios = []

    for client in clients:
        for server in servers:
            for facilitator in facilitators:
                # Check network compatibility
                networks = {client.network, server.network, facilitator.network}
                if len(networks) > 1:
                    # Skip incompatible networks
                    continue

                network = client.network
                if network_filter and network != network_filter:
                    continue

                scenario = TestScenario(
                    name=f"{client.name} -> {server.name} via {facilitator.name}",
                    client=client,
                    server=server,
                    facilitator=facilitator,
                    network=network,
                    description=f"Test payment flow using {client.language} client",
                    tags=[client.language, server.language, facilitator.language],
                )
                scenarios.append(scenario)

    return scenarios


def minimize_scenarios(
    scenarios: list[TestScenario],
    max_scenarios: int = 5,
) -> list[TestScenario]:
    """
    Minimize scenarios to reduce test time while maintaining coverage.

    Args:
        scenarios: All scenarios
        max_scenarios: Maximum number of scenarios to keep

    Returns:
        Minimized list of scenarios
    """
    if len(scenarios) <= max_scenarios:
        return scenarios

    # Prioritize diverse combinations
    selected = []
    seen_clients = set()
    seen_servers = set()
    seen_facilitators = set()

    for scenario in scenarios:
        # Prefer scenarios with unseen components
        score = 0
        if scenario.client.name not in seen_clients:
            score += 1
        if scenario.server.name not in seen_servers:
            score += 1
        if scenario.facilitator.name not in seen_facilitators:
            score += 1

        if score > 0 or len(selected) < max_scenarios:
            selected.append(scenario)
            seen_clients.add(scenario.client.name)
            seen_servers.add(scenario.server.name)
            seen_facilitators.add(scenario.facilitator.name)

        if len(selected) >= max_scenarios:
            break

    return selected


def filter_scenarios_by_tag(
    scenarios: list[TestScenario],
    include_tags: Optional[list[str]] = None,
    exclude_tags: Optional[list[str]] = None,
) -> list[TestScenario]:
    """
    Filter scenarios by tags.

    Args:
        scenarios: All scenarios
        include_tags: Only include scenarios with these tags
        exclude_tags: Exclude scenarios with these tags

    Returns:
        Filtered scenarios
    """
    result = scenarios

    if include_tags:
        result = [s for s in result if any(tag in s.tags for tag in include_tags)]

    if exclude_tags:
        result = [s for s in result if not any(tag in s.tags for tag in exclude_tags)]

    return result
