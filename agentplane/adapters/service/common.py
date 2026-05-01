from __future__ import annotations

import os
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path

from agentplane.runtime.wsl_bridge import windows_path_to_wsl_posix
from agentplane.ssh import resolve_ssh_target


@dataclass(frozen=True)
class CommandSpec:
    argv: list[str]
    display: str


def remote_repo_root(target: str, repo_root: Path) -> str:
    if target == "wsl":
        return windows_path_to_wsl_posix(repo_root) or str(repo_root)
    return "/opt/agentplane"


def shell_command_spec(repo_root: Path, target: str, command: str) -> CommandSpec:
    if target == "wsl":
        if os.name == "nt":
            return CommandSpec(argv=["wsl.exe", "-e", "bash", "-lc", command], display=f"wsl.exe -e bash -lc {command}")
        return CommandSpec(argv=["bash", "-lc", command], display=command)
    ssh_target = resolve_ssh_target(repo_root, target)
    return CommandSpec(
        argv=ssh_target.local_ssh_args_for_shell(command), display=ssh_target.display_ssh_command(command)
    )


def copy_file_spec(repo_root: Path, target: str, local_path: Path, remote_path: str) -> CommandSpec:
    if target == "wsl":
        rendered_local = windows_path_to_wsl_posix(local_path) or str(local_path)
        command = f"install -D {shlex.quote(rendered_local)} {shlex.quote(remote_path)}"
        if os.name == "nt":
            return CommandSpec(argv=["wsl.exe", "-e", "bash", "-lc", command], display=f"wsl.exe -e bash -lc {command}")
        return CommandSpec(argv=["bash", "-lc", command], display=command)
    ssh_target = resolve_ssh_target(repo_root, target)
    return CommandSpec(
        argv=ssh_target.local_scp_args(str(local_path), remote_path),
        display=ssh_target.display_scp_command(str(local_path), remote_path),
    )


def run_shell_command(repo_root: Path, target: str, command: str) -> dict[str, object]:
    spec = shell_command_spec(repo_root, target, command)
    return run_command_argv(spec.argv, spec.display)


def run_command_argv(argv: list[str], display: str) -> dict[str, object]:
    result = subprocess.run(argv, text=True, capture_output=True, check=False)
    return {
        "argv": argv,
        "display": display,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "ok": result.returncode == 0,
    }
