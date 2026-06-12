from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest
from agentplane.runtime.backends import build_backend_runner
from agentplane.runtime.execution import (
    ExecutionPlan,
    StreamChunk,
    _classify_error,
)

pytestmark = pytest.mark.integration




# ======================================================================
# From: test_execute_stream.py
# ======================================================================


class TestBackendRunnerExecuteStream:
    def setup_method(self) -> None:
        self._which_patcher = patch("shutil.which", return_value="/bin/fake")
        self._which_patcher.start()

    def teardown_method(self) -> None:
        self._which_patcher.stop()

    @patch("agentplane.runtime.execution_runners.subprocess.Popen")
    def test_stream_yields_stdout_and_stderr(self, mock_popen: MagicMock) -> None:
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

        mock_proc = MagicMock()
        mock_proc.stdout = MagicMock()
        mock_proc.stderr = MagicMock()
        mock_proc.wait.return_value = 0

        def stdout_lines():
            yield "hello\n"
            yield ""

        def stderr_lines():
            yield ""

        mock_proc.stdout.readline.side_effect = list(stdout_lines())
        mock_proc.stderr.readline.side_effect = list(stderr_lines())
        mock_popen.return_value = mock_proc

        chunks: list[StreamChunk] = []
        result = runner.execute_stream(
            plan,
            on_chunk=lambda c: chunks.append(c),
        )

        assert result.ok is True
        assert result.stdout == "hello\n"
        assert any(c.stream == "stdout" and "hello" in c.text for c in chunks)

    @patch("agentplane.runtime.execution_runners.subprocess.Popen")
    def test_stream_failure_returns_error(self, mock_popen: MagicMock) -> None:
        runner = build_backend_runner()
        plan = ExecutionPlan(
            backend_type="linux-native",
            cwd_ref="",
            argv=("false",),
            env_refs=(),
            input_refs=(),
            expected_outputs=(),
            capabilities=("bash",),
            timeout=300,
        )

        mock_proc = MagicMock()
        mock_proc.stdout = MagicMock()
        mock_proc.stderr = MagicMock()
        mock_proc.wait.return_value = 1

        mock_proc.stdout.readline.side_effect = ["", ""]
        mock_proc.stderr.readline.side_effect = ["error\n", ""]
        mock_popen.return_value = mock_proc

        result = runner.execute_stream(plan)
        assert result.ok is False
        assert result.returncode == 1
        assert "error" in result.stderr

    @patch("agentplane.runtime.execution_runners.subprocess.Popen")
    def test_stream_without_callback_still_collects_output(self, mock_popen: MagicMock) -> None:
        runner = build_backend_runner()
        plan = ExecutionPlan(
            backend_type="linux-native",
            cwd_ref="",
            argv=("echo", "hi"),
            env_refs=(),
            input_refs=(),
            expected_outputs=(),
            capabilities=("bash",),
            timeout=300,
        )

        mock_proc = MagicMock()
        mock_proc.stdout = MagicMock()
        mock_proc.stderr = MagicMock()
        mock_proc.wait.return_value = 0

        mock_proc.stdout.readline.side_effect = ["hi\n", ""]
        mock_proc.stderr.readline.side_effect = [""]
        mock_popen.return_value = mock_proc

        result = runner.execute_stream(plan)
        assert result.ok is True
        assert result.stdout == "hi\n"



# ======================================================================
# From: test_execution_error.py
# ======================================================================


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
        with patch(
            "agentplane.runtime.execution_runners.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="sleep 10", timeout=1),
        ):
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
        with patch("agentplane.runtime.execution_runners.subprocess.run", side_effect=FileNotFoundError("No such file")):
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
        with patch("agentplane.runtime.execution_runners.subprocess.run", side_effect=OSError("random os error")):
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
        with patch("agentplane.runtime.execution_runners.subprocess.run", return_value=mock_completed):
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
        with patch("agentplane.runtime.execution_runners.subprocess.run", return_value=mock_completed):
            result = runner.execute(plan)
        assert result.ok is True
        assert result.error is None
