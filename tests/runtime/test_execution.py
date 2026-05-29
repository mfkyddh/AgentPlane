"""Tests for agentplane.runtime.execution — pure functions and dataclasses."""

from __future__ import annotations

from pathlib import Path

import pytest
from agentplane.runtime.execution import (
    CommandSpec,
    ExecutionBindings,
    ExecutionError,
    ExecutionPlan,
    ExecutionResult,
    RenderedExecution,
    _classify_error,
    env_prefixed_command,
    shell_join,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# shell_join
# ---------------------------------------------------------------------------


class TestShellJoin:
    def test_simple(self) -> None:
        assert shell_join(["echo", "hello"]) == "echo hello"

    def test_with_spaces(self) -> None:
        result = shell_join(["echo", "hello world"])
        assert result == "echo 'hello world'"

    def test_empty(self) -> None:
        assert shell_join([]) == ""

    def test_tuple_input(self) -> None:
        assert shell_join(("ls", "-la")) == "ls -la"

    def test_special_chars(self) -> None:
        result = shell_join(["echo", "$HOME"])
        assert "$HOME" not in result or "'$HOME'" in result


# ---------------------------------------------------------------------------
# env_prefixed_command
# ---------------------------------------------------------------------------


class TestEnvPrefixedCommand:
    def test_with_env(self) -> None:
        result = env_prefixed_command(("echo", "hi"), {"VAR": "val"})
        assert "VAR=val" in result
        assert "echo hi" in result

    def test_empty_env(self) -> None:
        result = env_prefixed_command(("ls",), {})
        assert result == "ls"

    def test_multiple_env(self) -> None:
        result = env_prefixed_command(("cmd",), {"A": "1", "B": "2"})
        assert "A=1" in result
        assert "B=2" in result


# ---------------------------------------------------------------------------
# _classify_error
# ---------------------------------------------------------------------------


class TestClassifyError:
    def test_auth_error(self) -> None:
        err = _classify_error(1, "Permission denied (publickey)")
        assert err.category == "auth"
        assert err.retryable is False
        assert err.escalation == "human"

    def test_auth_authentication(self) -> None:
        err = _classify_error(1, "Authentication failed")
        assert err.category == "auth"

    def test_network_connection_refused(self) -> None:
        err = _classify_error(1, "Connection refused")
        assert err.category == "network"
        assert err.retryable is True
        assert err.escalation == "auto"

    def test_network_no_route(self) -> None:
        err = _classify_error(1, "No route to host")
        assert err.category == "network"

    def test_network_unreachable(self) -> None:
        err = _classify_error(1, "Network is unreachable")
        assert err.category == "network"

    def test_timeout(self) -> None:
        err = _classify_error(1, "Connection timed out")
        assert err.category == "timeout"
        assert err.retryable is True

    def test_timeout_timed_out(self) -> None:
        err = _classify_error(1, "Operation timed out")
        assert err.category == "timeout"

    def test_backend_ssh_connect(self) -> None:
        err = _classify_error(1, "ssh: connect to host example.com port 22")
        assert err.category == "backend_unavailable"
        assert err.retryable is True

    def test_command_not_found(self) -> None:
        err = _classify_error(127, "bash: docker: command not found")
        assert err.category == "command"
        assert err.retryable is False

    def test_no_such_file(self) -> None:
        err = _classify_error(1, "No such file or directory")
        assert err.category == "command"

    def test_generic_error(self) -> None:
        err = _classify_error(1, "Something went wrong")
        assert err.category == "command"
        assert err.retryable is True  # returncode == 1

    def test_generic_non_retryable(self) -> None:
        err = _classify_error(2, "Something went wrong")
        assert err.category == "command"
        assert err.retryable is False

    def test_diagnostic_contains_stderr(self) -> None:
        err = _classify_error(1, "error details here")
        assert "error details here" in err.diagnostic["stderr_tail"]


# ---------------------------------------------------------------------------
# ExecutionError
# ---------------------------------------------------------------------------


class TestExecutionError:
    def test_to_payload(self) -> None:
        err = ExecutionError(
            category="network",
            message="Connection refused",
            retryable=True,
            escalation="auto",
            hint="Check host",
            diagnostic={"returncode": 1},
        )
        payload = err.to_payload()
        assert payload["category"] == "network"
        assert payload["retryable"] is True
        assert payload["hint"] == "Check host"
        assert payload["diagnostic"]["returncode"] == 1

    def test_to_payload_no_hint(self) -> None:
        err = ExecutionError(category="command", message="fail", retryable=False, escalation="none")
        payload = err.to_payload()
        assert "hint" not in payload


# ---------------------------------------------------------------------------
# ExecutionPlan
# ---------------------------------------------------------------------------


class TestExecutionPlan:
    def test_to_payload(self) -> None:
        plan = ExecutionPlan(
            backend_type="linux-native",
            cwd_ref="repo",
            argv=("echo", "hi"),
            env_refs=("env1",),
            input_refs=(),
            expected_outputs=("out1",),
            capabilities=("ssh",),
            timeout=60,
        )
        payload = plan.to_payload()
        assert payload["backend_type"] == "linux-native"
        assert payload["argv"] == ["echo", "hi"]
        assert payload["env_refs"] == ["env1"]
        assert payload["timeout"] == 60


# ---------------------------------------------------------------------------
# CommandSpec
# ---------------------------------------------------------------------------


class TestCommandSpec:
    def test_to_payload(self) -> None:
        spec = CommandSpec(
            backend_type="linux-native",
            argv=("echo", "hi"),
            cwd=Path("/tmp"),
            env={"VAR": "val"},
            timeout=30,
        )
        payload = spec.to_payload()
        assert payload["backend_type"] == "linux-native"
        assert payload["cwd"] == str(Path("/tmp"))
        assert payload["env"] == {"VAR": "val"}
        assert payload["expects_stdin"] is False

    def test_to_payload_with_stdin(self) -> None:
        spec = CommandSpec(backend_type="linux-native", argv=("cat",), stdin_text="input")
        payload = spec.to_payload()
        assert payload["expects_stdin"] is True

    def test_to_payload_with_metadata(self) -> None:
        spec = CommandSpec(
            backend_type="linux-native",
            argv=("echo",),
            metadata={"display_override": "custom display", "count": 5},
        )
        payload = spec.to_payload()
        assert payload["metadata"]["display_override"] == "custom display"
        assert payload["metadata"]["count"] == 5


# ---------------------------------------------------------------------------
# RenderedExecution
# ---------------------------------------------------------------------------


class TestRenderedExecution:
    def test_to_payload(self) -> None:
        rendered = RenderedExecution(
            backend_type="linux-native",
            argv=("echo", "hi"),
            display_command="echo hi",
            cwd="/tmp",
            env={"VAR": "val"},
            stdin_text=None,
            expected_outputs=("out",),
            capabilities=("ssh",),
        )
        payload = rendered.to_payload()
        assert payload["display_command"] == "echo hi"
        assert payload["expects_stdin"] is False
        assert payload["capabilities"] == ["ssh"]


# ---------------------------------------------------------------------------
# ExecutionResult
# ---------------------------------------------------------------------------


class TestExecutionResult:
    def test_to_payload_ok(self) -> None:
        result = ExecutionResult(
            backend_type="linux-native",
            argv=("echo",),
            display_command="echo",
            cwd=None,
            returncode=0,
            stdout="hi",
            stderr="",
            ok=True,
        )
        payload = result.to_payload()
        assert payload["ok"] is True
        assert "error" not in payload

    def test_to_payload_with_error(self) -> None:
        err = ExecutionError(category="command", message="fail", retryable=False, escalation="none")
        result = ExecutionResult(
            backend_type="linux-native",
            argv=("bad",),
            display_command="bad",
            cwd=None,
            returncode=1,
            stdout="",
            stderr="fail",
            ok=False,
            error=err,
        )
        payload = result.to_payload()
        assert payload["ok"] is False
        assert payload["error"]["category"] == "command"


# ---------------------------------------------------------------------------
# ExecutionBindings
# ---------------------------------------------------------------------------


class TestExecutionBindings:
    def test_resolve_cwd(self) -> None:
        bindings = ExecutionBindings(cwd_values={"repo": Path("/repo")})
        assert bindings.resolve_cwd("repo") == Path("/repo")

    def test_resolve_cwd_empty(self) -> None:
        bindings = ExecutionBindings()
        assert bindings.resolve_cwd("") is None

    def test_resolve_cwd_fallback(self) -> None:
        bindings = ExecutionBindings()
        assert bindings.resolve_cwd("/some/path") == "/some/path"

    def test_resolve_env(self) -> None:
        bindings = ExecutionBindings(env_values={"e1": {"A": "1"}, "e2": {"B": "2"}})
        result = bindings.resolve_env(("e1", "e2"))
        assert result == {"A": "1", "B": "2"}

    def test_resolve_env_missing_raises(self) -> None:
        bindings = ExecutionBindings()
        with pytest.raises(ValueError, match="missing env binding"):
            bindings.resolve_env(("nope",))

    def test_resolve_input(self) -> None:
        bindings = ExecutionBindings(input_values={"i1": "hello", "i2": " world"})
        assert bindings.resolve_input(("i1", "i2")) == "hello world"

    def test_resolve_input_empty(self) -> None:
        bindings = ExecutionBindings()
        assert bindings.resolve_input(()) is None

    def test_resolve_input_missing_raises(self) -> None:
        bindings = ExecutionBindings()
        with pytest.raises(ValueError, match="missing input binding"):
            bindings.resolve_input(("nope",))


# ---------------------------------------------------------------------------
# Golden test
# ---------------------------------------------------------------------------


@pytest.mark.golden
class TestExecutionGolden:
    def test_full_spec_render_classify_roundtrip(self) -> None:
        """CommandSpec → to_payload → classify error → ExecutionResult."""
        spec = CommandSpec(
            backend_type="linux-native",
            argv=("docker", "compose", "up", "-d"),
            cwd=Path("/repo"),
            env={"COMPOSE_PROJECT_NAME": "myapp"},
            timeout=120,
        )
        payload = spec.to_payload()
        assert payload["backend_type"] == "linux-native"
        assert payload["timeout"] == 120

        err = _classify_error(1, "Connection refused")
        assert err.category == "network"
        assert err.retryable is True

        result = ExecutionResult(
            backend_type="linux-native",
            argv=("docker", "compose", "up", "-d"),
            display_command="docker compose up -d",
            cwd=Path("/repo"),
            returncode=1,
            stdout="",
            stderr="Connection refused",
            ok=False,
            error=err,
        )
        result_payload = result.to_payload()
        assert result_payload["error"]["category"] == "network"
