#!/usr/bin/env python3
"""Environment target resolution for repository-managed 1Panel operations."""

from __future__ import annotations

import re
import subprocess
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

from agentplane.runtime.platform import LinuxBackend, default_linux_backend
from agentplane.runtime.workspace import resolve_workspace_from_repo
from agentplane.ssh import SSHConnectionPool, SshTarget

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
    connection_pool: SSHConnectionPool | None = None
    remote_port: int = 9999

    def build_ssh_target(self) -> SshTarget:
        if not self.ssh_alias or not self.ssh_config:
            raise ValueError(f"Target {self.name} does not define SSH access")
        return SshTarget(
            alias=self.ssh_alias,
            config_path=self.ssh_config,
            user=self.ssh_user,
            os_family="linux",
            environment="production",
            connection_pool=self.connection_pool,
        )


def repo_root() -> Path:
    return REPO_ROOT


def _parse_ssh_config(config_path: Path) -> dict[str, dict[str, str]]:
    """Parse SSH config into {alias: {user, hostname, ...}}."""
    entries: dict[str, dict[str, str]] = {}
    current_alias: str | None = None
    if not config_path.is_file():
        return entries
    for raw_line in config_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^Host\s+(.+)$", line, re.IGNORECASE)
        if match:
            # First token is the primary alias
            current_alias = match.group(1).split()[0]
            entries[current_alias] = {}
            continue
        if current_alias:
            kv = line.split(None, 1)
            if len(kv) == 2:
                entries[current_alias][kv[0].lower()] = kv[1]
    return entries


def _derive_env_file(root: Path, target: str) -> Path:
    """Find the API env file for a target, checking target-specific first."""
    target_specific = root / "secrets" / "services" / f"onepanel-api.{target}.env"
    if target_specific.is_file():
        return target_specific
    host_specific = root / "secrets" / "hosts" / target / "onepanel" / "api.env"
    if host_specific.is_file():
        return host_specific
    return root / "secrets" / "services" / "onepanel-api.env"


def _derive_tunnel_port(config: OnePanelConfig) -> int | None:
    """Extract port from connect_base_url if it's a localhost address."""
    parsed = urllib.parse.urlparse(config.connect_base_url)
    if parsed.hostname in ("127.0.0.1", "localhost") and parsed.port:
        return parsed.port
    return None


def get_target(name: str, env_file_override: str | None = None) -> TargetConfig:
    root = repo_root()
    workspace = resolve_workspace_from_repo(root)
    ssh_config_path = workspace.private_root / "ssh" / "config"
    ssh_entries = _parse_ssh_config(ssh_config_path)

    # WSL: local mode with WSL backend
    if name == "wsl":
        env_file = Path(env_file_override) if env_file_override else _derive_env_file(root, name)
        return TargetConfig(
            name=name,
            mode="local",
            api_env_file=env_file,
            api_config=load_config(env_file),
            linux_backend=default_linux_backend(),
        )

    # SSH targets: derived from SSH config
    if name in ssh_entries:
        entry = ssh_entries[name]
        env_file = Path(env_file_override) if env_file_override else _derive_env_file(root, name)
        config = load_config(env_file)
        return TargetConfig(
            name=name,
            mode="ssh",
            api_env_file=env_file,
            api_config=config,
            ssh_alias=name,
            ssh_config=ssh_config_path,
            ssh_user=entry.get("user"),
            ssh_requires_sudo=entry.get("user") != "root",
            tunnel_port=_derive_tunnel_port(config),
        )

    raise ValueError(f"Unsupported target: {name}")


def supported_targets() -> tuple[str, ...]:
    root = repo_root()
    workspace = resolve_workspace_from_repo(root)
    ssh_config_path = workspace.private_root / "ssh" / "config"
    ssh_entries = _parse_ssh_config(ssh_config_path)
    return ("wsl", *ssh_entries.keys())
