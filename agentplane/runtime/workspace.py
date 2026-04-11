from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WorkspaceContext:
    control_root: Path
    legacy_control_root: Path | None
    private_root: Path
    linux_backend_root: Path | None

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
) -> WorkspaceContext:
    resolved_control_root = _as_path(control_root)
    resolved_legacy_control_root = _as_path(legacy_control_root)
    if resolved_control_root is None:
        raise ValueError("control_root is required")
    resolved_private_root = _as_path(private_root) or (resolved_control_root / "secrets")
    if linux_backend_root is not None:
        resolved_linux_backend_root = _as_path(linux_backend_root)
    elif resolved_legacy_control_root is not None:
        resolved_linux_backend_root = resolved_legacy_control_root
    elif _looks_like_windows_root(resolved_control_root):
        resolved_linux_backend_root = None
    else:
        resolved_linux_backend_root = resolved_control_root
    return WorkspaceContext(
        control_root=resolved_control_root,
        legacy_control_root=resolved_legacy_control_root,
        private_root=resolved_private_root,
        linux_backend_root=resolved_linux_backend_root,
    )


def resolve_workspace_from_repo(repo_root: Path | str) -> WorkspaceContext:
    resolved_repo_root = _materialize_path(repo_root)
    control_root = git_common_root(resolved_repo_root) or resolved_repo_root
    return resolve_workspace(
        control_root=control_root,
        private_root=control_root / "secrets",
        linux_backend_root=control_root,
    )
