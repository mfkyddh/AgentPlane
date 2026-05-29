"""Tests for agentplane.domain.app.delivery_handlers — pure helper functions."""

from __future__ import annotations

from typing import Any

import pytest
from agentplane.domain.app.delivery_handlers import (
    _delayed_cleanup_state,
    _display_commands,
    _rollback_state_payload,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# _display_commands
# ---------------------------------------------------------------------------


class TestDisplayCommands:
    def test_basic(self) -> None:
        steps = [
            {"backend": {"display_command": "docker compose up -d"}},
            {"backend": {"display_command": "systemctl restart app"}},
        ]
        result = _display_commands(steps)
        assert result == ["docker compose up -d", "systemctl restart app"]

    def test_empty(self) -> None:
        assert _display_commands([]) == []


# ---------------------------------------------------------------------------
# _delayed_cleanup_state
# ---------------------------------------------------------------------------


class TestDelayedCleanupState:
    def test_none_kind(self) -> None:
        entry: dict[str, Any] = {"kind": "none"}
        result = _delayed_cleanup_state(entry)
        assert result["status"] == "not-applicable"
        assert result["observation_window_required"] is False

    def test_other_kind(self) -> None:
        entry: dict[str, Any] = {"kind": "compose"}
        result = _delayed_cleanup_state(entry)
        assert result["status"] == "observation-window-pending"
        assert result["observation_window_required"] is True


# ---------------------------------------------------------------------------
# _rollback_state_payload
# ---------------------------------------------------------------------------


class TestRollbackStatePayload:
    def test_assembles_all_sections(self) -> None:
        result = _rollback_state_payload(
            previous_control_plane={"state": "old"},
            candidate={"state": "new"},
            cutover={"done": True},
            post_cutover_verification={"ok": True},
            rollback_on_failure={"plan": "revert"},
            delayed_cleanup={"status": "pending"},
        )
        assert result["previous_control_plane"]["state"] == "old"
        assert result["candidate"]["state"] == "new"
        assert result["cutover"]["done"] is True
        assert result["post_cutover_verification"]["ok"] is True
        assert result["rollback_on_failure"]["plan"] == "revert"
        assert result["delayed_cleanup"]["status"] == "pending"


# ---------------------------------------------------------------------------
# Golden test
# ---------------------------------------------------------------------------


@pytest.mark.golden
class TestDeliveryHelpersGolden:
    def test_full_rollback_roundtrip(self) -> None:
        """Full rollback state payload with all sections populated."""
        payload = _rollback_state_payload(
            previous_control_plane={"service": "myapp", "version": "1.0"},
            candidate={"service": "myapp", "version": "2.0"},
            cutover={"timestamp": "2026-05-11T10:00:00Z"},
            post_cutover_verification={"healthcheck": True, "origin": True},
            rollback_on_failure={"commands": ["docker compose down", "systemctl start"]},
            delayed_cleanup=_delayed_cleanup_state({"kind": "compose"}),
        )
        assert payload["candidate"]["version"] == "2.0"
        assert payload["delayed_cleanup"]["observation_window_required"] is True
