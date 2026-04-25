from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest

import shutil

from agentplane.runtime.execution import (
    ExecutionBindings,
    ExecutionError,
    ExecutionPlan,
    ExecutionResult,
    _classify_error,
)
from agentplane.runtime.backends import build_backend_runner


class TestClassifyError:
    def test_permission_denied_maps_to_auth(self) -> None:
        err = _classify_error(1, "sudo: permission denied")
        assert err.category == "auth"
        assert err.retryable is False
        assert err.escalation == "human"

    def test_connection_refused_maps_to_network(self) -> None:
        err = _classify_error(255, "ssh: connect to host 1.2.3.4 port 22: Connection refused")
        assert err.category == "network"
        assert err.retryable is True
        assert err.escalation == "auto"

    def test_command_not_found_maps_to_command(self) -> None:
        err = _classify_error(127, "bash: foo: command not found")
        assert err.category == "command"
        assert err.retryable is False
        assert err.escalation == "none"

    def test_generic_failure_maps_to_command(self) -> None:
        err = _classify_error(1, "some random error")
        assert err.category == "command"
        assert err.retryable is True
        assert err.escalation == "none"

    def test_exit_code_two_not_retryable(self) -> None:
        err = _classify_error(2, "invalid syntax")
        assert err.category == "command"
        assert err.retryable is False
        assert err.escalation == "none"


class TestBackendRunnerErrorHandling:
    def setup_method(self) -> None:
        self._which_patcher = patch("shutil.which", return_value="/bin/fake")
        self._which_patcher.start()

    def teardown_method(self) -> None:
        self._which_patcher.stop()

    def test_timeout_expired_returns_timeout_error(self) -> None:
        runner = build_backend_runner()
        plan = ExecutionPlan(
            backend_type="linux-native",
            cwd_ref="",
            argv=("sleep", "10"),
            env_refs=(),
            input_refs=(),
            expected_outputs=(),
            capabilities=("bash",),
            timeout=1,
        )
        with patch("agentplane.runtime.execution.subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="sleep 10", timeout=1)):
            result = runner.execute(plan)
        assert result.ok is False
        assert result.returncode == -1
        assert result.error is not None
        assert result.error.category == "timeout"
        assert result.error.retryable is True
        assert result.error.escalation == "auto"

    def test_file_not_found_returns_backend_unavailable(self) -> None:
        runner = build_backend_runner()
        plan = ExecutionPlan(
            backend_type="linux-native",
            cwd_ref="",
            argv=("nonexistent-binary-xyz",),
            env_refs=(),
            input_refs=(),
            expected_outputs=(),
            capabilities=("bash",),
            timeout=300,
        )
        with patch("agentplane.runtime.execution.subprocess.run", side_effect=FileNotFoundError("No such file")):
            result = runner.execute(plan)
        assert result.ok is False
        assert result.error is not None
        assert result.error.category == "backend_unavailable"
        assert result.error.retryable is False
        assert result.error.escalation == "human"

    def test_os_error_returns_unknown(self) -> None:
        runner = build_backend_runner()
        plan = ExecutionPlan(
            backend_type="linux-native",
            cwd_ref="",
            argv=("echo", "hello"),
            env_refs=(),
            input_refs=(),
            expected_outputs=(),
            capabilities=("bash",),
            timeout=300,
        )
        with patch("agentplane.runtime.execution.subprocess.run", side_effect=OSError("random os error")):
            result = runner.execute(plan)
        assert result.ok is False
        assert result.error is not None
        assert result.error.category == "unknown"
        assert result.error.escalation == "human"

    def test_failed_command_returns_classified_error(self) -> None:
        runner = build_backend_runner()
        plan = ExecutionPlan(
            backend_type="linux-native",
            cwd_ref="",
            argv=("ssh", "bad-host"),
            env_refs=(),
            input_refs=(),
            expected_outputs=(),
            capabilities=("ssh",),
            timeout=300,
        )
        mock_completed = subprocess.CompletedProcess(
            args=["ssh", "bad-host"],
            returncode=255,
            stdout="",
            stderr="ssh: connect to host bad-host port 22: Connection refused",
        )
        with patch("agentplane.runtime.execution.subprocess.run", return_value=mock_completed):
            result = runner.execute(plan)
        assert result.ok is False
        assert result.error is not None
        assert result.error.category == "network"

    def test_successful_command_has_no_error(self) -> None:
        runner = build_backend_runner()
        plan = ExecutionPlan(
            backend_type="linux-native",
            cwd_ref="",
            argv=("echo", "hello"),
            env_refs=(),
            input_refs=(),
            expected_outputs=(),
            capabilities=("bash",),
            timeout=300,
        )
        mock_completed = subprocess.CompletedProcess(
            args=["echo", "hello"],
            returncode=0,
            stdout="hello\n",
            stderr="",
        )
        with patch("agentplane.runtime.execution.subprocess.run", return_value=mock_completed):
            result = runner.execute(plan)
        assert result.ok is True
        assert result.error is None


class TestExecutionResultPayload:
    def test_payload_includes_error_when_present(self) -> None:
        error = ExecutionError(
            category="network",
            message="Connection refused",
            retryable=True,
            escalation="auto",
        )
        result = ExecutionResult(
            backend_type="linux-native",
            argv=("ssh", "host"),
            display_command="ssh host",
            cwd=None,
            returncode=255,
            stdout="",
            stderr="Connection refused",
            ok=False,
            error=error,
        )
        payload = result.to_payload()
        assert payload["ok"] is False
        assert payload["error"] == {
            "category": "network",
            "message": "Connection refused",
            "retryable": True,
            "escalation": "auto",
        }

    def test_payload_omits_error_when_absent(self) -> None:
        result = ExecutionResult(
            backend_type="linux-native",
            argv=("echo", "hi"),
            display_command="echo hi",
            cwd=None,
            returncode=0,
            stdout="hi\n",
            stderr="",
            ok=True,
            error=None,
        )
        payload = result.to_payload()
        assert "error" not in payload
