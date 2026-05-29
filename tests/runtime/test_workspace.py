"""Tests for agentplane.runtime.workspace — pure helper functions."""

from __future__ import annotations

from pathlib import Path

import pytest
from agentplane.runtime.workspace import (
    WorkspaceContext,
    _as_path,
    _looks_like_unc_path,
    _looks_like_windows_root,
    _materialize_path,
    _windows_path_to_wsl_posix,
    _wsl_unc_to_posix,
    resolve_workspace,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# _as_path
# ---------------------------------------------------------------------------


class TestAsPath:
    def test_none(self) -> None:
        assert _as_path(None) is None

    def test_string(self) -> None:
        assert _as_path("/tmp") == Path("/tmp")

    def test_path(self) -> None:
        assert _as_path(Path("/tmp")) == Path("/tmp")


# ---------------------------------------------------------------------------
# _looks_like_windows_root
# ---------------------------------------------------------------------------


class TestLooksLikeWindowsRoot:
    def test_drive_letter(self) -> None:
        assert _looks_like_windows_root(Path("C:\\Users")) is True

    def test_lowercase(self) -> None:
        assert _looks_like_windows_root(Path("d:\\Projects")) is True

    def test_posix(self) -> None:
        assert _looks_like_windows_root(Path("/home")) is False

    def test_relative(self) -> None:
        assert _looks_like_windows_root(Path("relative")) is False


# ---------------------------------------------------------------------------
# _looks_like_unc_path
# ---------------------------------------------------------------------------


class TestLooksLikeUncPath:
    def test_wsl_localhost(self) -> None:
        assert _looks_like_unc_path(Path("\\\\wsl.localhost\\Ubuntu\\home")) is True

    def test_wsl_dollar(self) -> None:
        assert _looks_like_unc_path(Path("\\\\wsl$\\Ubuntu\\home")) is True

    def test_regular_unc(self) -> None:
        assert _looks_like_unc_path(Path("\\\\server\\share")) is False

    def test_posix(self) -> None:
        assert _looks_like_unc_path(Path("/home")) is False


# ---------------------------------------------------------------------------
# _wsl_unc_to_posix
# ---------------------------------------------------------------------------


class TestWslUncToPosix:
    def test_basic(self) -> None:
        result = _wsl_unc_to_posix(Path("\\\\wsl.localhost\\Ubuntu\\home\\user"))
        assert result == Path("/home/user")

    def test_wsl_dollar(self) -> None:
        result = _wsl_unc_to_posix(Path("\\\\wsl$\\Ubuntu\\home\\user"))
        assert result == Path("/home/user")

    def test_non_wsl(self) -> None:
        assert _wsl_unc_to_posix(Path("\\\\server\\share")) is None

    def test_too_few_parts(self) -> None:
        assert _wsl_unc_to_posix(Path("\\\\wsl.localhost")) is None


# ---------------------------------------------------------------------------
# _windows_path_to_wsl_posix
# ---------------------------------------------------------------------------


class TestWindowsPathToWslPosix:
    def test_drive_letter(self) -> None:
        result = _windows_path_to_wsl_posix(Path("C:\\Users\\test"))
        assert result is not None
        assert "mnt" in str(result)
        assert "c" in str(result).lower()

    def test_unc_path(self) -> None:
        result = _windows_path_to_wsl_posix(Path("\\\\wsl.localhost\\Ubuntu\\home"))
        assert result == Path("/home")

    def test_posix_path(self) -> None:
        result = _windows_path_to_wsl_posix(Path("/home/user"))
        # On Windows, Path("/home/user") backslash-normalizes so startswith("/") fails → None
        # On Linux, it passes through as-is
        assert result is None or str(result).replace("\\", "/").startswith("/home")

    def test_relative(self) -> None:
        result = _windows_path_to_wsl_posix(Path("relative"))
        assert result is None


# ---------------------------------------------------------------------------
# _materialize_path
# ---------------------------------------------------------------------------


class TestMaterializePath:
    def test_posix_resolves(self) -> None:
        result = _materialize_path("/tmp")
        assert result.is_absolute()

    def test_windows_kept(self) -> None:
        result = _materialize_path("C:\\Users")
        assert str(result).startswith("C:")

    def test_string_input(self) -> None:
        result = _materialize_path("/tmp")
        assert isinstance(result, Path)


# ---------------------------------------------------------------------------
# resolve_workspace
# ---------------------------------------------------------------------------


class TestResolveWorkspace:
    def test_basic_linux(self) -> None:
        ctx = resolve_workspace(control_root=Path("/repo"))
        assert ctx.control_root == Path("/repo")
        assert ctx.linux_backend_root == Path("/repo")
        assert ctx.private_root == Path("/repo/secrets")

    def test_windows_with_wsl_backend(self) -> None:
        ctx = resolve_workspace(control_root=Path("C:\\Projects"))
        assert ctx.control_root == Path("C:\\Projects")
        # Should derive WSL path
        assert ctx.linux_backend_root is not None

    def test_legacy_control_root(self) -> None:
        ctx = resolve_workspace(
            control_root=Path("/repo"),
            legacy_control_root=Path("/legacy"),
        )
        assert ctx.linux_backend_root == Path("/legacy")

    def test_explicit_linux_backend(self) -> None:
        ctx = resolve_workspace(
            control_root=Path("/repo"),
            linux_backend_root=Path("/wsl/repo"),
        )
        assert ctx.linux_backend_root == Path("/wsl/repo")

    def test_private_root_override(self) -> None:
        ctx = resolve_workspace(control_root=Path("/repo"), private_root=Path("/secrets"))
        assert ctx.private_root == Path("/secrets")

    def test_source_root_override(self) -> None:
        ctx = resolve_workspace(control_root=Path("/repo"), source_root=Path("/src"))
        assert ctx.source_root == Path("/src")
        assert ctx.local_command_root == Path("/src")

    def test_artifact_staging_root(self) -> None:
        ctx = resolve_workspace(control_root=Path("/repo"))
        assert ".agentplane" in str(ctx.artifact_staging_root)
        assert "staging" in str(ctx.artifact_staging_root)

    def test_control_root_required(self) -> None:
        with pytest.raises(ValueError, match="control_root"):
            resolve_workspace(control_root=None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# WorkspaceContext properties
# ---------------------------------------------------------------------------


class TestWorkspaceContext:
    def test_local_command_root(self) -> None:
        ctx = WorkspaceContext(
            control_root=Path("/repo"),
            legacy_control_root=None,
            private_root=Path("/secrets"),
            linux_backend_root=None,
            source_root=Path("/src"),
        )
        assert ctx.local_command_root == Path("/src")

    def test_artifact_staging_root_uses_backend(self) -> None:
        ctx = WorkspaceContext(
            control_root=Path("/repo"),
            legacy_control_root=None,
            private_root=Path("/secrets"),
            linux_backend_root=Path("/wsl"),
            source_root=Path("/src"),
        )
        assert ctx.artifact_staging_root == Path("/wsl/.agentplane/staging")

    def test_artifact_staging_root_fallback(self) -> None:
        ctx = WorkspaceContext(
            control_root=Path("/repo"),
            legacy_control_root=None,
            private_root=Path("/secrets"),
            linux_backend_root=None,
            source_root=Path("/src"),
        )
        assert ctx.artifact_staging_root == Path("/repo/.agentplane/staging")


# ---------------------------------------------------------------------------
# Golden test
# ---------------------------------------------------------------------------


@pytest.mark.golden
class TestWorkspaceGolden:
    def test_full_workspace_roundtrip(self) -> None:
        """resolve_workspace → properties → artifact_staging_root."""
        ctx = resolve_workspace(
            control_root=Path("/repo"),
            private_root=Path("/repo/secrets"),
            source_root=Path("/repo/src"),
        )
        assert ctx.control_root == Path("/repo")
        assert ctx.private_root == Path("/repo/secrets")
        assert ctx.source_root == Path("/repo/src")
        assert ctx.local_command_root == Path("/repo/src")
        assert ctx.artifact_staging_root == Path("/repo/.agentplane/staging")
