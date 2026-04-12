from __future__ import annotations

import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import Any

from agentplane.runtime.host_profile import host_profile_from_platform
from agentplane.runtime.platform import HostPlatform, LinuxBackend, detect_host_platform, select_linux_backend
from agentplane.runtime.resolution import PATH_POLICY_PAYLOAD, WorkspaceResolver
from agentplane.runtime.secret_resolver import SecretResolver
from agentplane.runtime.target_resolver import TargetResolver
from agentplane.runtime.workspace import (
    WorkspaceContext,
    _windows_path_to_wsl_posix,
    _wsl_unc_to_posix,
    resolve_workspace,
)


DEFAULT_WSL_DISTRO = "Ubuntu"
PRIVATE_DIR_NAMES = ("secrets",)
MIGRATION_EXCLUDES = (".git", ".venv", "tmp", "__pycache__")


@dataclass(frozen=True)
class LocalLinuxBackendStatus:
    backend: LinuxBackend
    available: bool

    def to_payload(self) -> dict[str, Any]:
        return {
            "backend_type": self.backend.backend_type,
            "executable": list(self.backend.executable),
            "shell_executable": list(self.backend.shell_executable),
            "available": self.available,
        }


def is_windows_path(path: Path | str | None) -> bool:
    if path is None:
        return False
    rendered = str(path)
    return len(rendered) >= 2 and rendered[0].isalpha() and rendered[1] == ":"


def is_wsl_unc_path(path: Path | str | None) -> bool:
    if path is None:
        return False
    rendered = str(path).replace("/", "\\")
    lowered = rendered.lower()
    return lowered.startswith("\\\\wsl.localhost\\") or lowered.startswith("\\\\wsl$\\")


def normalize_wsl_posix_path(path: Path | str | None) -> str | None:
    if path is None:
        return None
    rendered = str(path)
    if rendered.startswith("\\\\"):
        return rendered
    if rendered.startswith("\\"):
        return rendered.replace("\\", "/")
    return rendered


def windows_path_to_wsl_posix(path: Path | str | None) -> str | None:
    if path is None:
        return None
    posix = _windows_path_to_wsl_posix(Path(path))
    return normalize_wsl_posix_path(posix) if posix is not None else None


def normalize_repo_root_for_current_host(
    path: Path | str,
    *,
    host_platform: HostPlatform | None = None,
) -> Path:
    facts = host_platform or detect_host_platform()
    rendered = str(path)
    if facts.os_name == "windows" and not facts.is_wsl:
        if is_windows_path(rendered) or is_wsl_unc_path(rendered):
            return Path(rendered).expanduser()
        if rendered.startswith("/"):
            unc_path = wsl_posix_to_unc(rendered)
            if unc_path is not None:
                return Path(unc_path)
    posix_path = windows_path_to_wsl_posix(path)
    if posix_path:
        return Path(posix_path).resolve()
    candidate = wsl_unc_to_posix(path)
    if candidate is not None:
        return candidate.resolve()
    normalized = normalize_wsl_posix_path(path)
    if normalized:
        maybe_posix = Path(normalized)
        if maybe_posix.is_absolute():
            return maybe_posix.resolve()
    return Path(path).expanduser().resolve()


def render_host_path(path: Path | str | None) -> str | None:
    if path is None:
        return None
    rendered = str(path)
    if is_windows_path(rendered):
        return str(PureWindowsPath(rendered))
    if rendered.startswith("\\") and not rendered.startswith("\\\\"):
        return rendered.replace("\\", "/")
    return rendered


def _coerce_path(path: Path | str | None) -> Path | None:
    if path is None:
        return None
    resolved = path if isinstance(path, Path) else Path(path)
    if is_windows_path(resolved) or is_wsl_unc_path(resolved) or str(path).startswith("/"):
        return resolved
    return resolved.resolve()


def wsl_unc_to_posix(path: Path | str | None) -> Path | None:
    if path is None:
        return None
    return _wsl_unc_to_posix(Path(path))


def wsl_posix_to_unc(path: Path | str | None, *, distro: str = DEFAULT_WSL_DISTRO) -> str | None:
    if path is None:
        return None
    rendered = str(path).replace("\\", "/")
    if not rendered.startswith("/"):
        return None
    tail = rendered.lstrip("/").replace("/", "\\")
    return f"\\\\wsl.localhost\\{distro}\\{tail}" if tail else f"\\\\wsl.localhost\\{distro}"


def resolve_local_workspace(
    repo_root: Path | str = ".",
    *,
    windows_root: Path | str | None = None,
    legacy_control_root: Path | str | None = None,
    host_platform: HostPlatform | None = None,
) -> WorkspaceContext:
    repo_path = _coerce_path(repo_root) or Path(".").resolve()
    facts = host_platform or detect_host_platform()

    if windows_root is not None:
        control_root = _coerce_path(windows_root) or repo_path
    else:
        control_root = repo_path

    if is_windows_path(control_root):
        resolved_legacy_root = _coerce_path(legacy_control_root)
        if resolved_legacy_root is None:
            resolved_legacy_root = wsl_unc_to_posix(repo_path)
        if resolved_legacy_root is None:
            posix_root = windows_path_to_wsl_posix(control_root)
            resolved_legacy_root = _coerce_path(posix_root)
        source_root = repo_path if is_windows_path(repo_path) else (resolved_legacy_root or repo_path)
        return resolve_workspace(
            control_root=control_root,
            legacy_control_root=resolved_legacy_root,
            private_root=control_root / "secrets",
            source_root=source_root,
        )

    resolved_legacy_root = _coerce_path(legacy_control_root)
    if resolved_legacy_root is None:
        resolved_legacy_root = wsl_unc_to_posix(control_root)
    source_root = resolved_legacy_root or repo_path
    return resolve_workspace(
        control_root=control_root,
        legacy_control_root=resolved_legacy_root,
        private_root=control_root / "secrets",
        source_root=source_root,
    )


