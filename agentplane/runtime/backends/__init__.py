from __future__ import annotations

from agentplane.runtime.execution import BackendRunner

from .linux_native import LinuxNativeBackend
from .macos_lima import MacosLimaBackend
from .ssh_linux import SshLinuxBackend
from .windows_wsl import WindowsWslBackend


def build_backend_runner() -> BackendRunner:
    return BackendRunner(
        {
            "linux-native": LinuxNativeBackend(),
            "windows-wsl": WindowsWslBackend(),
            "macos-lima": MacosLimaBackend(),
            "ssh-linux": SshLinuxBackend(),
        }
    )


__all__ = [
    "BackendRunner",
    "LinuxNativeBackend",
    "MacosLimaBackend",
    "SshLinuxBackend",
    "WindowsWslBackend",
    "build_backend_runner",
]
