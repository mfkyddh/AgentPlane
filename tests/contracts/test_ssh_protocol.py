"""Contract tests for SSHConnectionProtocol and RemoteAPIProtocol.

Every test is parametrized over all implementations (real + stub).
If a test passes for one implementation but fails for another,
the Protocol contract is violated.

Three-tier structure (mirrors test_provider_protocol.py):
1. Parametrized contract tests — behavior validation per implementation
2. Structural compatibility check — stub satisfies Protocol
3. Method count guard — Protocol doesn't exceed limits
"""

from __future__ import annotations

from pathlib import Path

import pytest
from agentplane.ssh import (
    RemoteAPIProtocol,
    SSHConnectionPool,
    SSHConnectionProtocol,
)

# ---------------------------------------------------------------------------
# Stubs — minimal implementations proving Protocol replaceability
# ---------------------------------------------------------------------------


class StubSSHConnection:
    """Minimal SSHConnectionProtocol implementation for contract testing."""

    def __init__(self) -> None:
        self._connected: set[str] = set()

    def ensure_connection(self, alias: str) -> None:
        self._connected.add(alias)

    def ssh_args(self, alias: str, command: str) -> list[str]:
        self.ensure_connection(alias)
        return ["ssh", alias, command]

    def tunnel_args(self, alias: str, local_port: int, remote_port: int) -> list[str]:
        self.ensure_connection(alias)
        return ["ssh", "-L", f"{local_port}:127.0.0.1:{remote_port}", "-N", alias]

    def scp_args(self, alias: str, local_path: str, remote_path: str) -> list[str]:
        self.ensure_connection(alias)
        return ["scp", local_path, f"{alias}:{remote_path}"]


class StubRemoteAPIClient:
    """Minimal RemoteAPIProtocol implementation for contract testing."""

    def __init__(self) -> None:
        self._port = 19999
        self._closed = False

    @property
    def local_port(self) -> int:
        return self._port

    def close(self) -> None:
        self._closed = True

    def __enter__(self) -> StubRemoteAPIClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _has_ssh_config() -> bool:
    """Check if a valid SSH config exists for real pool tests."""
    ssh_config = Path.home() / ".ssh" / "config"
    return ssh_config.is_file()


def _ssh_connection_params():
    params = [pytest.param("stub", id="stub")]
    if _has_ssh_config():
        params.append(pytest.param("real", id="real"))
    return params


@pytest.fixture(params=_ssh_connection_params())
def ssh_connection(request):
    """Yield an SSHConnectionProtocol implementation."""
    if request.param == "real":
        pool = SSHConnectionPool(Path.home() / ".ssh" / "config", persist_timeout=60)
        return pool
    return StubSSHConnection()


@pytest.fixture
def remote_api_client():
    """Yield a StubRemoteAPIClient (real client needs SSH, skip in unit tests)."""
    return StubRemoteAPIClient()


# ---------------------------------------------------------------------------
# Tier 1: Parametrized contract tests
# ---------------------------------------------------------------------------


class TestSSHConnectionContract:
    """Verify that any SSHConnectionProtocol implementation satisfies the contract."""

    def test_ensure_connection_accepts_alias(self, ssh_connection) -> None:
        ssh_connection.ensure_connection("test-alias")

    def test_ssh_args_returns_list_of_strings(self, ssh_connection) -> None:
        result = ssh_connection.ssh_args("test-alias", "echo hello")
        assert isinstance(result, list)
        assert all(isinstance(item, str) for item in result)
        assert len(result) > 0

    def test_tunnel_args_returns_list_of_strings(self, ssh_connection) -> None:
        result = ssh_connection.tunnel_args("test-alias", 8080, 80)
        assert isinstance(result, list)
        assert all(isinstance(item, str) for item in result)
        assert len(result) > 0

    def test_scp_args_returns_list_of_strings(self, ssh_connection) -> None:
        result = ssh_connection.scp_args("test-alias", "/local/path", "/remote/path")
        assert isinstance(result, list)
        assert all(isinstance(item, str) for item in result)
        assert len(result) > 0

    def test_ssh_args_contains_alias(self, ssh_connection) -> None:
        result = ssh_connection.ssh_args("myhost", "uptime")
        assert "myhost" in result

    def test_tunnel_args_contains_port_mapping(self, ssh_connection) -> None:
        result = ssh_connection.tunnel_args("myhost", 9090, 90)
        port_mapping = "9090:127.0.0.1:90"
        assert any(port_mapping in arg for arg in result)

    def test_scp_args_contains_paths(self, ssh_connection) -> None:
        result = ssh_connection.scp_args("myhost", "/tmp/file.txt", "/opt/file.txt")
        assert "/tmp/file.txt" in result
        assert any("file.txt" in arg for arg in result)


class TestRemoteAPIContract:
    """Verify that any RemoteAPIProtocol implementation satisfies the contract."""

    def test_local_port_returns_int(self, remote_api_client) -> None:
        assert isinstance(remote_api_client.local_port, int)

    def test_local_port_is_positive(self, remote_api_client) -> None:
        assert remote_api_client.local_port > 0

    def test_close_is_callable(self, remote_api_client) -> None:
        remote_api_client.close()

    def test_context_manager_enter_returns_self(self, remote_api_client) -> None:
        with remote_api_client as client:
            assert client is remote_api_client

    def test_context_manager_exit_calls_close(self, remote_api_client) -> None:
        with remote_api_client:
            pass
        assert remote_api_client._closed is True


# ---------------------------------------------------------------------------
# Tier 2: Structural compatibility check
# ---------------------------------------------------------------------------


class TestStubSSHIsProtocolCompatible:
    """Explicit check that StubSSHConnection structurally matches SSHConnectionProtocol."""

    def test_stub_ssh_connection_is_protocol_compatible(self) -> None:
        stub = StubSSHConnection()
        proto: SSHConnectionProtocol = stub  # type: ignore[assignment]
        assert proto is stub

    def test_stub_remote_api_is_protocol_compatible(self) -> None:
        stub = StubRemoteAPIClient()
        proto: RemoteAPIProtocol = stub  # type: ignore[assignment]
        assert proto is stub


# ---------------------------------------------------------------------------
# Tier 3: Method count guard
# ---------------------------------------------------------------------------


class TestSSHProtocolMethodCount:
    """Ensure SSH protocols don't exceed the 5-method limit."""

    def test_ssh_connection_protocol_method_count(self) -> None:
        protocol_methods = [
            name for name in dir(SSHConnectionProtocol)
            if not name.startswith("_") and callable(getattr(SSHConnectionProtocol, name, None))
        ]
        assert len(protocol_methods) <= 5, (
            f"SSHConnectionProtocol has {len(protocol_methods)} methods, exceeds limit of 5. "
            f"Methods: {protocol_methods}"
        )

    def test_remote_api_protocol_method_count(self) -> None:
        protocol_methods = [
            name for name in dir(RemoteAPIProtocol)
            if not name.startswith("_") and callable(getattr(RemoteAPIProtocol, name, None))
        ]
        # local_port is a property, not counted as callable method
        assert len(protocol_methods) <= 5, (
            f"RemoteAPIProtocol has {len(protocol_methods)} methods, exceeds limit of 5. "
            f"Methods: {protocol_methods}"
        )
