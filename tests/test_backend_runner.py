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
    assert rendered.argv[:4] == ("ssh", "-F", str(ssh_config), "root@prod0-main")
    assert rendered.metadata["remote_command"] == "docker inspect sub2api-prod"
