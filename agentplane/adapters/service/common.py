from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from agentplane.ssh import resolve_ssh_target


@dataclass(frozen=True)
class CommandSpec:
    argv: list[str]
    display: str


def remote_repo_root(target: str, repo_root: Path) -> str:
    if target == "wsl":
        return str(repo_root)
    return "/opt/agentplane"


def shell_command_spec(repo_root: Path, target: str, command: str) -> CommandSpec:
    if target == "wsl":
        return CommandSpec(argv=["bash", "-lc", command], display=command)
    ssh_target = resolve_ssh_target(repo_root, target)
    return CommandSpec(argv=ssh_target.ssh_args_for_shell(command), display=ssh_target.display_ssh_command(command))


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
