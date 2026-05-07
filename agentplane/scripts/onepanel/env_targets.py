#!/usr/bin/env python3
"""Environment target resolution for repository-managed 1Panel operations."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from agentplane.runtime.platform import LinuxBackend, default_linux_backend
from agentplane.runtime.workspace import resolve_workspace_from_repo
from agentplane.ssh import SshTarget

from .client import OnePanelConfig, load_config


def resolve_repo_root(anchor: Path) -> Path:
    repo_candidate = anchor.parents[3]
    return resolve_workspace_from_repo(repo_candidate).control_root


REPO_ROOT = resolve_repo_root(Path(__file__).resolve())


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, capture_output=True, check=False, encoding="utf-8")


@dataclass(frozen=True)
class TargetConfig:
    name: str
    mode: str
    api_env_file: Path
    api_config: OnePanelConfig
    ssh_alias: str | None = None
    ssh_config: Path | None = None
    ssh_user: str | None = None
    ssh_requires_sudo: bool = False
    linux_backend: LinuxBackend | None = None
    tunnel_port: int | None = None

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


def get_target(name: str, env_file_override: str | None = None) -> TargetConfig:
    root = repo_root()
    workspace = resolve_workspace_from_repo(root)
    if name == "prod0-main":
        env_file = Path(env_file_override) if env_file_override else root / "secrets" / "services" / "onepanel-api.env"
        return TargetConfig(
            name=name,
            mode="ssh",
            api_env_file=env_file,
            api_config=load_config(env_file),
            ssh_alias="prod0-main",
            ssh_config=workspace.private_root / "ssh" / "config",
            ssh_user="root",
            ssh_requires_sudo=False,
            tunnel_port=2096,
        )
    if name == "wsl":
        host_truth_env = workspace.private_root / "hosts" / "wsl" / "onepanel" / "api.env"
        env_file = (
            Path(env_file_override)
            if env_file_override
            else (host_truth_env if host_truth_env.is_file() else workspace.private_root / "services" / "onepanel-api.wsl.env")
        )
        return TargetConfig(
            name=name,
            mode="local",
            api_env_file=env_file,
            api_config=load_config(env_file),
            linux_backend=default_linux_backend(),
        )
    raise ValueError(f"Unsupported target: {name}")


def supported_targets() -> tuple[str, ...]:
    return ("prod0-main", "wsl")
