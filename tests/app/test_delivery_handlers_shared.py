"""Unit tests for delivery_handlers_shared module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from agentplane.domain.app.delivery_handlers_shared import (
    _display_commands,
    _execute_steps,
    _render_execution_steps,
    _transition_step_to_execution,
)

pytestmark = pytest.mark.unit


class TestDisplayCommands:
    """Tests for _display_commands function."""

    def test_returns_display_commands(self) -> None:
        """Test that returns display commands from execution steps."""
        steps = [
            {"backend": {"display_command": "docker compose up -d"}},
            {"backend": {"display_command": "echo hello"}},
        ]

        result = _display_commands(steps)

        assert result == ["docker compose up -d", "echo hello"]

    def test_returns_empty_for_empty_steps(self) -> None:
        """Test that returns empty list for empty steps."""
        assert _display_commands([]) == []


class TestRenderExecutionSteps:
    """Tests for _render_execution_steps function."""

    def test_renders_steps_with_runner(self) -> None:
        """Test that renders steps using runner."""
        mock_runner = MagicMock()
        mock_rendered = MagicMock()
        mock_rendered.to_payload.return_value = {
            "backend_type": "linux-native",
            "display_command": "echo hello",
        }
        mock_runner.render_spec.return_value = mock_rendered

        step = MagicMock()
        step.key = "test.step"
        step.spec.metadata = {}
        step.spec.backend_type = "linux-native"
        step.spec.to_payload.return_value = {"backend_type": "linux-native"}

        result = _render_execution_steps([step], _runner=mock_runner)

        assert len(result) == 1
        assert result[0]["key"] == "test.step"
        assert result[0]["backend"]["display_command"] == "echo hello"

    def test_handles_display_override(self) -> None:
        """Test that handles display_override metadata."""
        mock_runner = MagicMock()
        mock_rendered = MagicMock()
        mock_rendered.to_payload.return_value = {
            "backend_type": "linux-native",
            "display_command": "original",
        }
        mock_runner.render_spec.return_value = mock_rendered

        step = MagicMock()
        step.key = "test.step"
        step.spec.metadata = {"display_override": "custom display"}
        step.spec.backend_type = "linux-native"
        step.spec.to_payload.return_value = {"backend_type": "linux-native"}

        result = _render_execution_steps([step], _runner=mock_runner)

        assert result[0]["backend"]["display_command"] == "custom display"

    def test_handles_windows_wsl_backend_error(self) -> None:
        """Test that handles windows-wsl backend error gracefully."""
        mock_runner = MagicMock()
        mock_runner.render_spec.side_effect = ValueError("backend not available")

        step = MagicMock()
        step.key = "test.step"
        step.spec.metadata = {}
        step.spec.backend_type = "windows-wsl"
        step.spec.argv = ("docker", "ps")
        step.spec.stdin_text = None
        step.spec.expected_outputs = []
        step.spec.capabilities = ("docker",)

        result = _render_execution_steps([step], _runner=mock_runner)

        assert len(result) == 1
        assert result[0]["backend"]["blocked"] is True
        assert "backend not available" in result[0]["backend"]["reason"]

    def test_raises_on_non_windows_wsl_backend_error(self) -> None:
        """Test that raises on non-windows-wsl backend error."""
        mock_runner = MagicMock()
        mock_runner.render_spec.side_effect = ValueError("backend not available")

        step = MagicMock()
        step.key = "test.step"
        step.spec.metadata = {}
        step.spec.backend_type = "linux-native"
        step.spec.argv = ("docker", "ps")

        with pytest.raises(ValueError, match="backend not available"):
            _render_execution_steps([step], _runner=mock_runner)


class TestExecuteSteps:
    """Tests for _execute_steps function."""

    def test_executes_all_steps(self) -> None:
        """Test that executes all steps."""
        mock_runner = MagicMock()
        mock_result = MagicMock()
        mock_result.ok = True
        mock_result.to_payload.return_value = {"ok": True, "stdout": "ok"}
        mock_runner.execute_spec.return_value = mock_result

        step = MagicMock()
        step.key = "test.step"

        with patch("agentplane.domain.app.delivery_handlers_shared.redact_execution_payload", side_effect=lambda x: x):
            result = _execute_steps([step, step], stop_on_failure=False, _runner=mock_runner)

        assert len(result) == 2
        assert mock_runner.execute_spec.call_count == 2

    def test_stops_on_failure(self) -> None:
        """Test that stops on failure when stop_on_failure is True."""
        mock_runner = MagicMock()
        mock_result = MagicMock()
        mock_result.ok = False
        mock_result.to_payload.return_value = {"ok": False, "stderr": "failed"}
        mock_runner.execute_spec.return_value = mock_result

        step = MagicMock()
        step.key = "test.step"

        with patch("agentplane.domain.app.delivery_handlers_shared.redact_execution_payload", side_effect=lambda x: x):
            result = _execute_steps([step, step], stop_on_failure=True, _runner=mock_runner)

        assert len(result) == 1
        assert mock_runner.execute_spec.call_count == 1

    def test_continues_on_failure_when_not_stopping(self) -> None:
        """Test that continues on failure when stop_on_failure is False."""
        mock_runner = MagicMock()
        mock_result = MagicMock()
        mock_result.ok = False
        mock_result.to_payload.return_value = {"ok": False, "stderr": "failed"}
        mock_runner.execute_spec.return_value = mock_result

        step = MagicMock()
        step.key = "test.step"

        with patch("agentplane.domain.app.delivery_handlers_shared.redact_execution_payload", side_effect=lambda x: x):
            result = _execute_steps([step, step], stop_on_failure=False, _runner=mock_runner)

        assert len(result) == 2


class TestTransitionStepToExecution:
    """Tests for _transition_step_to_execution function."""

    def test_returns_none_for_none_transition(self) -> None:
        """Test that returns None for None transition."""
        app_cli = MagicMock()

        result = _transition_step_to_execution(
            app_cli,
            repo_root=Path("/tmp"),
            target="wsl",
            key="test.step",
            transition_step=None,
        )

        assert result is None

    def test_handles_ssh_transition(self) -> None:
        """Test that handles SSH transition step."""
        app_cli = MagicMock()
        app_cli._target_ssh_target.return_value = MagicMock()

        transition_step = (["ssh", "user@host", "-lc", "echo hello"], "ssh echo")

        with patch("agentplane.domain.app.delivery_handlers_shared.plan_remote_shell_step") as mock_plan:
            mock_plan.return_value = MagicMock()

            result = _transition_step_to_execution(
                app_cli,
                repo_root=Path("/tmp"),
                target="prod0-main",
                key="test.step",
                transition_step=transition_step,
            )

        assert result is not None
        mock_plan.assert_called_once()

    def test_handles_local_transition(self) -> None:
        """Test that handles local transition step."""
        app_cli = MagicMock()

        transition_step = (["docker", "compose", "up", "-d"], "docker compose up -d")

        with patch("agentplane.domain.app.delivery_handlers_shared.detect_host_profile") as mock_detect:
            mock_detect.return_value = MagicMock(linux_backend="linux-native")

            with patch("agentplane.domain.app.delivery_handlers_shared.plan_local_backend_step") as mock_plan:
                mock_plan.return_value = MagicMock()

                result = _transition_step_to_execution(
                    app_cli,
                    repo_root=Path("/tmp"),
                    target="wsl",
                    key="test.step",
                    transition_step=transition_step,
                )

        assert result is not None
        mock_plan.assert_called_once()
