from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from agentplane.runtime.workspace import WorkspaceContext, resolve_workspace_from_repo

PATH_POLICY_PAYLOAD = {
    "truth": "canonical-ref-only",
    "ledger": "summary-no-host-paths",
    "verification": "host-observation-allowed",
}


def _looks_like_windows_root(path: Path | str) -> bool:
    rendered = str(path)
    return len(rendered) >= 2 and rendered[0].isalpha() and rendered[1] == ":"


def _looks_like_unc_path(path: Path | str) -> bool:
    rendered = str(path).replace("/", "\\")
    lowered = rendered.lower()
    return lowered.startswith("\\\\wsl.localhost\\") or lowered.startswith("\\\\wsl$\\")


def _coerce_path(path: Path | str) -> Path:
    return path if isinstance(path, Path) else Path(path)


def materialize_path(base_root: Path | str, relative_path: Path | str | None = None) -> Path:
    base = _coerce_path(base_root)
    candidate = base if relative_path is None else base / _coerce_path(relative_path)
    if _looks_like_windows_root(candidate) or _looks_like_unc_path(candidate):
        return candidate
    return candidate.resolve()


@dataclass(frozen=True)
class ResolvedReference:
    canonical_ref: str
    resolved_path: Path

    def to_payload(
        self,
        *,
        render_path: Callable[[Path | None], str | None] | None = None,
    ) -> dict[str, str | None]:
        render = render_path or (lambda path: None if path is None else str(path))
        return {
            "canonical_ref": self.canonical_ref,
            "resolved_path": render(self.resolved_path),
        }


@dataclass(frozen=True)
class WorkspaceBindings:
    repo_root: Path
    control_root: Path
    legacy_control_root: Path | None
    private_root: Path
    linux_backend_root: Path | None
    artifact_staging_root: Path

    def to_payload(
        self,
        *,
        render_path: Callable[[Path | None], str | None] | None = None,
    ) -> dict[str, str | None]:
        render = render_path or (lambda path: None if path is None else str(path))
        return {
            "repo_root": render(self.repo_root),
            "control_root": render(self.control_root),
            "legacy_control_root": render(self.legacy_control_root),
            "private_root": render(self.private_root),
            "linux_backend_root": render(self.linux_backend_root),
            "artifact_staging_root": render(self.artifact_staging_root),
        }


class WorkspaceResolver:
    def __init__(self, *, repo_root: Path | str, workspace: WorkspaceContext) -> None:
        self._repo_root = materialize_path(repo_root)
        self._workspace = workspace

    @classmethod
    def from_repo_root(cls, repo_root: Path | str) -> "WorkspaceResolver":
        resolved_repo_root = materialize_path(repo_root)
        workspace = resolve_workspace_from_repo(resolved_repo_root)
        return cls(repo_root=resolved_repo_root, workspace=workspace)

    @classmethod
    def from_workspace(cls, *, repo_root: Path | str, workspace: WorkspaceContext) -> "WorkspaceResolver":
        return cls(repo_root=repo_root, workspace=workspace)

    @property
    def workspace(self) -> WorkspaceContext:
        return self._workspace

    @property
    def bindings(self) -> WorkspaceBindings:
        return WorkspaceBindings(
            repo_root=self._repo_root,
            control_root=self._workspace.control_root,
            legacy_control_root=self._workspace.legacy_control_root,
            private_root=self._workspace.private_root,
            linux_backend_root=self._workspace.linux_backend_root,
            artifact_staging_root=self._workspace.artifact_staging_root,
        )

    def resolve_relative_reference(
        self,
        *,
        canonical_ref: str,
        relative_path: Path | str,
        base_root: Path | str | None = None,
    ) -> ResolvedReference:
        root = self.bindings.repo_root if base_root is None else _coerce_path(base_root)
        return ResolvedReference(
            canonical_ref=canonical_ref,
            resolved_path=materialize_path(root, relative_path),
        )
