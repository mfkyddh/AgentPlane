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
