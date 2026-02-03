"""
Component Discovery

Discovers available clients, servers, and facilitators from examples directory.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ComponentInfo:
    """Information about a discovered component"""

    name: str
    path: Path
    language: str  # "python" or "typescript"
    component_type: str  # "client", "server", "facilitator"
    network: str = "tron:nile"
    port: int = 0
    env_file: Optional[Path] = None
    start_script: Optional[Path] = None
    main_file: Optional[Path] = None
    config: dict = field(default_factory=dict)


def _find_env_file(directory: Path) -> Optional[Path]:
    """Find .env or .env.example file"""
    for name in [".env", ".env.example"]:
        env_path = directory / name
        if env_path.exists():
            return env_path
    return None


def _find_start_script(directory: Path) -> Optional[Path]:
    """Find start.sh or run.sh script"""
    for name in ["start.sh", "run.sh"]:
        script_path = directory / name
        if script_path.exists():
            return script_path
    return None


def _find_main_file(directory: Path, language: str) -> Optional[Path]:
    """Find main entry file"""
    if language == "python":
        main_py = directory / "main.py"
        if main_py.exists():
            return main_py
    elif language == "typescript":
        for name in ["index.ts", "main.ts", "src/index.ts", "src/main.ts"]:
            main_ts = directory / name
            if main_ts.exists():
                return main_ts
    return None


def _detect_port(directory: Path, component_type: str) -> int:
    """Detect default port from code or config"""
    # Default ports
    defaults = {
        "server": 8000,
        "facilitator": 8001,
        "client": 0,  # Clients don't need ports
    }

    # Try to read from main.py
    main_py = directory / "main.py"
    if main_py.exists():
        content = main_py.read_text()
        # Look for PORT = or port = patterns
        import re

        match = re.search(r"(?:PORT|port)\s*=\s*(\d+)", content)
        if match:
            return int(match.group(1))

    return defaults.get(component_type, 0)


def discover_clients(examples_dir: Optional[Path] = None) -> list[ComponentInfo]:
    """
    Discover available client implementations.

    Args:
        examples_dir: Path to examples directory

    Returns:
        List of discovered clients
    """
    if examples_dir is None:
        examples_dir = Path(__file__).parent.parent.parent / "examples"

    clients = []

    # Python client
    py_client_dir = examples_dir / "python" / "client"
    if py_client_dir.exists():
        clients.append(
            ComponentInfo(
                name="python-client",
                path=py_client_dir,
                language="python",
                component_type="client",
                env_file=_find_env_file(py_client_dir),
                start_script=_find_start_script(py_client_dir),
                main_file=_find_main_file(py_client_dir, "python"),
            )
        )

    # TypeScript web client
    ts_client_dir = examples_dir / "typescript" / "client-web"
    if ts_client_dir.exists():
        clients.append(
            ComponentInfo(
                name="typescript-client-web",
                path=ts_client_dir,
                language="typescript",
                component_type="client",
                env_file=_find_env_file(ts_client_dir),
                start_script=_find_start_script(ts_client_dir),
                main_file=_find_main_file(ts_client_dir, "typescript"),
            )
        )

    return clients


def discover_servers(examples_dir: Optional[Path] = None) -> list[ComponentInfo]:
    """
    Discover available server implementations.

    Args:
        examples_dir: Path to examples directory

    Returns:
        List of discovered servers
    """
    if examples_dir is None:
        examples_dir = Path(__file__).parent.parent.parent / "examples"

    servers = []

    # Python server
    py_server_dir = examples_dir / "python" / "server"
    if py_server_dir.exists():
        servers.append(
            ComponentInfo(
                name="python-server",
                path=py_server_dir,
                language="python",
                component_type="server",
                port=_detect_port(py_server_dir, "server"),
                env_file=_find_env_file(py_server_dir),
                start_script=_find_start_script(py_server_dir),
                main_file=_find_main_file(py_server_dir, "python"),
            )
        )

    return servers


def discover_facilitators(examples_dir: Optional[Path] = None) -> list[ComponentInfo]:
    """
    Discover available facilitator implementations.

    Args:
        examples_dir: Path to examples directory

    Returns:
        List of discovered facilitators
    """
    if examples_dir is None:
        examples_dir = Path(__file__).parent.parent.parent / "examples"

    facilitators = []

    # Python facilitator
    py_facilitator_dir = examples_dir / "python" / "facilitator"
    if py_facilitator_dir.exists():
        facilitators.append(
            ComponentInfo(
                name="python-facilitator",
                path=py_facilitator_dir,
                language="python",
                component_type="facilitator",
                port=_detect_port(py_facilitator_dir, "facilitator"),
                env_file=_find_env_file(py_facilitator_dir),
                start_script=_find_start_script(py_facilitator_dir),
                main_file=_find_main_file(py_facilitator_dir, "python"),
            )
        )

    return facilitators


def discover_all(examples_dir: Optional[Path] = None) -> dict[str, list[ComponentInfo]]:
    """
    Discover all components.

    Returns:
        Dict with keys: clients, servers, facilitators
    """
    return {
        "clients": discover_clients(examples_dir),
        "servers": discover_servers(examples_dir),
        "facilitators": discover_facilitators(examples_dir),
    }
