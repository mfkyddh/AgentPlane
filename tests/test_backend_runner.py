from pathlib import Path

from agentplane.runtime.backends import WindowsWslBackend, build_backend_runner
from agentplane.runtime.execution import ExecutionBindings, ExecutionPlan
from agentplane.ssh import SshTarget


def test_windows_wsl_backend_wraps_linux_command() -> None:
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
        ExecutionBindings(cwd_values={"workspace.control_root": "D:/Projects/AgentPlane"}),
    )

    assert rendered.argv[:3] == ("wsl.exe", "-e", "bash")
    assert "docker ps" in rendered.argv[-1]
    assert "/mnt/d/Projects/AgentPlane" in rendered.argv[-1]


def test_backend_runner_renders_ssh_linux_shell_plan() -> None:
    ssh_target = SshTarget(alias="prod0-main", config_path=Path("/tmp/ssh-config"), user="root")
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
    assert rendered.argv[:4] == ("ssh", "-F", "/tmp/ssh-config", "root@prod0-main")
    assert rendered.metadata["remote_command"] == "docker inspect sub2api-prod"
