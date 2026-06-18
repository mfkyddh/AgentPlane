"""Tests for runtime_rollback module."""

from __future__ import annotations

import importlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


def _import_runtime_rollback():
    """Import runtime_rollback module lazily to avoid circular imports."""
    mod = importlib.import_module("agentplane.domain.app.runtime_rollback")
    return mod.rollback_app


class TestRollbackApp:
    """Tests for rollback_app function."""

    def test_wsl_target_returns_local_result(self) -> None:
        """Test that wsl target returns local-only result."""
        rollback_app = _import_runtime_rollback()

        contract = {
            "app_id": "test-app",
            "rollback": {
                "previous_control_plane": {
                    "kind": "compose",
                    "image_ref": "test-image:v1",
                },
            },
        }

        with (
            patch("agentplane.domain.app.runtime._record_app_operation") as mock_record,
            patch("agentplane.domain.app.runtime_rollback.next_operation_id") as mock_op_id,
        ):
            mock_record.return_value = {"action": "rollback", "result": "local-only"}
            mock_op_id.return_value = "op-rollback-1"

            result = rollback_app(
                contract,
                repo_root=Path("/tmp"),
                target="wsl",
                dry_run=False,
                execute=False,
            )

            assert result["dry_run"] is False
            assert "operation" in result
            assert "rollback_entry" in result

    def test_wsl_target_dry_run(self) -> None:
        """Test that wsl target with dry_run returns planned result."""
        rollback_app = _import_runtime_rollback()

        contract = {
            "app_id": "test-app",
            "rollback": {
                "previous_control_plane": {
                    "kind": "compose",
                    "image_ref": "test-image:v1",
                },
            },
        }

        with (
            patch("agentplane.domain.app.runtime._record_app_operation") as mock_record,
            patch("agentplane.domain.app.runtime_rollback.next_operation_id") as mock_op_id,
        ):
            mock_record.return_value = {"action": "rollback", "result": "planned"}
            mock_op_id.return_value = "op-rollback-2"

            result = rollback_app(
                contract,
                repo_root=Path("/tmp"),
                target="wsl",
                dry_run=True,
                execute=False,
            )

            assert result["dry_run"] is True
            assert "operation" in result

    def test_raises_when_both_dry_run_and_execute(self) -> None:
        """Test that raises ValueError when both dry_run and execute are True."""
        rollback_app = _import_runtime_rollback()

        contract = {
            "app_id": "test-app",
            "rollback": {
                "previous_control_plane": {
                    "kind": "compose",
                    "image_ref": "test-image:v1",
                },
            },
        }

        with pytest.raises(ValueError, match="不允许同时传 --dry-run 和 --execute"):
            rollback_app(
                contract,
                repo_root=Path("/tmp"),
                target="prod0-main",
                dry_run=True,
                execute=True,
            )

    def test_none_rollback_returns_noop(self) -> None:
        """Test that none rollback kind returns noop result."""
        rollback_app = _import_runtime_rollback()

        contract = {
            "app_id": "test-app",
            "rollback": {
                "previous_control_plane": {
                    "kind": "none",
                },
            },
        }

        with (
            patch("agentplane.domain.app.runtime._record_app_operation") as mock_record,
            patch("agentplane.domain.app.runtime_rollback.next_operation_id") as mock_op_id,
        ):
            mock_record.return_value = {"action": "rollback", "result": "noop"}
            mock_op_id.return_value = "op-rollback-3"

            result = rollback_app(
                contract,
                repo_root=Path("/tmp"),
                target="prod0-main",
                dry_run=False,
                execute=False,
            )

            assert result["ok"] is True
            assert result["commands"] == []
            assert "warning" in result

    def test_dry_run_returns_planned_result(self) -> None:
        """Test that dry_run returns planned result without executing."""
        rollback_app = _import_runtime_rollback()

        contract = {
            "app_id": "test-app",
            "rollback": {
                "previous_control_plane": {
                    "kind": "compose",
                    "image_ref": "test-image:v1",
                },
            },
        }

        with (
            patch("agentplane.domain.app.runtime._record_app_operation") as mock_record,
            patch("agentplane.domain.app.runtime_rollback.next_operation_id") as mock_op_id,
            patch("agentplane.domain.app.runtime._target_ssh_target") as mock_ssh,
            patch("agentplane.domain.app.runtime._control_plane_transition_step") as mock_transition,
        ):
            mock_record.return_value = {"action": "rollback", "result": "planned"}
            mock_op_id.return_value = "op-rollback-4"

            mock_ssh_target = MagicMock()
            mock_ssh_target.display_ssh_command.return_value = "ssh user@host 'command'"
            mock_ssh.return_value = mock_ssh_target

            mock_transition.return_value = None

            result = rollback_app(
                contract,
                repo_root=Path("/tmp"),
                target="prod0-main",
                dry_run=True,
                execute=False,
            )

            assert result["dry_run"] is True
            assert "commands" in result
            assert "operation" in result

    def test_execute_runs_steps(self) -> None:
        """Test that execute=True runs the rollback steps."""
        rollback_app = _import_runtime_rollback()

        contract = {
            "app_id": "test-app",
            "rollback": {
                "previous_control_plane": {
                    "kind": "compose",
                    "image_ref": "test-image:v1",
                },
            },
        }

        with (
            patch("agentplane.domain.app.runtime._record_app_operation") as mock_record,
            patch("agentplane.domain.app.runtime_rollback.next_operation_id") as mock_op_id,
            patch("agentplane.domain.app.runtime._target_ssh_target") as mock_ssh,
            patch("agentplane.domain.app.runtime._control_plane_transition_step") as mock_transition,
            patch("agentplane.domain.app.runtime._execute_step") as mock_execute,
            patch("agentplane.domain.app.runtime._local_backend_type") as mock_backend,
        ):
            mock_record.return_value = {"action": "rollback", "result": "rolled-back"}
            mock_op_id.return_value = "op-rollback-5"

            mock_ssh_target = MagicMock()
            mock_ssh_target.local_ssh_args_for_shell.return_value = ["ssh", "user@host", "command"]
            mock_ssh_target.display_ssh_command.return_value = "ssh user@host 'command'"
            mock_ssh.return_value = mock_ssh_target

            mock_transition.return_value = None
            mock_backend.return_value = "linux"

            mock_execute.return_value = {"ok": True, "result": "success"}

            result = rollback_app(
                contract,
                repo_root=Path("/tmp"),
                target="prod0-main",
                dry_run=False,
                execute=True,
            )

            assert result["dry_run"] is False
            assert result["ok"] is True
            assert "results" in result
            assert "commands" in result
