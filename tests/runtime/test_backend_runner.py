import os
import subprocess
from pathlib import Path

from agentplane.runtime.backends import WindowsWslBackend, build_backend_runner
from agentplane.runtime.execution import ExecutionBindings, ExecutionPlan
from agentplane.ssh import SshTarget


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
        assert rendered.argv[3:6] == ("-F", str(ssh_config), "root@prod0-main")
    else:
        assert rendered.argv[:4] == ("ssh", "-F", str(ssh_config), "root@prod0-main")
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

