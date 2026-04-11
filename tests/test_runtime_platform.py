from agentplane.runtime.host_profile import host_profile_from_platform
from agentplane.runtime.platform import HostPlatform, select_linux_backend


def test_selects_wsl_linux_backend_for_windows_host() -> None:
    facts = HostPlatform(os_name="windows", has_wsl=True, is_wsl=False)

    backend = select_linux_backend(facts)

    assert backend.backend_type == "wsl-linux"
    assert backend.executable == ("wsl.exe", "-e", "bash", "-lc")


def test_selects_native_backend_inside_wsl_linux() -> None:
    facts = HostPlatform(os_name="linux", has_wsl=True, is_wsl=True)

    backend = select_linux_backend(facts)

    assert backend.backend_type == "native-posix"
    assert backend.executable == ("bash", "-lc")


def test_host_profile_maps_windows_host_to_windows_wsl_backend() -> None:
    profile = host_profile_from_platform(HostPlatform(os_name="windows", has_wsl=True, is_wsl=False))

    assert profile.os_name == "windows"
    assert profile.linux_backend == "windows-wsl"
    assert profile.supports_docker is True


def test_host_profile_maps_wsl_linux_to_linux_native_backend() -> None:
    profile = host_profile_from_platform(HostPlatform(os_name="linux", has_wsl=True, is_wsl=True))

    assert profile.os_name == "linux"
    assert profile.linux_backend == "linux-native"
    assert profile.is_wsl is True
