from __future__ import annotations

# Import backends so their @register_backend decorators run.
from agentplane.runtime.execution import BackendRunner

from .linux_native import LinuxNativeBackend
from .macos_lima import MacosLimaBackend
from .registry import build_backend_runner, register_backend  # noqa: F401
from .ssh_linux import SshLinuxBackend
from .windows_wsl import WindowsWslBackend

__all__ = [
    "BackendRunner",
    "LinuxNativeBackend",
    "MacosLimaBackend",
    "SshLinuxBackend",
    "WindowsWslBackend",
    "build_backend_runner",
    "register_backend",
]
