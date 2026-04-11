from __future__ import annotations

import argparse
import json
import shlex
from dataclasses import dataclass
from pathlib import Path

from agentplane.runtime.workspace import resolve_workspace_from_repo


@dataclass(frozen=True)
class SshTarget:
    alias: str
    config_path: Path
    user: str | None = None
    os_family: str = "linux"
    environment: str = "production"

    @property
    def connection_target(self) -> str:
        if self.user:
            return f"{self.user}@{self.alias}"
        return self.alias

    @property
    def requires_sudo(self) -> bool:
        return self.os_family == "linux" and self.environment == "production" and self.user != "root"

    def wrap_argv(self, argv: list[str]) -> str:
        effective = list(argv)
        if self.requires_sudo:
            effective.insert(0, "sudo")
        return " ".join(shlex.quote(part) for part in effective)

    def wrap_shell(self, command: str) -> str:
        shell_command = f"bash -lc {shlex.quote(command)}"
        if self.requires_sudo:
            return f"sudo {shell_command}"
        return shell_command

    def wrap_bash_stdin(self, argv: list[str] | None = None) -> str:
        effective = ["bash", "-s", "--"]
        if argv:
            effective.extend(argv)
        return self.wrap_argv(effective)

    def ssh_args_for_bash_stdin(self, argv: list[str] | None = None) -> list[str]:
        return ["ssh", "-T", "-F", str(self.config_path), self.connection_target, self.wrap_bash_stdin(argv)]

    def display_ssh_bash_stdin(self, argv: list[str] | None = None) -> str:
        return " ".join(
            [
                "ssh",
                "-T",
                "-F",
                shlex.quote(str(self.config_path)),
                shlex.quote(self.connection_target),
                shlex.quote(self.wrap_bash_stdin(argv)),
            ]
        )

    def ssh_args_for_argv(self, argv: list[str]) -> list[str]:
        return ["ssh", "-F", str(self.config_path), self.connection_target, self.wrap_argv(argv)]

    def ssh_args_for_shell(self, command: str) -> list[str]:
        return ["ssh", "-F", str(self.config_path), self.connection_target, self.wrap_shell(command)]

    def display_ssh_command(self, command: str) -> str:
        return " ".join(
            [
                "ssh",
                "-F",
                shlex.quote(str(self.config_path)),
                shlex.quote(self.connection_target),
                shlex.quote(self.wrap_shell(command)),
            ]
        )

    def display_ssh_argv(self, argv: list[str]) -> str:
        return " ".join(
            [
                "ssh",
                "-F",
                shlex.quote(str(self.config_path)),
                shlex.quote(self.connection_target),
                shlex.quote(self.wrap_argv(argv)),
            ]
        )

    def scp_destination(self, remote_path: str) -> str:
        return f"{self.connection_target}:{remote_path}"

    def display_scp_command(self, local_path: str, remote_path: str) -> str:
        return " ".join(
            [
                "scp",
                "-F",
                shlex.quote(str(self.config_path)),
                shlex.quote(local_path),
                shlex.quote(self.scp_destination(remote_path)),
            ]
        )


def resolve_ssh_config_path(repo_root: Path) -> Path:
    workspace = resolve_workspace_from_repo(repo_root)
    return workspace.private_root / "ssh" / "config"


def resolve_ssh_target(repo_root: Path, alias: str) -> SshTarget:
    inventory_root = repo_root / "inventory" / "servers"
    config_path = resolve_ssh_config_path(repo_root)
    if inventory_root.is_dir():
        for inventory_file in sorted(inventory_root.glob("*/inventory.json")):
            try:
                payload = json.loads(inventory_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(payload, dict):
                continue
            ssh_section = payload.get("ssh")
            if not isinstance(ssh_section, dict):
                continue
            aliases = ssh_section.get("aliases")
            if not isinstance(aliases, list) or alias not in aliases:
                continue
            user = ssh_section.get("user")
            if user is not None and not isinstance(user, str):
                user = None
            return SshTarget(
                alias=alias,
                config_path=config_path,
                user=user,
                os_family="linux",
                environment="production",
            )
    return SshTarget(alias=alias, config_path=config_path)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Resolve repository-managed SSH targets")
    parser.add_argument("--repo-root", default=".", help="Repository root path")
    parser.add_argument(
        "action",
        choices=("connection-target", "config-path", "bash-stdin-command"),
        help="Action to perform",
    )
    parser.add_argument("alias", nargs="?", help="SSH alias")
    parser.add_argument("remote_args", nargs=argparse.REMAINDER, help="Arguments passed to remote bash stdin wrapper")
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()
    if args.action == "config-path":
        print(resolve_ssh_config_path(repo_root))
        return 0
    if not args.alias:
        parser.error("alias is required for connection-target")
    target = resolve_ssh_target(repo_root, args.alias)
    if args.action == "connection-target":
        print(target.connection_target)
        return 0
    if args.action == "bash-stdin-command":
        remote_args = list(args.remote_args)
        if remote_args[:1] == ["--"]:
            remote_args = remote_args[1:]
        print(target.wrap_bash_stdin(remote_args))
        return 0
    parser.error(f"Unsupported action: {args.action}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
