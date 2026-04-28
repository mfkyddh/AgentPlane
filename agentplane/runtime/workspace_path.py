from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agentplane.runtime.workspace import (
    WorkspaceContext,
    _looks_like_windows_root,
    _windows_path_to_wsl_posix,
    _wsl_unc_to_posix,
)


@dataclass(frozen=True)
class WorkspacePath:
    """Unified path abstraction tied to a WorkspaceContext.

    Encapsulates cross-platform path conversion so callers do not need
    to branch on host OS or manually convert between Windows, WSL POSIX,
    and UNC representations.
    """

    workspace: WorkspaceContext
    canonical_ref: str

    @classmethod
    def from_physical(
        cls,
        workspace: WorkspaceContext,
        physical_path: Path | str,
    ) -> "WorkspacePath":
        """Derive a WorkspacePath from a physical path on the current host."""
        path = Path(physical_path)
        control = workspace.control_root
        try:
            rel = path.relative_to(control)
            canonical = str(rel.as_posix())
        except ValueError:
            # Fallback: treat the last part as a weak canonical ref.
            canonical = path.name
        return cls(workspace=workspace, canonical_ref=canonical)

    @property
    def posix_path(self) -> Path:
        """Physical POSIX path under *control_root*."""
        return self.workspace.control_root / self.canonical_ref

    @property
    def windows_path(self) -> Path | None:
        """Windows drive-letter path, if *control_root* looks like one."""
        if _looks_like_windows_root(self.workspace.control_root):
            return self.workspace.control_root / self.canonical_ref
        return None

    @property
    def wsl_path(self) -> Path | None:
        """WSL POSIX path (``/mnt/<drive>/...``), when applicable."""
        posix = _windows_path_to_wsl_posix(self.posix_path)
        return posix

    @property
    def unc_path(self) -> Path | None:
        """WSL UNC path (``\\\\wsl.localhost\\...``), when applicable."""
        unc = _wsl_unc_to_posix(self.workspace.control_root)
        if unc is not None:
            return unc / self.canonical_ref
        return None

    @property
    def linux_backend_path(self) -> Path | None:
        """Path seen from the Linux backend (same checkout under WSL)."""
        if self.workspace.linux_backend_root is not None:
            return self.workspace.linux_backend_root / self.canonical_ref
        return self.posix_path if not _looks_like_windows_root(self.posix_path) else None

    def joinpath(self, *parts: str) -> "WorkspacePath":
        return WorkspacePath(
            workspace=self.workspace,
            canonical_ref=str((Path(self.canonical_ref) / Path(*parts)).as_posix()),
        )

    def with_suffix(self, suffix: str) -> "WorkspacePath":
        return WorkspacePath(
            workspace=self.workspace,
            canonical_ref=str(Path(self.canonical_ref).with_suffix(suffix).as_posix()),
        )

    def to_payload(self) -> dict[str, str | None]:
        return {
            "canonical_ref": self.canonical_ref,
            "posix_path": str(self.posix_path),
            "windows_path": None if self.windows_path is None else str(self.windows_path),
            "wsl_path": None if self.wsl_path is None else str(self.wsl_path),
            "unc_path": None if self.unc_path is None else str(self.unc_path),
            "linux_backend_path": None if self.linux_backend_path is None else str(self.linux_backend_path),
        }
