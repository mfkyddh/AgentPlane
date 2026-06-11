"""Command step factories for local and remote execution backends."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agentplane.runtime.execution import CommandSpec, CommandStep, shell_join
from agentplane.ssh import SshTarget


def plan_local_backend_step(
    key: str,
    *,
    backend_type: str,
    cwd: Path | str,
    argv: tuple[str, ...],
    env: dict[str, str] | None = None,
    stdin_text: str | None = None,
    capabilities: tuple[str, ...] = (),
    expected_outputs: tuple[str, ...] = (),
    timeout: int = 300,
    display_command: str | None = None,
) -> CommandStep:
    return CommandStep(
        key=key,
        spec=CommandSpec(
            backend_type=backend_type,  # type: ignore[arg-type]
            argv=argv,
            cwd=cwd,
            env=env or {},
            stdin_text=stdin_text,
            expected_outputs=expected_outputs,
            capabilities=capabilities,
            timeout=timeout,
            metadata={"display_override": display_command or shell_join(argv)},
        ),
    )


def plan_remote_shell_step(
    key: str,
    *,
    ssh_target: SshTarget,
    cwd: str | None,
    argv: tuple[str, ...],
    shell_command: str | None = None,
    env: dict[str, str] | None = None,
    capabilities: tuple[str, ...] = (),
    expected_outputs: tuple[str, ...] = (),
    timeout: int = 300,
) -> CommandStep:
    metadata: dict[str, Any] = {"transport": "shell", "ssh_target": ssh_target}
    if shell_command is not None:
        metadata["shell_command"] = shell_command
    return CommandStep(
        key=key,
        spec=CommandSpec(
            backend_type="ssh-linux",
            argv=argv,
            cwd=cwd,
            env=env or {},
            expected_outputs=expected_outputs,
            capabilities=capabilities,
            timeout=timeout,
            metadata=metadata,
        ),
    )


def plan_remote_bash_stdin_step(
    key: str,
    *,
    ssh_target: SshTarget,
    argv: tuple[str, ...],
    stdin_text: str,
    capabilities: tuple[str, ...] = (),
    expected_outputs: tuple[str, ...] = (),
    timeout: int = 300,
) -> CommandStep:
    return CommandStep(
        key=key,
        spec=CommandSpec(
            backend_type="ssh-linux",
            argv=argv,
            stdin_text=stdin_text,
            expected_outputs=expected_outputs,
            capabilities=capabilities,
            timeout=timeout,
            metadata={"transport": "bash-stdin", "ssh_target": ssh_target},
        ),
    )


def plan_remote_copy_step(
    key: str,
    *,
    ssh_target: SshTarget,
    local_path: Path,
    remote_path: str,
    expected_outputs: tuple[str, ...] = (),
    timeout: int = 300,
) -> CommandStep:
    return CommandStep(
        key=key,
        spec=CommandSpec(
            backend_type="ssh-linux",
            argv=("scp", str(local_path), remote_path),
            expected_outputs=expected_outputs,
            capabilities=("scp",),
            timeout=timeout,
            metadata={
                "transport": "copy-to-remote",
                "ssh_target": ssh_target,
                "local_path": local_path,
                "remote_path": remote_path,
            },
        ),
    )
