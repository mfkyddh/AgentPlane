"""Tests for agentplane.runtime.wsl_bridge — pure path helper functions."""

from __future__ import annotations

from pathlib import Path

import pytest
from agentplane.runtime.wsl_bridge import (
    is_windows_path,
    is_wsl_unc_path,
    normalize_wsl_posix_path,
    render_host_path,
    windows_path_to_wsl_posix,
    wsl_posix_to_unc,
    wsl_unc_to_posix,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# is_windows_path
# ---------------------------------------------------------------------------


class TestIsWindowsPath:
    def test_drive_letter(self) -> None:
        assert is_windows_path("C:\\Users\\test") is True

    def test_lowercase_drive(self) -> None:
        assert is_windows_path("d:\\Projects") is True

    def test_posix_path(self) -> None:
        assert is_windows_path("/home/user") is False

    def test_relative_path(self) -> None:
        assert is_windows_path("relative/path") is False

    def test_none(self) -> None:
        assert is_windows_path(None) is False

    def test_path_object(self) -> None:
        assert is_windows_path(Path("C:\\Users")) is True


# ---------------------------------------------------------------------------
# is_wsl_unc_path
# ---------------------------------------------------------------------------


class TestIsWslUncPath:
    def test_wsl_localhost(self) -> None:
        assert is_wsl_unc_path("\\\\wsl.localhost\\Ubuntu\\home") is True

    def test_wsl_dollar(self) -> None:
        assert is_wsl_unc_path("\\\\wsl$\\Ubuntu\\home") is True

    def test_wsl_localhost_forward_slash(self) -> None:
        assert is_wsl_unc_path("//wsl.localhost/Ubuntu/home") is True

    def test_regular_unc(self) -> None:
        assert is_wsl_unc_path("\\\\server\\share") is False

    def test_posix_path(self) -> None:
        assert is_wsl_unc_path("/home/user") is False

    def test_none(self) -> None:
        assert is_wsl_unc_path(None) is False


# ---------------------------------------------------------------------------
# normalize_wsl_posix_path
# ---------------------------------------------------------------------------


class TestNormalizeWslPosixPath:
    def test_backslash_to_slash(self) -> None:
        result = normalize_wsl_posix_path("\\home\\user")
        assert result == "/home/user"

    def test_posix_passthrough(self) -> None:
        assert normalize_wsl_posix_path("/home/user") == "/home/user"

    def test_unc_passthrough(self) -> None:
        result = normalize_wsl_posix_path("\\\\wsl.localhost\\Ubuntu\\home")
        assert result.startswith("\\\\")

    def test_none(self) -> None:
        assert normalize_wsl_posix_path(None) is None


# ---------------------------------------------------------------------------
# wsl_unc_to_posix
# ---------------------------------------------------------------------------


class TestWslUncToPosix:
    def test_basic(self) -> None:
        result = wsl_unc_to_posix("\\\\wsl.localhost\\Ubuntu\\home\\user")
        assert result == Path("/home/user")

    def test_wsl_dollar(self) -> None:
        result = wsl_unc_to_posix("\\\\wsl$\\Ubuntu\\home\\user")
        assert result == Path("/home/user")

    def test_none(self) -> None:
        assert wsl_unc_to_posix(None) is None

    def test_non_wsl_unc(self) -> None:
        result = wsl_unc_to_posix("\\\\server\\share")
        assert result is None


# ---------------------------------------------------------------------------
# wsl_posix_to_unc
# ---------------------------------------------------------------------------


class TestWslPosixToUnc:
    def test_basic(self) -> None:
        result = wsl_posix_to_unc("/home/user")
        assert result == "\\\\wsl.localhost\\Ubuntu\\home\\user"

    def test_custom_distro(self) -> None:
        result = wsl_posix_to_unc("/home/user", distro="Debian")
        assert result == "\\\\wsl.localhost\\Debian\\home\\user"

    def test_root(self) -> None:
        result = wsl_posix_to_unc("/")
        assert result == "\\\\wsl.localhost\\Ubuntu"

    def test_none(self) -> None:
        assert wsl_posix_to_unc(None) is None

    def test_relative_path(self) -> None:
        result = wsl_posix_to_unc("relative/path")
        assert result is None


# ---------------------------------------------------------------------------
# windows_path_to_wsl_posix
# ---------------------------------------------------------------------------


class TestWindowsPathToWslPosix:
    def test_drive_letter(self) -> None:
        result = windows_path_to_wsl_posix("C:\\Users\\test")
        # Should convert to WSL mount path
        assert result is not None
        assert "/" in result

    def test_none(self) -> None:
        assert windows_path_to_wsl_posix(None) is None

    def test_posix_path(self) -> None:
        result = windows_path_to_wsl_posix("/home/user")
        # POSIX paths are not Windows paths, so _windows_path_to_wsl_posix returns None
        assert result is None


# ---------------------------------------------------------------------------
# render_host_path
# ---------------------------------------------------------------------------


class TestRenderHostPath:
    def test_windows_path(self) -> None:
        result = render_host_path("C:\\Users\\test")
        assert "C:" in result

    def test_posix_path(self) -> None:
        assert render_host_path("/home/user") == "/home/user"

    def test_none(self) -> None:
        assert render_host_path(None) is None

    def test_backslash_relative(self) -> None:
        result = render_host_path("\\some\\path")
        assert "\\" not in result or "/" in result


# ---------------------------------------------------------------------------
# Golden test
# ---------------------------------------------------------------------------


@pytest.mark.golden
class TestWslBridgeGolden:
    def test_wsl_unc_roundtrip(self) -> None:
        """UNC → POSIX → UNC roundtrip preserves path."""
        original = "\\\\wsl.localhost\\Ubuntu\\home\\user\\project"
        posix_path = wsl_unc_to_posix(original)
        assert posix_path is not None
        back_to_unc = wsl_posix_to_unc(str(posix_path))
        assert back_to_unc == original

    def test_windows_path_detection_roundtrip(self) -> None:
        """Windows path detected → rendered correctly."""
        win_path = "D:\\Projects\\AgentPlane"
        assert is_windows_path(win_path) is True
        rendered = render_host_path(win_path)
        assert "D:" in rendered
