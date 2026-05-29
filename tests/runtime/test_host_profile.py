"""Tests for agentplane.runtime.host_profile and platform — pure functions."""

from __future__ import annotations

import pytest
from agentplane.runtime.host_profile import (
    _normalize_profile_os_name,
    host_profile_from_platform,
)
from agentplane.runtime.platform import (
    HostPlatform,
    LinuxBackend,
    _normalize_os_name,
    select_linux_backend,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# _normalize_profile_os_name
# ---------------------------------------------------------------------------


class TestNormalizeProfileOsName:
    def test_darwin(self) -> None:
        assert _normalize_profile_os_name("darwin") == "macos"

    def test_windows(self) -> None:
        assert _normalize_profile_os_name("windows") == "windows"

    def test_linux(self) -> None:
        assert _normalize_profile_os_name("linux") == "linux"

    def test_macos(self) -> None:
        assert _normalize_profile_os_name("macos") == "macos"

    def test_unsupported_raises(self) -> None:
        with pytest.raises(ValueError, match="Unsupported"):
            _normalize_profile_os_name("freebsd")


# ---------------------------------------------------------------------------
# host_profile_from_platform
# ---------------------------------------------------------------------------


class TestHostProfileFromPlatform:
    def test_windows_with_wsl(self) -> None:
        facts = HostPlatform(os_name="windows", has_wsl=True, is_wsl=False)
        profile = host_profile_from_platform(facts)
        assert profile.os_name == "windows"
        assert profile.linux_backend == "windows-wsl"
        assert profile.supports_docker is True
        assert profile.has_wsl is True

    def test_windows_without_wsl(self) -> None:
        facts = HostPlatform(os_name="windows", has_wsl=False, is_wsl=False)
        profile = host_profile_from_platform(facts)
        assert profile.supports_docker is False

    def test_linux(self) -> None:
        facts = HostPlatform(os_name="linux", has_wsl=False, is_wsl=False)
        profile = host_profile_from_platform(facts)
        assert profile.os_name == "linux"
        assert profile.linux_backend == "linux-native"
        assert profile.supports_docker is True

    def test_macos(self) -> None:
        facts = HostPlatform(os_name="darwin", has_wsl=False, is_wsl=False)
        profile = host_profile_from_platform(facts)
        assert profile.os_name == "macos"
        assert profile.linux_backend == "macos-lima"

    def test_is_wsl(self) -> None:
        facts = HostPlatform(os_name="linux", has_wsl=False, is_wsl=True)
        profile = host_profile_from_platform(facts)
        assert profile.is_wsl is True


# ---------------------------------------------------------------------------
# HostProfile.to_payload
# ---------------------------------------------------------------------------


class TestHostProfileToPayload:
    def test_payload_keys(self) -> None:
        facts = HostPlatform(os_name="linux", has_wsl=False, is_wsl=False)
        profile = host_profile_from_platform(facts)
        payload = profile.to_payload()
        assert "os_name" in payload
        assert "linux_backend" in payload
        assert "supports_docker" in payload
        assert "has_wsl" in payload
        assert "is_wsl" in payload


# ---------------------------------------------------------------------------
# _normalize_os_name (platform)
# ---------------------------------------------------------------------------


class TestNormalizeOsName:
    def test_windows(self) -> None:
        assert _normalize_os_name("Windows") == "windows"

    def test_windows_nt(self) -> None:
        assert _normalize_os_name("Windows_NT") == "windows"

    def test_linux(self) -> None:
        assert _normalize_os_name("Linux") == "linux"

    def test_darwin(self) -> None:
        assert _normalize_os_name("Darwin") == "macos"

    def test_unknown_passthrough(self) -> None:
        assert _normalize_os_name("FreeBSD") == "freebsd"


# ---------------------------------------------------------------------------
# select_linux_backend
# ---------------------------------------------------------------------------


class TestSelectLinuxBackend:
    def test_windows_with_wsl(self) -> None:
        facts = HostPlatform(os_name="windows", has_wsl=True, is_wsl=False)
        backend = select_linux_backend(facts)
        assert backend.backend_type == "wsl-linux"
        assert backend.executable == ("wsl.exe", "-e")
        assert "bash" in backend.shell_executable

    def test_windows_without_wsl_raises(self) -> None:
        facts = HostPlatform(os_name="windows", has_wsl=False, is_wsl=False)
        with pytest.raises(ValueError, match="WSL"):
            select_linux_backend(facts)

    def test_windows_is_wsl_raises(self) -> None:
        facts = HostPlatform(os_name="windows", has_wsl=True, is_wsl=True)
        with pytest.raises(ValueError, match="WSL"):
            select_linux_backend(facts)

    def test_linux(self) -> None:
        facts = HostPlatform(os_name="linux", has_wsl=False, is_wsl=False)
        backend = select_linux_backend(facts)
        assert backend.backend_type == "native-posix"
        assert backend.executable == ()

    def test_macos(self) -> None:
        facts = HostPlatform(os_name="macos", has_wsl=False, is_wsl=False)
        backend = select_linux_backend(facts)
        assert backend.backend_type == "native-posix"


# ---------------------------------------------------------------------------
# LinuxBackend
# ---------------------------------------------------------------------------


class TestLinuxBackend:
    def test_program_argv(self) -> None:
        backend = LinuxBackend(
            backend_type="wsl-linux",
            executable=("wsl.exe", "-e"),
            shell_executable=("wsl.exe", "-e", "bash", "-lc"),
        )
        result = backend.program_argv("echo", "hi")
        assert result == ["wsl.exe", "-e", "echo", "hi"]

    def test_shell_argv(self) -> None:
        backend = LinuxBackend(
            backend_type="native-posix",
            executable=(),
            shell_executable=("bash", "-lc"),
        )
        result = backend.shell_argv("echo hi")
        assert result == ["bash", "-lc", "echo hi"]


# ---------------------------------------------------------------------------
# Golden test
# ---------------------------------------------------------------------------


@pytest.mark.golden
class TestHostProfileGolden:
    def test_full_linux_profile_roundtrip(self) -> None:
        """Linux host: normalize → profile → backend → payload."""
        facts = HostPlatform(os_name="linux", has_wsl=False, is_wsl=False)
        profile = host_profile_from_platform(facts)
        assert profile.os_name == "linux"
        assert profile.supports_docker is True

        backend = select_linux_backend(facts)
        assert backend.backend_type == "native-posix"

        payload = profile.to_payload()
        assert payload["os_name"] == "linux"
        assert payload["supports_docker"] is True

    def test_full_windows_wsl_profile_roundtrip(self) -> None:
        """Windows+WSL host: normalize → profile → backend → payload."""
        facts = HostPlatform(os_name="windows", has_wsl=True, is_wsl=False)
        profile = host_profile_from_platform(facts)
        assert profile.os_name == "windows"
        assert profile.linux_backend == "windows-wsl"
        assert profile.supports_docker is True

        backend = select_linux_backend(facts)
        assert backend.backend_type == "wsl-linux"

        payload = profile.to_payload()
        assert payload["has_wsl"] is True
