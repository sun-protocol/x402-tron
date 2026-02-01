#!/usr/bin/env python3
"""
E2E Test Runner

Interactive runner for e2e tests with real services.

Usage:
    python run_e2e.py                    # Run all tests
    python run_e2e.py --discover         # Discover components only
    python run_e2e.py --quick            # Skip slow tests
    python run_e2e.py --scenario python  # Filter by scenario tag
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent / "python" / "x402" / "src"))

from framework.discovery import discover_all
from framework.env import load_env_config, validate_env_config, print_env_status
from framework.scenarios import generate_test_scenarios


def discover_components():
    """Discover and print available components"""
    examples_dir = Path(__file__).parent.parent / "examples"
    components = discover_all(examples_dir)

    print("\n" + "=" * 60)
    print("Discovered Components")
    print("=" * 60)

    print("\nClients:")
    for c in components["clients"]:
        print(f"  - {c.name} ({c.language})")
        print(f"    Path: {c.path}")
        if c.main_file:
            print(f"    Main: {c.main_file.name}")

    print("\nServers:")
    for s in components["servers"]:
        print(f"  - {s.name} ({s.language})")
        print(f"    Path: {s.path}")
        print(f"    Port: {s.port}")

    print("\nFacilitators:")
    for f in components["facilitators"]:
        print(f"  - {f.name} ({f.language})")
        print(f"    Path: {f.path}")
        print(f"    Port: {f.port}")

    print("=" * 60 + "\n")

    return components


def generate_scenarios(components):
    """Generate and print test scenarios"""
    scenarios = generate_test_scenarios(
        clients=components["clients"],
        servers=components["servers"],
        facilitators=components["facilitators"],
    )

    print("\n" + "=" * 60)
    print("Test Scenarios")
    print("=" * 60)

    for i, s in enumerate(scenarios, 1):
        print(f"\n{i}. {s.name}")
        print(f"   Network: {s.network}")
        print(f"   Tags: {', '.join(s.tags)}")

    print("=" * 60 + "\n")

    return scenarios


def run_pytest(args: list[str]):
    """Run pytest with given arguments"""
    import subprocess

    cmd = [sys.executable, "-m", "pytest", "e2e/"] + args
    print(f"Running: {' '.join(cmd)}\n")

    result = subprocess.run(cmd, cwd=Path(__file__).parent.parent)
    return result.returncode


def main():
    parser = argparse.ArgumentParser(description="E2E Test Runner")
    parser.add_argument(
        "--discover",
        action="store_true",
        help="Discover components only, don't run tests",
    )
    parser.add_argument(
        "--scenario",
        type=str,
        help="Filter scenarios by tag (e.g., 'python')",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output",
    )
    parser.add_argument(
        "pytest_args",
        nargs="*",
        help="Additional pytest arguments",
    )

    args = parser.parse_args()

    # Load and validate environment
    config = load_env_config()
    is_valid, issues = validate_env_config(config)
    print_env_status(config)

    if issues:
        print("⚠️  Environment issues:")
        for issue in issues:
            print(f"   - {issue}")
        print()

    # Discover components
    components = discover_components()

    if args.discover:
        generate_scenarios(components)
        return 0

    # Check if we can run tests
    if not is_valid:
        print("❌ Cannot run e2e tests: environment not configured")
        print("   Please set required environment variables in .env")
        return 1

    # Build pytest arguments
    pytest_args = []

    if args.verbose:
        pytest_args.append("-v")

    if args.scenario:
        # Filter by scenario tag
        pytest_args.extend(["-k", args.scenario])

    # Add any additional pytest args
    pytest_args.extend(args.pytest_args)

    # Build pytest arguments
    pytest_args = []

    if args.verbose:
        pytest_args.append("-v")

    if args.quick:
        pytest_args.extend(["-m", "not slow"])

    if args.real_only:
        pytest_args.extend(["-m", "real_services"])

    if args.scenario:
        # Filter by scenario tag
        pytest_args.extend(["-k", args.scenario])

    # Add any additional pytest args
    pytest_args.extend(args.pytest_args)

    # Run tests
    return run_pytest(pytest_args)


if __name__ == "__main__":
    sys.exit(main())
