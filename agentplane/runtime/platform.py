from __future__ import annotations

import os
import platform
import shutil
from dataclasses import dataclass
from typing import Literal, Mapping


@dataclass(frozen=True)
class HostPlatform:
    os_name: str
    has_wsl: bool
    is_wsl: bool


@dataclass(frozen=True)
class LinuxBackend:
    backend_type: Literal["native-posix", "wsl-linux", "ssh-linux"]
    executable: tuple[str, ...]

    def shell_argv(self, command: str) -> list[str]:
        return [*self.executable, command]


def _normalize_os_name(raw: str) -> str:
    value = raw.lower()
    if value.startswith("win"):
        return "windows"
    if value.startswith("linux"):
        return "linux"
    if value.startswith("darwin"):
        return "darwin"
    return value


def detect_host_platform(
    *,
    os_name: str | None = None,
    environ: Mapping[str, str] | None = None,
    has_wsl: bool | None = None,
) -> HostPlatform:
    env = environ or os.environ
    normalized_os = _normalize_os_name(os_name or platform.system())
    release = platform.release().lower()
    is_wsl = "wsl_interop" in env or "wsl_distro_name" in env or "microsoft" in release
    resolved_has_wsl = has_wsl if has_wsl is not None else shutil.which("wsl.exe") is not None
    return HostPlatform(os_name=normalized_os, has_wsl=resolved_has_wsl, is_wsl=is_wsl)


def select_linux_backend(facts: HostPlatform) -> LinuxBackend:
    if facts.os_name == "windows":
        if facts.has_wsl and not facts.is_wsl:
            return LinuxBackend(backend_type="wsl-linux", executable=("wsl.exe", "-e", "bash", "-lc"))
        raise ValueError("Windows host requires WSL to provide a local Linux backend")
    return LinuxBackend(backend_type="native-posix", executable=("bash", "-lc"))


def default_linux_backend() -> LinuxBackend:
    return select_linux_backend(detect_host_platform())
