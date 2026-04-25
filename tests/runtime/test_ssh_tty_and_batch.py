from pathlib import Path

from agentplane.runtime.execution import ExecutionBindings, ExecutionPlan
from agentplane.runtime.backends import build_backend_runner
from agentplane.ssh import SshTarget


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
