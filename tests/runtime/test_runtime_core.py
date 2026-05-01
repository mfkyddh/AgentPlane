from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from agentplane.domain.app.catalog import resolve_app_contract_reference
from agentplane.runtime.backends import BackendRunner, WindowsWslBackend, build_backend_runner
from agentplane.runtime.backends.registry import BackendRegistry
from agentplane.runtime.execution import (
    ExecutionBindings,
    ExecutionError,
    ExecutionPlan,
    ExecutionResult,
    StreamChunk,
    _classify_error,
)
from agentplane.runtime.host_profile import HostProfile
from agentplane.runtime.target_resolver import TargetResolver
from agentplane.ssh import SshTarget

pytestmark = pytest.mark.integration


def test_registry_self_registers_backends() -> None:
    runner = build_backend_runner()
    assert isinstance(runner, BackendRunner)
    # All four default backends should be present.
    assert set(runner._backends.keys()) == {"linux-native", "windows-wsl", "macos-lima", "ssh-linux"}


def test_registry_tracks_registered_types() -> None:
    registry = BackendRegistry()
    registry.register("fake", object)
    assert registry.registered_types() == ("fake",)


def test_registry_duplicate_registration_raises() -> None:
    registry = BackendRegistry()
    registry.register("fake", object)
    try:
        registry.register("fake", str)
        raise AssertionError("should have raised ValueError")
    except ValueError as exc:
        assert "already registered" in str(exc)


def test_register_backend_decorator() -> None:
    registry = BackendRegistry()

    def _decorator(cls: type) -> type:
        return registry.register("demo", cls)

    @_decorator
    class DemoBackend:
        pass

    assert "demo" in registry.registered_types()
    runner = registry.build_runner()
    assert isinstance(runner._backends["demo"], DemoBackend)


# ======================================================================
# From: test_backend_runner.py
# ======================================================================


def test_windows_wsl_backend_routes_windows_checkout_cwd_through_wsl_bridge(monkeypatch) -> None:
    monkeypatch.setattr("agentplane.runtime.backends.windows_wsl.require_local_executable", lambda _name: None)
    plan = ExecutionPlan(
        backend_type="windows-wsl",
        cwd_ref="workspace.control_root",
        argv=("docker", "ps"),
        env_refs=(),
        input_refs=(),
        expected_outputs=(),
        capabilities=("docker",),
        timeout=300,
    )

    rendered = WindowsWslBackend().render(
        plan,
        ExecutionBindings(cwd_values={"workspace.control_root": "C:/Users/example/AgentPlane"}),
    )

    assert rendered.argv[:4] == ("wsl.exe", "-e", "bash", "-lc")
    assert rendered.metadata["linux_command"] == "cd /mnt/c/Users/example/AgentPlane && docker ps"


def test_backend_runner_renders_ssh_linux_shell_plan() -> None:
    ssh_config = Path("/tmp/ssh-config")
    ssh_target = SshTarget(alias="prod0-main", config_path=ssh_config, user="root")
    plan = ExecutionPlan(
        backend_type="ssh-linux",
        cwd_ref="",
        argv=("docker", "inspect", "sub2api-prod"),
        env_refs=(),
        input_refs=(),
        expected_outputs=(),
        capabilities=("ssh", "docker"),
        timeout=300,
    )

    rendered = build_backend_runner().render(
        plan,
        bindings=ExecutionBindings(metadata={"transport": "shell", "ssh_target": ssh_target}),
    )

    assert rendered.backend_type == "ssh-linux"
    if os.name == "nt":
        assert rendered.argv[:3] == ("wsl.exe", "-e", "ssh")
        assert rendered.argv[3] == "-T"
        assert rendered.argv[4:7] == ("-F", str(ssh_config), "root@prod0-main")
    else:
        assert rendered.argv[:5] == ("ssh", "-T", "-F", str(ssh_config), "root@prod0-main")
    assert rendered.metadata["remote_command"] == "docker inspect sub2api-prod"


def test_backend_runner_uses_binary_stdin_for_windows_wsl(monkeypatch) -> None:
    monkeypatch.setattr("agentplane.runtime.execution.os.name", "nt")
    monkeypatch.setattr("agentplane.runtime.backends.windows_wsl.require_local_executable", lambda _name: None)
    captured: dict[str, object] = {}

    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        captured.update(kwargs)
        return subprocess.CompletedProcess(argv, 0, stdout=b"ok\n", stderr=b"")

    monkeypatch.setattr("agentplane.runtime.execution.subprocess.run", fake_run)
    plan = ExecutionPlan(
        backend_type="windows-wsl",
        cwd_ref="workspace.control_root",
        argv=("bash", "-s", "--"),
        env_refs=(),
        input_refs=("remote.stdin",),
        expected_outputs=(),
        capabilities=("bash",),
        timeout=300,
    )

    result = build_backend_runner().execute(
        plan,
        bindings=ExecutionBindings(
            cwd_values={"workspace.control_root": "D:/Projects/AgentPlane"},
            input_values={"remote.stdin": "set -euo pipefail\n"},
        ),
    )

    assert result.ok
    assert captured["input"] == b"set -euo pipefail\n"
    assert captured["text"] is False


