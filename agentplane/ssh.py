from __future__ import annotations

import argparse
import atexit
import json
import os
import shlex
import socket
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from agentplane.runtime.secret_resolver import SecretResolver
from agentplane.runtime.wsl_bridge import windows_path_to_wsl_posix


def _local_backend_arg(value: str) -> str:
    if os.name != "nt":
        return value
    return windows_path_to_wsl_posix(value) or value


def _local_backend_argv(argv: list[str]) -> list[str]:
    if os.name != "nt" or os.environ.get("AGENTPLANE_DISABLE_WSL_SSH") == "1":
        return argv
    return ["wsl.exe", "-e", *[_local_backend_arg(part) for part in argv]]


@dataclass(frozen=True)
class SshTarget:
    alias: str
    config_path: Path
    user: str | None = None
    os_family: str = "linux"
    environment: str = "production"
    allocate_tty: bool = False
    connection_pool: SSHConnectionPool | None = field(default=None, repr=False)

    def _tty_flag(self) -> str:
        return "-t" if self.allocate_tty else "-T"

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

    def _pool_control_args(self) -> list[str]:
        if self.connection_pool is not None:
            self.connection_pool.ensure_connection(self.alias)
            return ["-o", "ControlMaster=auto"]
        return []

    def ssh_args_for_bash_stdin(self, argv: list[str] | None = None) -> list[str]:
        return [
            "ssh",
            self._tty_flag(),
            *self._pool_control_args(),
            "-F",
            str(self.config_path),
            self.connection_target,
            self.wrap_bash_stdin(argv),
        ]

    def local_ssh_args_for_bash_stdin(self, argv: list[str] | None = None) -> list[str]:
        return _local_backend_argv(self.ssh_args_for_bash_stdin(argv))

    def _display_pool_args(self) -> list[str]:
        if self.connection_pool is not None:
            return ["-o", "ControlMaster=auto"]
        return []

    def display_ssh_bash_stdin(self, argv: list[str] | None = None) -> str:
        return " ".join(
            [
                "ssh",
                self._tty_flag(),
                *self._display_pool_args(),
                "-F",
                shlex.quote(str(self.config_path)),
                shlex.quote(self.connection_target),
                shlex.quote(self.wrap_bash_stdin(argv)),
            ]
        )

    def ssh_args_for_argv(self, argv: list[str]) -> list[str]:
        return ["ssh", self._tty_flag(), *self._pool_control_args(), "-F", str(self.config_path), self.connection_target, self.wrap_argv(argv)]

    def local_ssh_args_for_argv(self, argv: list[str]) -> list[str]:
        return _local_backend_argv(self.ssh_args_for_argv(argv))

    def ssh_args_for_shell(self, command: str) -> list[str]:
        return ["ssh", self._tty_flag(), *self._pool_control_args(), "-F", str(self.config_path), self.connection_target, self.wrap_shell(command)]

    def local_ssh_args_for_shell(self, command: str) -> list[str]:
        return _local_backend_argv(self.ssh_args_for_shell(command))

    def display_ssh_command(self, command: str) -> str:
        return " ".join(
            [
                "ssh",
                self._tty_flag(),
                *self._display_pool_args(),
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
                self._tty_flag(),
                *self._display_pool_args(),
                "-F",
                shlex.quote(str(self.config_path)),
                shlex.quote(self.connection_target),
                shlex.quote(self.wrap_argv(argv)),
            ]
        )

    def scp_destination(self, remote_path: str) -> str:
        return f"{self.connection_target}:{remote_path}"

    def scp_args(self, local_path: str, remote_path: str) -> list[str]:
        return ["scp", *self._pool_control_args(), "-F", str(self.config_path), str(local_path), self.scp_destination(remote_path)]

    def local_scp_args(self, local_path: str, remote_path: str) -> list[str]:
        return _local_backend_argv(self.scp_args(local_path, remote_path))

    def display_scp_command(self, local_path: str, remote_path: str) -> str:
        return " ".join(
            [
                "scp",
                *self._display_pool_args(),
                "-F",
                shlex.quote(str(self.config_path)),
                shlex.quote(local_path),
                shlex.quote(self.scp_destination(remote_path)),
            ]
        )


class SSHConnectionPool:
    """SSH connection pool using ControlMaster for connection reuse."""

    def __init__(self, config_path: Path, persist_timeout: int = 600):
        self._config_path = config_path
        self._persist_timeout = persist_timeout
        self._initialized: set[str] = set()
        self._lock = threading.Lock()

    def ensure_connection(self, alias: str) -> None:
        with self._lock:
            if alias in self._initialized:
                return
            subprocess.run(
                [
                    "ssh",
                    "-o", "ControlMaster=yes",
                    "-o", f"ControlPersist={self._persist_timeout}s",
                    "-F", str(self._config_path),
                    alias,
                    "true",
                ],
                check=True,
                capture_output=True,
            )
            self._initialized.add(alias)

    def ssh_args(self, alias: str, command: str) -> list[str]:
        self.ensure_connection(alias)
        return [
            "ssh",
            "-o", "ControlMaster=auto",
            "-F", str(self._config_path),
            alias,
            command,
        ]

    def tunnel_args(self, alias: str, local_port: int, remote_port: int) -> list[str]:
        self.ensure_connection(alias)
        return [
            "ssh",
            "-o", "ControlMaster=auto",
            "-L", f"{local_port}:127.0.0.1:{remote_port}",
            "-F", str(self._config_path),
            "-N",
            alias,
        ]

    def scp_args(self, alias: str, local_path: str, remote_path: str) -> list[str]:
        self.ensure_connection(alias)
        return [
            "scp",
            "-o", "ControlMaster=auto",
            "-F", str(self._config_path),
            local_path,
            f"{alias}:{remote_path}",
        ]


class RemoteAPIClient:
    """SSH port-forwarding HTTP client for remote 1Panel API access."""

    def __init__(self, pool: SSHConnectionPool, alias: str, remote_port: int = 9999):
        self._pool = pool
        self._alias = alias
        self._remote_port = remote_port
        self._local_port: int | None = None
        self._tunnel_process: subprocess.Popen[bytes] | None = None
        atexit.register(self.close)

    def _find_free_port(self) -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("", 0))
            return s.getsockname()[1]

    def _probe_port(self, port: int, timeout: float = 5.0, interval: float = 0.1) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=1):
                    return True
            except OSError:
                time.sleep(interval)
        return False

    def _ensure_tunnel(self) -> int:
        if self._tunnel_process and self._tunnel_process.poll() is None:
            return self._local_port  # type: ignore[return-value]
        self._local_port = self._find_free_port()
        self._tunnel_process = subprocess.Popen(
            self._pool.tunnel_args(self._alias, self._local_port, self._remote_port),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if not self._probe_port(self._local_port):
            self.close()
            raise ConnectionError(f"SSH tunnel to {self._alias}:{self._remote_port} failed to open")
        return self._local_port  # type: ignore[return-value]

    @property
    def local_port(self) -> int:
        port = self._ensure_tunnel()
        return port  # type: ignore[return-value]

    def close(self) -> None:
        if self._tunnel_process and self._tunnel_process.poll() is None:
            self._tunnel_process.terminate()
            self._tunnel_process.wait(timeout=5)

    def __enter__(self) -> RemoteAPIClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def resolve_ssh_config_path(repo_root: Path) -> Path:
    return SecretResolver.from_repo_root(repo_root).ssh_config_path()


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
