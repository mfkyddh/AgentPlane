#!/usr/bin/env python3
"""Environment target resolution for repository-managed 1Panel operations."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path
import shlex
import subprocess
import sys

from agentplane.runtime.platform import LinuxBackend, default_linux_backend
from agentplane.runtime.workspace import resolve_workspace_from_repo

def resolve_repo_root(anchor: Path) -> Path:
    repo_candidate = anchor.parents[3]
    return resolve_workspace_from_repo(repo_candidate).control_root


REPO_ROOT = resolve_repo_root(Path(__file__).resolve())
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agentplane.ssh import SshTarget


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, capture_output=True, check=False)


@dataclass(frozen=True)
class TargetConfig:
    name: str
    mode: str
    api_env_file: Path
    api_request_script: Path
    ssh_alias: str | None = None
    ssh_config: Path | None = None
    ssh_user: str | None = None
    ssh_requires_sudo: bool = False
    linux_backend: LinuxBackend | None = None

    def build_ssh_target(self) -> SshTarget:
        if not self.ssh_alias or not self.ssh_config:
            raise ValueError(f"Target {self.name} does not define SSH access")
        return SshTarget(
            alias=self.ssh_alias,
            config_path=self.ssh_config,
            user=self.ssh_user,
            os_family="linux",
            environment="production",
        )


def repo_root() -> Path:
    return REPO_ROOT


def _remote_api_path_candidates(default_env_file: Path, default_script: Path) -> tuple[tuple[Path, Path], ...]:
    # Compatibility contract: production targets still probe the historical
    # `api_request.py` path, including `/opt/env_ubuntu/...`, until the remote
    # estate no longer depends on that location.
    candidates = [(default_env_file, default_script)]
    live_repo_pair = (
        Path("/root/work/AgentPlane/secrets/services/onepanel-api.env"),
        Path("/root/work/AgentPlane/agentplane/scripts/onepanel/api_request.py"),
    )
    legacy_pair = (
        Path("/opt/env_ubuntu/secrets/services/onepanel-api.env"),
        Path("/opt/env_ubuntu/agentplane/scripts/onepanel/api_request.py"),
    )
    for pair in (live_repo_pair, legacy_pair):
        if pair not in candidates:
            candidates.append(pair)
    return tuple(candidates)


@lru_cache(maxsize=None)
def _resolve_remote_api_paths(
    ssh_alias: str,
    ssh_config: str,
    ssh_user: str | None,
    default_env_file: str,
    default_script: str,
) -> tuple[Path, Path]:
    ssh_target = SshTarget(
        alias=ssh_alias,
        config_path=Path(ssh_config),
        user=ssh_user,
        os_family="linux",
        environment="production",
    )
    default_env_path = Path(default_env_file)
    default_script_path = Path(default_script)
    candidates = _remote_api_path_candidates(default_env_path, default_script_path)

    probe_lines = ["set -euo pipefail"]
    for env_file, script in candidates:
        quoted_env = shlex.quote(str(env_file))
        quoted_script = shlex.quote(str(script))
        probe_lines.append(
            f"if [ -f {quoted_env} ] && [ -f {quoted_script} ]; then printf '%s\\n%s\\n' {quoted_env} {quoted_script}; exit 0; fi"
        )
    probe_lines.append(
        "printf '%s\\n%s\\n' "
        f"{shlex.quote(str(default_env_path))} {shlex.quote(str(default_script_path))}"
    )

    result = run_command(ssh_target.ssh_args_for_shell("; ".join(probe_lines)))
    if result.returncode != 0:
        return default_env_path, default_script_path
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if len(lines) >= 2:
        return Path(lines[0]), Path(lines[1])
    return default_env_path, default_script_path


def resolve_api_paths(target: TargetConfig) -> tuple[Path, Path]:
    if target.mode != "ssh":
        return target.api_env_file, target.api_request_script
    if not target.ssh_alias or not target.ssh_config:
        return target.api_env_file, target.api_request_script
    return _resolve_remote_api_paths(
        target.ssh_alias,
        str(target.ssh_config),
        target.ssh_user,
        str(target.api_env_file),
        str(target.api_request_script),
    )


def build_api_request_command(
    target: TargetConfig,
    method: str,
    path: str,
    *,
    body: dict[str, object] | None = None,
    query: dict[str, object] | None = None,
) -> list[str]:
    env_file, script = resolve_api_paths(target)
    command = [
        "python3",
        str(script),
        method,
        path,
        "--env-file",
        str(env_file),
    ]
    if body is not None:
        command.extend(["--body-json", json.dumps(body, ensure_ascii=False)])
    if query:
        command.extend(["--query-json", json.dumps(query, ensure_ascii=False)])
    return command


def get_target(name: str, env_file_override: str | None = None) -> TargetConfig:
    root = repo_root()
    workspace = resolve_workspace_from_repo(root)
    if name == "prod0-main":
        return TargetConfig(
            name=name,
            mode="ssh",
            api_env_file=Path("/opt/agentplane/secrets/services/onepanel-api.env"),
            api_request_script=Path("/opt/agentplane/agentplane/scripts/onepanel/api_request.py"),
            ssh_alias="prod0-main",
            ssh_config=workspace.private_root / "ssh" / "config",
            ssh_user="root",
            ssh_requires_sudo=False,
        )
    if name == "prod2-main":
        return TargetConfig(
            name=name,
            mode="ssh",
            api_env_file=Path("/opt/agentplane/secrets/services/onepanel-api.env"),
            api_request_script=Path("/opt/agentplane/agentplane/scripts/onepanel/api_request.py"),
            ssh_alias="prod2-main",
            ssh_config=workspace.private_root / "ssh" / "config",
            ssh_user="root",
            ssh_requires_sudo=False,
        )
    if name == "wsl":
        host_truth_env = workspace.private_root / "hosts" / "wsl" / "onepanel" / "api.env"
        default_env = host_truth_env if host_truth_env.is_file() else workspace.private_root / "services" / "onepanel-api.wsl.env"
        return TargetConfig(
            name=name,
            mode="local",
            api_env_file=Path(env_file_override) if env_file_override else default_env,
            api_request_script=workspace.control_root / "agentplane/scripts/onepanel/api_request.py",
            linux_backend=default_linux_backend(),
        )
    raise ValueError(f"Unsupported target: {name}")


def supported_targets() -> tuple[str, ...]:
    return ("prod0-main", "prod2-main", "wsl")
