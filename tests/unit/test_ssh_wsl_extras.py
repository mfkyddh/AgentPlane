"""Unit tests for ssh.py and wsl_bridge.py uncovered paths.

Focuses on pure functions and SshTarget methods not covered by existing e2e/integration tests.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# ssh.py — SshTarget methods, _local_backend_argv, _build_parser
# ---------------------------------------------------------------------------


class TestSshTargetMethods:
    def test_connection_target_without_user(self) -> None:
        from agentplane.ssh import SshTarget

        target = SshTarget(alias="myhost", config_path=Path("/tmp/cfg"))
        assert target.connection_target == "myhost"

    def test_connection_target_with_user(self) -> None:
        from agentplane.ssh import SshTarget

        target = SshTarget(alias="myhost", config_path=Path("/tmp/cfg"), user="admin")
        assert target.connection_target == "admin@myhost"

    def test_requires_sudo_root_user(self) -> None:
        from agentplane.ssh import SshTarget

        target = SshTarget(alias="h", config_path=Path("/c"), user="root", os_family="linux", environment="production")
        assert target.requires_sudo is False

    def test_requires_sudo_non_root_production_linux(self) -> None:
        from agentplane.ssh import SshTarget

        target = SshTarget(alias="h", config_path=Path("/c"), user="ubuntu", os_family="linux", environment="production")
        assert target.requires_sudo is True

    def test_requires_sudo_non_production(self) -> None:
        from agentplane.ssh import SshTarget

        target = SshTarget(alias="h", config_path=Path("/c"), user="ubuntu", os_family="linux", environment="staging")
        assert target.requires_sudo is False

    def test_requires_sudo_non_linux(self) -> None:
        from agentplane.ssh import SshTarget

        target = SshTarget(alias="h", config_path=Path("/c"), user="admin", os_family="darwin", environment="production")
        assert target.requires_sudo is False

    def test_tty_flag_default(self) -> None:
        from agentplane.ssh import SshTarget

        target = SshTarget(alias="h", config_path=Path("/c"))
        assert "-T" in target.ssh_args_for_shell("ls")[1]

    def test_tty_flag_allocated(self) -> None:
        from agentplane.ssh import SshTarget

        target = SshTarget(alias="h", config_path=Path("/c"), allocate_tty=True)
        assert "-t" in target.ssh_args_for_shell("ls")[1]

    def test_wrap_argv_with_sudo(self) -> None:
        from agentplane.ssh import SshTarget

        target = SshTarget(alias="h", config_path=Path("/c"), user="ubuntu", os_family="linux", environment="production")
        result = target.wrap_argv(["docker", "ps"])
        assert result.startswith("sudo ")

    def test_wrap_argv_without_sudo(self) -> None:
        from agentplane.ssh import SshTarget

        target = SshTarget(alias="h", config_path=Path("/c"), user="root", os_family="linux", environment="production")
        result = target.wrap_argv(["docker", "ps"])
        assert not result.startswith("sudo ")

    def test_wrap_shell_with_sudo(self) -> None:
        from agentplane.ssh import SshTarget

        target = SshTarget(alias="h", config_path=Path("/c"), user="ubuntu", os_family="linux", environment="production")
        result = target.wrap_shell("docker ps")
        assert result.startswith("sudo bash -lc")

    def test_ssh_args_for_argv(self) -> None:
        from agentplane.ssh import SshTarget

        target = SshTarget(alias="myhost", config_path=Path("/tmp/cfg"), user="root")
        args = target.ssh_args_for_argv(["docker", "ps"])
        assert args[0] == "ssh"
        assert "root@myhost" in args
        assert args[-1] == "docker ps"

    def test_local_ssh_args_for_argv_non_windows(self) -> None:
        from agentplane.ssh import SshTarget

        target = SshTarget(alias="myhost", config_path=Path("/tmp/cfg"), user="root")
        with patch("agentplane.ssh.os.name", "posix"):
            args = target.local_ssh_args_for_argv(["echo", "hi"])
        assert args[0] == "ssh"

    def test_display_ssh_argv(self) -> None:
        from agentplane.ssh import SshTarget

        target = SshTarget(alias="myhost", config_path=Path("/tmp/cfg"), user="root")
        display = target.display_ssh_argv(["docker", "ps"])
        assert "ssh" in display
        assert "myhost" in display

    def test_scp_destination(self) -> None:
        from agentplane.ssh import SshTarget

        target = SshTarget(alias="myhost", config_path=Path("/tmp/cfg"), user="root")
        assert target.scp_destination("/tmp/file") == "root@myhost:/tmp/file"

    def test_scp_args(self) -> None:
        from agentplane.ssh import SshTarget

        target = SshTarget(alias="myhost", config_path=Path("/tmp/cfg"), user="root")
        args = target.scp_args("/local/file", "/remote/file")
        assert args[0] == "scp"
        assert "/local/file" in args
        assert "root@myhost:/remote/file" in args

    def test_local_scp_args_non_windows(self) -> None:
        from agentplane.ssh import SshTarget

        target = SshTarget(alias="myhost", config_path=Path("/tmp/cfg"), user="root")
        with patch("agentplane.ssh.os.name", "posix"):
            args = target.local_scp_args("/local", "/remote")
        assert args[0] == "scp"

    def test_display_scp_command(self) -> None:
        from agentplane.ssh import SshTarget

        target = SshTarget(alias="myhost", config_path=Path("/tmp/cfg"), user="root")
        display = target.display_scp_command("/local/file", "/remote/file")
        assert "scp" in display
        assert "myhost" in display

    def test_display_ssh_bash_stdin(self) -> None:
        from agentplane.ssh import SshTarget

        target = SshTarget(alias="myhost", config_path=Path("/tmp/cfg"), user="root")
        display = target.display_ssh_bash_stdin(["--flag", "val"])
        assert "ssh" in display
        assert "bash -s" in display


class TestLocalBackendArgv:
    def test_local_backend_argv_wsl_disabled(self) -> None:
        from agentplane.ssh import _local_backend_argv

        with patch("agentplane.ssh.os.name", "nt"), patch.dict("agentplane.ssh.os.environ", {"AGENTPLANE_DISABLE_WSL_SSH": "1"}):
            result = _local_backend_argv(["ssh", "host"])
        assert result == ["ssh", "host"]

    def test_local_backend_argv_non_windows(self) -> None:
        from agentplane.ssh import _local_backend_argv

        with patch("agentplane.ssh.os.name", "posix"):
            result = _local_backend_argv(["ssh", "host"])
        assert result == ["ssh", "host"]


class TestBuildParser:
    def test_parser_connection_target(self) -> None:
        from agentplane.ssh import _build_parser

        parser = _build_parser()
        args = parser.parse_args(["--repo-root", "/tmp", "connection-target", "myhost"])
        assert args.action == "connection-target"
        assert args.alias == "myhost"

    def test_parser_config_path(self) -> None:
        from agentplane.ssh import _build_parser

        parser = _build_parser()
        args = parser.parse_args(["--repo-root", "/tmp", "config-path"])
        assert args.action == "config-path"

    def test_parser_bash_stdin_command(self) -> None:
        from agentplane.ssh import _build_parser

        parser = _build_parser()
        args = parser.parse_args(["--repo-root", "/tmp", "bash-stdin-command", "myhost", "--", "arg1"])
        assert args.action == "bash-stdin-command"
        assert args.alias == "myhost"


class TestSshMain:
    def test_main_config_path(self, tmp_path: Path) -> None:
        from agentplane.ssh import main

        with patch("sys.argv", ["ssh.py", "--repo-root", str(tmp_path), "config-path"]):
            result = main()
        assert result == 0

    def test_main_connection_target(self, tmp_path: Path) -> None:
        from agentplane.ssh import main

        with patch("sys.argv", ["ssh.py", "--repo-root", str(tmp_path), "connection-target", "myhost"]):
            result = main()
        assert result == 0

    def test_main_bash_stdin_command(self, tmp_path: Path) -> None:
        from agentplane.ssh import main

        with patch("sys.argv", ["ssh.py", "--repo-root", str(tmp_path), "bash-stdin-command", "myhost", "--", "arg1"]):
            result = main()
        assert result == 0

    def test_main_bash_stdin_command_without_separator(self, tmp_path: Path) -> None:
        from agentplane.ssh import main

        with patch("sys.argv", ["ssh.py", "--repo-root", str(tmp_path), "bash-stdin-command", "myhost", "arg1"]):
            result = main()
        assert result == 0


class TestResolveSshTargetEdgeCases:
    def test_resolve_ssh_target_corrupt_json(self, tmp_path: Path) -> None:
        from agentplane.ssh import resolve_ssh_target

        inv_dir = tmp_path / "inventory" / "servers" / "wsl"
        inv_dir.mkdir(parents=True)
        (inv_dir / "inventory.json").write_text("not-json", encoding="utf-8")
        target = resolve_ssh_target(tmp_path, "myhost")
        assert target.alias == "myhost"
        assert target.user is None

    def test_resolve_ssh_target_non_dict_payload(self, tmp_path: Path) -> None:
        from agentplane.ssh import resolve_ssh_target

        inv_dir = tmp_path / "inventory" / "servers" / "wsl"
        inv_dir.mkdir(parents=True)
        (inv_dir / "inventory.json").write_text('"just a string"', encoding="utf-8")
        target = resolve_ssh_target(tmp_path, "myhost")
        assert target.alias == "myhost"

    def test_resolve_ssh_target_no_ssh_section(self, tmp_path: Path) -> None:
        from agentplane.ssh import resolve_ssh_target

        inv_dir = tmp_path / "inventory" / "servers" / "wsl"
        inv_dir.mkdir(parents=True)
        (inv_dir / "inventory.json").write_text(json.dumps({"hostname": "wsl"}), encoding="utf-8")
        target = resolve_ssh_target(tmp_path, "myhost")
        assert target.alias == "myhost"

    def test_resolve_ssh_target_invalid_user_type(self, tmp_path: Path) -> None:
        from agentplane.ssh import resolve_ssh_target

        inv_dir = tmp_path / "inventory" / "servers" / "wsl"
        inv_dir.mkdir(parents=True)
        (inv_dir / "inventory.json").write_text(
            json.dumps({"ssh": {"aliases": ["myhost"], "user": 123}}), encoding="utf-8"
        )
        target = resolve_ssh_target(tmp_path, "myhost")
        assert target.user is None


# ---------------------------------------------------------------------------
# wsl_bridge.py — pure path functions
# ---------------------------------------------------------------------------


class TestWslBridgePathFunctions:
    def test_is_windows_path_drive_letter(self) -> None:
        from agentplane.runtime.wsl_bridge import is_windows_path

        assert is_windows_path("C:/repos") is True
        assert is_windows_path("D:\\projects") is True

    def test_is_windows_path_posix(self) -> None:
        from agentplane.runtime.wsl_bridge import is_windows_path

        assert is_windows_path("/srv/data") is False

    def test_is_windows_path_none(self) -> None:
        from agentplane.runtime.wsl_bridge import is_windows_path

        assert is_windows_path(None) is False

    def test_is_windows_path_short(self) -> None:
        from agentplane.runtime.wsl_bridge import is_windows_path

        assert is_windows_path("C") is False
        assert is_windows_path("") is False

    def test_is_wsl_unc_path_wsl_localhost(self) -> None:
        from agentplane.runtime.wsl_bridge import is_wsl_unc_path

        assert is_wsl_unc_path(r"\\wsl.localhost\Ubuntu\home") is True
        assert is_wsl_unc_path(r"\\wsl$\Ubuntu\home") is True

    def test_is_wsl_unc_path_normal_unc(self) -> None:
        from agentplane.runtime.wsl_bridge import is_wsl_unc_path

        assert is_wsl_unc_path(r"\\server\share") is False

    def test_is_wsl_unc_path_none(self) -> None:
        from agentplane.runtime.wsl_bridge import is_wsl_unc_path

        assert is_wsl_unc_path(None) is False

    def test_normalize_wsl_posix_path_none(self) -> None:
        from agentplane.runtime.wsl_bridge import normalize_wsl_posix_path

        assert normalize_wsl_posix_path(None) is None

    def test_normalize_wsl_posix_path_unc(self) -> None:
        from agentplane.runtime.wsl_bridge import normalize_wsl_posix_path

        result = normalize_wsl_posix_path(r"\\wsl.localhost\Ubuntu\home")
        assert result.startswith("\\\\")

    def test_normalize_wsl_posix_path_single_backslash(self) -> None:
        from agentplane.runtime.wsl_bridge import normalize_wsl_posix_path

        result = normalize_wsl_posix_path("\\srv\\data")
        assert result == "/srv/data"

    def test_normalize_wsl_posix_path_posix(self) -> None:
        from agentplane.runtime.wsl_bridge import normalize_wsl_posix_path

        assert normalize_wsl_posix_path("/srv/data") == "/srv/data"

    def test_wsl_unc_to_posix_none(self) -> None:
        from agentplane.runtime.wsl_bridge import wsl_unc_to_posix

        assert wsl_unc_to_posix(None) is None

    def test_wsl_posix_to_unc_none(self) -> None:
        from agentplane.runtime.wsl_bridge import wsl_posix_to_unc

        assert wsl_posix_to_unc(None) is None

    def test_wsl_posix_to_unc_relative(self) -> None:
        from agentplane.runtime.wsl_bridge import wsl_posix_to_unc

        assert wsl_posix_to_unc("relative/path") is None

    def test_wsl_posix_to_unc_absolute(self) -> None:
        from agentplane.runtime.wsl_bridge import wsl_posix_to_unc

        result = wsl_posix_to_unc("/home/user")
        assert "wsl.localhost" in result
        assert "Ubuntu" in result

    def test_wsl_posix_to_unc_root(self) -> None:
        from agentplane.runtime.wsl_bridge import wsl_posix_to_unc

        result = wsl_posix_to_unc("/")
        assert "wsl.localhost" in result

    def test_render_host_path_none(self) -> None:
        from agentplane.runtime.wsl_bridge import render_host_path

        assert render_host_path(None) is None

    def test_render_host_path_windows(self) -> None:
        from agentplane.runtime.wsl_bridge import render_host_path

        result = render_host_path("C:/repos/agentplane")
        assert result == "C:\\repos\\agentplane"

    def test_render_host_path_posix(self) -> None:
        from agentplane.runtime.wsl_bridge import render_host_path

        assert render_host_path("/srv/data") == "/srv/data"

    def test_render_host_path_single_backslash(self) -> None:
        from agentplane.runtime.wsl_bridge import render_host_path

        result = render_host_path("\\srv\\data")
        assert result == "/srv/data"

    def test_windows_path_to_wsl_posix_none(self) -> None:
        from agentplane.runtime.wsl_bridge import windows_path_to_wsl_posix

        assert windows_path_to_wsl_posix(None) is None

    def test_windows_path_to_wsl_posix_drive_path(self) -> None:
        from agentplane.runtime.wsl_bridge import windows_path_to_wsl_posix

        result = windows_path_to_wsl_posix("C:/repos/agentplane")
        assert result == "/mnt/c/repos/agentplane"

    def test_local_backend_status_payload(self) -> None:
        from agentplane.runtime.platform import LinuxBackend
        from agentplane.runtime.wsl_bridge import LocalLinuxBackendStatus

        backend = LinuxBackend(
            backend_type="wsl-linux",
            executable=("wsl.exe", "-e"),
            shell_executable=("wsl.exe", "-e", "bash", "-lc"),
        )
        status = LocalLinuxBackendStatus(backend=backend, available=True)
        payload = status.to_payload()
        assert payload["backend_type"] == "wsl-linux"
        assert payload["available"] is True
        assert "wsl.exe" in payload["executable"]
