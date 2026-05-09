from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from agentplane.domain.app.catalog import resolve_app_contract_reference
from agentplane.runtime.backends import build_backend_runner
from agentplane.runtime.execution import (
    ExecutionBindings,
    ExecutionError,
    ExecutionPlan,
    ExecutionResult,
)
from agentplane.runtime.host_profile import HostProfile
from agentplane.runtime.target_resolver import TargetResolver
from agentplane.ssh import SshTarget

pytestmark = pytest.mark.integration




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
