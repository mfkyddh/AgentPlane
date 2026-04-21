from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WorkspaceContext:
    control_root: Path
    legacy_control_root: Path | None
    private_root: Path
    linux_backend_root: Path | None
    source_root: Path

    @property
    def local_command_root(self) -> Path:
        return self.source_root

    @property
    def artifact_staging_root(self) -> Path:
        base_root = self.linux_backend_root or self.control_root
        return base_root / ".agentplane" / "staging"


def _as_path(value: Path | str | None) -> Path | None:
    if value is None:
        return None
    if isinstance(value, Path):
        return value
    return Path(value)


def _looks_like_windows_root(path: Path) -> bool:
    rendered = str(path)
    return len(rendered) >= 2 and rendered[0].isalpha() and rendered[1] == ":"


def _looks_like_unc_path(path: Path) -> bool:
    rendered = str(path).replace("/", "\\")
    lowered = rendered.lower()
    return lowered.startswith("\\\\wsl.localhost\\") or lowered.startswith("\\\\wsl$\\")


def _looks_like_windows_mount_path(path: Path) -> bool:
    rendered = str(path).replace("\\", "/").lower().rstrip("/")
    if not rendered.startswith("/mnt/"):
        return False
    parts = rendered.split("/")
    return len(parts) >= 3 and len(parts[2]) == 1 and parts[2].isalpha()


def _assert_not_windows_mount(path: Path | None, *, field: str) -> None:
    if path is not None and _looks_like_windows_mount_path(path):
        raise ValueError(
            f"{field} cannot be a Windows-mounted WSL path: {path}. "
            "AgentPlane requires separate Windows and WSL checkouts."
        )


def _wsl_unc_to_posix(path: Path) -> Path | None:
    rendered = str(path).replace("/", "\\")
    lowered = rendered.lower()
    prefixes = ("\\\\wsl.localhost\\", "\\\\wsl$\\")
    if not any(lowered.startswith(prefix) for prefix in prefixes):
        return None
    parts = [part for part in rendered.split("\\") if part]
    if len(parts) < 3:
        return None
    return Path("/") / Path(*parts[2:])


def _windows_path_to_wsl_posix(path: Path) -> Path | None:
    unc_posix = _wsl_unc_to_posix(path)
    if unc_posix is not None:
        return unc_posix
    rendered = str(path)
    if rendered.startswith("/"):
        return Path(rendered)
    if not _looks_like_windows_root(path):
        return None
    drive = rendered[0].lower()
    tail = rendered[2:].replace("\\", "/").lstrip("/")
    return Path(f"/mnt/{drive}/{tail}") if tail else Path(f"/mnt/{drive}")


def _materialize_path(value: Path | str) -> Path:
    path = _as_path(value)
    if path is None:
        raise ValueError("path is required")
    if _looks_like_windows_root(path) or _looks_like_unc_path(path):
        return path
    return path.resolve()


def git_common_root(repo_root: Path) -> Path | None:
    git_entry = repo_root / ".git"
    if git_entry.is_dir():
        return repo_root
    if not git_entry.is_file():
        return None
    content = git_entry.read_text(encoding="utf-8").strip()
    prefix = "gitdir:"
    if not content.startswith(prefix):
        return None
    git_dir = Path(content[len(prefix) :].strip())
    if not git_dir.is_absolute():
        git_dir = (repo_root / git_dir).resolve()
    if len(git_dir.parts) >= 3 and git_dir.parent.name == "worktrees" and git_dir.parent.parent.name == ".git":
        return git_dir.parents[2]
    return None


def resolve_workspace(
    *,
    control_root: Path | str,
    legacy_control_root: Path | str | None = None,
    private_root: Path | str | None = None,
    linux_backend_root: Path | str | None = None,
    source_root: Path | str | None = None,
) -> WorkspaceContext:
    resolved_control_root = _as_path(control_root)
    resolved_legacy_control_root = _as_path(legacy_control_root)
    if resolved_control_root is None:
        raise ValueError("control_root is required")
    resolved_private_root = _as_path(private_root) or (resolved_control_root / "secrets")
    resolved_source_root = _as_path(source_root) or resolved_control_root
    _assert_not_windows_mount(resolved_control_root, field="control_root")
    _assert_not_windows_mount(resolved_legacy_control_root, field="legacy_control_root")
    _assert_not_windows_mount(resolved_source_root, field="source_root")
    if linux_backend_root is not None:
        resolved_linux_backend_root = _as_path(linux_backend_root)
        _assert_not_windows_mount(resolved_linux_backend_root, field="linux_backend_root")
    elif resolved_legacy_control_root is not None:
        resolved_linux_backend_root = resolved_legacy_control_root
    elif _looks_like_windows_root(resolved_control_root):
        resolved_linux_backend_root = None
    elif _looks_like_unc_path(resolved_control_root):
        resolved_linux_backend_root = _wsl_unc_to_posix(resolved_control_root)
    else:
        resolved_linux_backend_root = resolved_control_root
    return WorkspaceContext(
        control_root=resolved_control_root,
        legacy_control_root=resolved_legacy_control_root,
        private_root=resolved_private_root,
        linux_backend_root=resolved_linux_backend_root,
        source_root=resolved_source_root,
    )


def resolve_workspace_from_repo(repo_root: Path | str) -> WorkspaceContext:
    resolved_repo_root = _materialize_path(repo_root)
    control_root = git_common_root(resolved_repo_root) or resolved_repo_root
    return resolve_workspace(
        control_root=control_root,
        private_root=control_root / "secrets",
        source_root=resolved_repo_root,
    )