# ======================================================================
# From: test_execute_stream.py
# ======================================================================


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
            "agentplane.runtime.execution.subprocess.run",
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


# ======================================================================
# From: test_ssh_tty_and_batch.py
# ======================================================================


def test_ssh_target_default_uses_no_tty() -> None:
    target = SshTarget(alias="prod0-main", config_path=Path("/tmp/ssh-config"), user="root")
    assert target._tty_flag() == "-T"
    assert target.ssh_args_for_bash_stdin()[1] == "-T"


def test_ssh_target_allocate_tty_uses_t() -> None:
    target = SshTarget(alias="prod0-main", config_path=Path("/tmp/ssh-config"), user="root", allocate_tty=True)
    assert target._tty_flag() == "-t"
    assert target.ssh_args_for_bash_stdin()[1] == "-t"


def test_backend_runner_execute_batch_runs_serially(monkeypatch) -> None:
    monkeypatch.setattr("agentplane.runtime.backends.linux_native.require_local_executable", lambda _name: None)
    call_count = 0

    def fake_run(argv: list[str], **kwargs: object):
        nonlocal call_count
        call_count += 1
        from subprocess import CompletedProcess

        return CompletedProcess(argv, 0, stdout=f"ok{call_count}", stderr="")

    monkeypatch.setattr("agentplane.runtime.execution.subprocess.run", fake_run)
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
    results = runner.execute_batch(
        plan,
        bindings_list=[
            ExecutionBindings(),
            ExecutionBindings(),
        ],
    )
    assert len(results) == 2
    assert results[0].stdout == "ok1"
    assert results[1].stdout == "ok2"


def test_backend_runner_execute_batch_on_each_callback(monkeypatch) -> None:
    monkeypatch.setattr("agentplane.runtime.backends.linux_native.require_local_executable", lambda _name: None)

    def fake_run(argv: list[str], **kwargs: object):
        from subprocess import CompletedProcess

        return CompletedProcess(argv, 0, stdout="done", stderr="")

    monkeypatch.setattr("agentplane.runtime.execution.subprocess.run", fake_run)
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
    collected: list[str] = []
    runner.execute_batch(
        plan,
        bindings_list=[ExecutionBindings(), ExecutionBindings()],
        on_each=lambda r: collected.append(r.stdout),
    )
    assert collected == ["done", "done"]


# ======================================================================
# From: test_runtime_resolution.py
# ======================================================================


def test_workspace_resolver_returns_canonical_and_resolved_paths() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo_root = Path(tmp)
        app_root = repo_root / "sub2api"
        contract_file = app_root / "deploy" / "agentplane" / "contract.yaml"
        contract_file.parent.mkdir(parents=True, exist_ok=True)
        contract_file.write_text("app_id: sub2api\n", encoding="utf-8")
        catalog_root = repo_root / "inventory" / "apps"
        catalog_root.mkdir(parents=True, exist_ok=True)
        (catalog_root / "catalog.json").write_text(
            json.dumps(
                {
                    "apps": [
                        {
                            "app": "sub2api",
                            "repo_name": "sub2api",
                            "repo_root": str(app_root),
                            "service_key": "sub2api",
                            "contracts": {"prod0-main": "deploy/agentplane/contract.yaml"},
                        }
                    ]
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        _, result = resolve_app_contract_reference(repo_root, target="prod0-main", app="sub2api")

        assert result.canonical_ref == "apps/sub2api/contracts/prod0-main"
        assert result.resolved_path.samefile(contract_file)


def test_target_resolver_distinguishes_local_and_remote_execution_policies() -> None:
    resolver = TargetResolver(HostProfile(os_name="windows", linux_backend="windows-wsl", supports_docker=True))

    local = resolver.resolve("wsl")
    remote = resolver.resolve("prod0-main")

    assert local.execution_backend == "windows-wsl"
    assert local.ssh_alias is None
    assert local.is_local is True
    assert remote.execution_backend == "ssh-linux"
    assert remote.ssh_alias == "prod0-main"
    assert remote.is_local is False
