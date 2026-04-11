from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping

from agentplane.runtime.platform import HostPlatform, detect_host_platform

HostOsName = Literal["windows", "linux", "macos"]
HostLinuxBackend = Literal["windows-wsl", "linux-native", "macos-lima", "ssh-linux"]


@dataclass(frozen=True)
class HostProfile:
    os_name: HostOsName
    linux_backend: HostLinuxBackend
    supports_docker: bool
    has_wsl: bool = False
    is_wsl: bool = False

    def to_payload(self) -> dict[str, bool | str]:
        return {
            "os_name": self.os_name,
            "linux_backend": self.linux_backend,
            "supports_docker": self.supports_docker,
            "has_wsl": self.has_wsl,
            "is_wsl": self.is_wsl,
        }


def _normalize_profile_os_name(raw: str) -> HostOsName:
    if raw == "darwin":
        return "macos"
    if raw in {"windows", "linux", "macos"}:
        return raw
    raise ValueError(f"Unsupported host os for profile: {raw}")


def host_profile_from_platform(facts: HostPlatform) -> HostProfile:
    os_name = _normalize_profile_os_name(facts.os_name)
    if os_name == "windows":
        linux_backend: HostLinuxBackend = "windows-wsl"
    elif os_name == "macos":
        linux_backend = "macos-lima"
    else:
        linux_backend = "linux-native"

    supports_docker = os_name == "linux" or (os_name == "windows" and facts.has_wsl)
    return HostProfile(
        os_name=os_name,
        linux_backend=linux_backend,
        supports_docker=supports_docker,
        has_wsl=facts.has_wsl,
        is_wsl=facts.is_wsl,
    )


def detect_host_profile(
    *,
    os_name: str | None = None,
    environ: Mapping[str, str] | None = None,
    has_wsl: bool | None = None,
) -> HostProfile:
    return host_profile_from_platform(
        detect_host_platform(
            os_name=os_name,
            environ=environ,
            has_wsl=has_wsl,
        )
    )
