"""Tests for agentplane.domain.app.delivery_handlers — pure helper functions."""

from __future__ import annotations

from typing import Any

import pytest
from agentplane.domain.app.delivery_handlers import (
    _candidate_host_binding,
    _delayed_cleanup_state,
    _display_commands,
    _rollback_state_payload,
)

pytestmark = pytest.mark.unit


class _FakeAppCli:
    """Minimal mock for app_cli that provides _split_host_binding."""

    def _split_host_binding(self, host_binding: str) -> tuple[str, str]:
        host, sep, port = host_binding.rpartition(":")
        if not sep or not port:
            raise ValueError(f"runtime.host_binding 格式不合法: {host_binding}")
        return host or "127.0.0.1", port


# ---------------------------------------------------------------------------
# _candidate_host_binding
# ---------------------------------------------------------------------------


class TestCandidateHostBinding:
    def test_normal_port(self) -> None:
        cli = _FakeAppCli()
        result = _candidate_host_binding(cli, "127.0.0.1:8080")
        assert result == "127.0.0.1:9080"

    def test_high_port(self) -> None:
        cli = _FakeAppCli()
        result = _candidate_host_binding(cli, "0.0.0.0:65000")
        assert result == "0.0.0.0:64000"

    def test_very_low_port_adds_1000(self) -> None:
        cli = _FakeAppCli()
        # port 500 <= 64535, so candidate = 500 + 1000 = 1500
        result = _candidate_host_binding(cli, "127.0.0.1:500")
        assert result == "127.0.0.1:1500"


# ---------------------------------------------------------------------------
# _display_commands
# ---------------------------------------------------------------------------


class TestDisplayCommands:
    def test_basic(self) -> None:
        steps: list[dict[str, Any]] = [
            {"backend": {"display_command": "docker compose up -d"}},
            {"backend": {"display_command": "curl http://localhost:8080/health"}},
        ]
        result = _display_commands(steps)
        assert result == ["docker compose up -d", "curl http://localhost:8080/health"]

    def test_empty(self) -> None:
        assert _display_commands([]) == []


# ---------------------------------------------------------------------------
# _delayed_cleanup_state
# ---------------------------------------------------------------------------


class TestDelayedCleanupState:
    def test_kind_none(self) -> None:
        result = _delayed_cleanup_state({"kind": "none"})
        assert result["status"] == "not-applicable"
        assert result["observation_window_required"] is False

    def test_kind_systemd(self) -> None:
        result = _delayed_cleanup_state({"kind": "systemd", "service_name": "myapp"})
        assert result["status"] == "observation-window-pending"
        assert result["observation_window_required"] is True

    def test_unknown_kind(self) -> None:
        result = _delayed_cleanup_state({"kind": "compose"})
        assert result["status"] == "observation-window-pending"


# ---------------------------------------------------------------------------
# _rollback_state_payload
# ---------------------------------------------------------------------------


class TestRollbackStatePayload:
    def test_assembles_all_sections(self) -> None:
        result = _rollback_state_payload(
            previous_control_plane={"kind": "none"},
            candidate={"image_ref": "myapp:latest"},
            cutover={"ok": True},
            post_cutover_verification={"ok": True},
            rollback_on_failure={"ok": False},
            delayed_cleanup={"status": "not-applicable"},
        )
        assert result["previous_control_plane"]["kind"] == "none"
        assert result["candidate"]["image_ref"] == "myapp:latest"
        assert result["cutover"]["ok"] is True
        assert result["post_cutover_verification"]["ok"] is True
        assert result["rollback_on_failure"]["ok"] is False
        assert result["delayed_cleanup"]["status"] == "not-applicable"


# ---------------------------------------------------------------------------
# Golden test
# ---------------------------------------------------------------------------


@pytest.mark.golden
class TestDeliveryHandlersGolden:
    def test_full_delivery_roundtrip(self) -> None:
        """Full candidate binding + display + cleanup state."""
        cli = _FakeAppCli()

        binding = _candidate_host_binding(cli, "127.0.0.1:8080")
        assert binding == "127.0.0.1:9080"

        steps: list[dict[str, Any]] = [
            {"backend": {"display_command": "docker pull myapp:latest"}},
            {"backend": {"display_command": "docker compose up -d"}},
        ]
        commands = _display_commands(steps)
        assert len(commands) == 2

        cleanup = _delayed_cleanup_state({"kind": "systemd", "service_name": "myapp"})
        assert cleanup["observation_window_required"] is True

        payload = _rollback_state_payload(
            previous_control_plane={"kind": "systemd", "service_name": "myapp"},
            candidate={"image_ref": "myapp:latest"},
            cutover={"ok": True},
            post_cutover_verification={"ok": True},
            rollback_on_failure={"ok": True},
            delayed_cleanup=cleanup,
        )
        assert payload["previous_control_plane"]["service_name"] == "myapp"
        assert payload["delayed_cleanup"]["status"] == "observation-window-pending"