def detect_local_linux_backend(
    workspace: WorkspaceContext,
    *,
    host_platform: HostPlatform | None = None,
) -> LocalLinuxBackendStatus:
    facts = host_platform or detect_host_platform()
    if is_windows_path(workspace.control_root):
        facts = HostPlatform(os_name="windows", has_wsl=shutil.which("wsl.exe") is not None, is_wsl=False)
    backend = select_linux_backend(facts)
    if backend.backend_type != "wsl-linux":
        return LocalLinuxBackendStatus(backend=backend, available=True)
    if shutil.which("wsl.exe") is None:
        return LocalLinuxBackendStatus(backend=backend, available=False)
    if workspace.linux_backend_root is None:
        return LocalLinuxBackendStatus(backend=backend, available=True)

    backend_root = normalize_wsl_posix_path(workspace.linux_backend_root) or str(workspace.linux_backend_root)
    try:
        probe = subprocess.run(
            backend.shell_argv(f"test -d {shlex.quote(backend_root)}"),
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError:
        return LocalLinuxBackendStatus(backend=backend, available=False)
    return LocalLinuxBackendStatus(backend=backend, available=probe.returncode == 0)


def inspect_local_host(
    repo_root: Path | str = ".",
    *,
    windows_root: Path | str | None = None,
    legacy_control_root: Path | str | None = None,
    host_platform: HostPlatform | None = None,
) -> dict[str, Any]:
    facts = host_platform or detect_host_platform()
    workspace = resolve_local_workspace(
        repo_root,
        windows_root=windows_root,
        legacy_control_root=legacy_control_root,
        host_platform=facts,
    )
    profile_facts = facts
    if is_windows_path(workspace.control_root):
        profile_facts = HostPlatform(os_name="windows", has_wsl=shutil.which("wsl.exe") is not None, is_wsl=False)
    profile = host_profile_from_platform(profile_facts)
    backend = detect_local_linux_backend(workspace, host_platform=profile_facts)
    repo_path = _coerce_path(repo_root) or Path(".").resolve()
    workspace_resolver = WorkspaceResolver.from_workspace(repo_root=repo_path, workspace=workspace)
    ssh_config = SecretResolver(workspace_resolver).resolve_ssh_config()
    local_target = TargetResolver(profile).resolve("wsl")
    return {
        "control_root": render_host_path(workspace.control_root),
        "legacy_control_root": render_host_path(workspace.legacy_control_root),
        "private_root": render_host_path(workspace.private_root),
        "linux_backend_root": render_host_path(workspace.linux_backend_root),
        "private_dirs": list(PRIVATE_DIR_NAMES),
        "linux_backend": backend.to_payload(),
        "host_profile": profile.to_payload(),
        "workspace": workspace_resolver.bindings.to_payload(render_path=render_host_path),
        "path_policy": dict(PATH_POLICY_PAYLOAD),
        "secret_bindings": {
            "ssh_config": ssh_config.to_payload(render_path=render_host_path),
        },
        "targets": {
            "wsl": local_target.to_payload(),
        },
    }


def plan_local_migration(
    repo_root: Path | str = ".",
    *,
    windows_root: Path | str | None = None,
    legacy_control_root: Path | str | None = None,
) -> dict[str, Any]:
    payload = inspect_local_host(
        repo_root,
        windows_root=windows_root,
        legacy_control_root=legacy_control_root,
    )
    source_root = wsl_posix_to_unc(payload["legacy_control_root"]) or payload["legacy_control_root"]
    control_root = payload["control_root"]
    private_root = render_host_path(Path(control_root) / "secrets") if control_root is not None else None
    return {
        **payload,
        "source_root": source_root,
        "windows_root": control_root,
        "copy_commands": [
            f'robocopy "{source_root}" "{control_root}" /MIR /XD {" ".join(MIGRATION_EXCLUDES)}',
            f'robocopy "{source_root}\\secrets" "{private_root}" /E',
        ],
    }


def plan_local_copy(
    repo_root: Path | str = ".",
    *,
    windows_root: Path | str | None = None,
    legacy_control_root: Path | str | None = None,
    execute: bool = False,
) -> dict[str, Any]:
    return {
        **plan_local_migration(
            repo_root,
            windows_root=windows_root,
            legacy_control_root=legacy_control_root,
        ),
        "execute_requested": execute,
        "executed": False,
        "ok": not execute,
        "message": "copy execution is planned but not run by default; use the emitted robocopy commands from a Windows host shell",
    }


def verify_local_migration(
    repo_root: Path | str = ".",
    *,
    windows_root: Path | str | None = None,
    legacy_control_root: Path | str | None = None,
) -> dict[str, Any]:
    payload = inspect_local_host(
        repo_root,
        windows_root=windows_root,
        legacy_control_root=legacy_control_root,
    )
    control_root = _coerce_path(payload["control_root"])
    private_root = _coerce_path(payload["private_root"])
    checks = [
        {
            "name": "control_root_exists",
            "ok": control_root is not None and control_root.exists(),
            "path": payload["control_root"],
        },
        {
            "name": "private_root_exists",
            "ok": private_root is not None and private_root.exists(),
            "path": payload["private_root"],
        },
        {
            "name": "linux_backend_available",
            "ok": bool(payload["linux_backend"]["available"]),
            "path": payload["linux_backend_root"],
        },
    ]
    return {
        **payload,
        "ok": all(check["ok"] for check in checks),
        "checks": checks,
    }
