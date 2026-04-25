from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from agentplane.runtime.execution import (
    ExecutionBindings,
    ExecutionPlan,
    StreamChunk,
)
from agentplane.runtime.backends import build_backend_runner


class TestBackendRunnerExecuteStream:
    def setup_method(self) -> None:
        self._which_patcher = patch("shutil.which", return_value="/bin/fake")
        self._which_patcher.start()

    def teardown_method(self) -> None:
        self._which_patcher.stop()

    @patch("agentplane.runtime.execution.subprocess.Popen")
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

    @patch("agentplane.runtime.execution.subprocess.Popen")
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

    @patch("agentplane.runtime.execution.subprocess.Popen")
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
