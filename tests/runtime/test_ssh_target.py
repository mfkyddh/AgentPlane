"""Tests for agentplane.ssh — SshTarget dataclass pure methods."""

from __future__ import annotations

from pathlib import Path

import pytest
from agentplane.ssh import SshTarget

pytestmark = pytest.mark.unit

CONFIG = Path("/home/user/.ssh/config")


# ---------------------------------------------------------------------------
# connection_target
# ---------------------------------------------------------------------------


class TestConnectionTarget:
    def test_with_user(self) -> None:
        t = SshTarget(alias="srv", config_path=CONFIG, user="root")
        assert t.connection_target == "root@srv"

    def test_without_user(self) -> None:
        t = SshTarget(alias="srv", config_path=CONFIG)
        assert t.connection_target == "srv"


# ---------------------------------------------------------------------------
# requires_sudo
# ---------------------------------------------------------------------------


class TestRequiresSudo:
    def test_linux_production_non_root(self) -> None:
        t = SshTarget(alias="srv", config_path=CONFIG, user="deploy", os_family="linux", environment="production")
        assert t.requires_sudo is True

    def test_root(self) -> None:
        t = SshTarget(alias="srv", config_path=CONFIG, user="root", os_family="linux", environment="production")
        assert t.requires_sudo is False

    def test_non_production(self) -> None:
        t = SshTarget(alias="srv", config_path=CONFIG, user="deploy", os_family="linux", environment="staging")
        assert t.requires_sudo is False

    def test_non_linux(self) -> None:
        t = SshTarget(alias="srv", config_path=CONFIG, user="deploy", os_family="windows", environment="production")
        assert t.requires_sudo is False


# ---------------------------------------------------------------------------
# _tty_flag
# ---------------------------------------------------------------------------


class TestTtyFlag:
    def test_allocate_tty(self) -> None:
        t = SshTarget(alias="srv", config_path=CONFIG, allocate_tty=True)
        assert t._tty_flag() == "-t"

    def test_no_tty(self) -> None:
        t = SshTarget(alias="srv", config_path=CONFIG, allocate_tty=False)
        assert t._tty_flag() == "-T"


# ---------------------------------------------------------------------------
# wrap_argv
# ---------------------------------------------------------------------------


class TestWrapArgv:
    def test_simple(self) -> None:
        t = SshTarget(alias="srv", config_path=CONFIG, user="root")
        assert t.wrap_argv(["echo", "hi"]) == "echo hi"

    def test_with_sudo(self) -> None:
        t = SshTarget(alias="srv", config_path=CONFIG, user="deploy", os_family="linux", environment="production")
        result = t.wrap_argv(["echo", "hi"])
        assert result.startswith("sudo ")
        assert "echo" in result


# ---------------------------------------------------------------------------
# wrap_shell
# ---------------------------------------------------------------------------


class TestWrapShell:
    def test_simple(self) -> None:
        t = SshTarget(alias="srv", config_path=CONFIG, user="root")
        result = t.wrap_shell("echo hi")
        assert "bash -lc" in result
        assert "echo hi" in result

    def test_with_sudo(self) -> None:
        t = SshTarget(alias="srv", config_path=CONFIG, user="deploy", os_family="linux", environment="production")
        result = t.wrap_shell("echo hi")
        assert result.startswith("sudo ")
        assert "bash -lc" in result


# ---------------------------------------------------------------------------
# wrap_bash_stdin
# ---------------------------------------------------------------------------


class TestWrapBashStdin:
    def test_no_args(self) -> None:
        t = SshTarget(alias="srv", config_path=CONFIG, user="root")
        result = t.wrap_bash_stdin()
        assert "bash" in result
        assert "-s" in result

    def test_with_args(self) -> None:
        t = SshTarget(alias="srv", config_path=CONFIG, user="root")
        result = t.wrap_bash_stdin(["arg1"])
        assert "arg1" in result


# ---------------------------------------------------------------------------
# scp_destination
# ---------------------------------------------------------------------------


class TestScpDestination:
    def test_basic(self) -> None:
        t = SshTarget(alias="srv", config_path=CONFIG, user="root")
        assert t.scp_destination("/tmp/file") == "root@srv:/tmp/file"


# ---------------------------------------------------------------------------
# ssh_args methods
# ---------------------------------------------------------------------------


class TestSshArgs:
    def test_ssh_args_for_argv(self) -> None:
        t = SshTarget(alias="srv", config_path=CONFIG, user="root")
        args = t.ssh_args_for_argv(["echo", "hi"])
        assert args[0] == "ssh"
        assert "root@srv" in args
        assert str(CONFIG) in args

    def test_ssh_args_for_shell(self) -> None:
        t = SshTarget(alias="srv", config_path=CONFIG, user="root")
        args = t.ssh_args_for_shell("echo hi")
        assert args[0] == "ssh"
        assert "root@srv" in args

    def test_ssh_args_for_bash_stdin(self) -> None:
        t = SshTarget(alias="srv", config_path=CONFIG, user="root")
        args = t.ssh_args_for_bash_stdin()
        assert args[0] == "ssh"
        assert "root@srv" in args

    def test_scp_args(self) -> None:
        t = SshTarget(alias="srv", config_path=CONFIG, user="root")
        args = t.scp_args("/local/file", "/remote/file")
        assert args[0] == "scp"
        assert str(CONFIG) in args
        assert "/local/file" in args


# ---------------------------------------------------------------------------
# display methods
# ---------------------------------------------------------------------------


class TestDisplayMethods:
    def test_display_ssh_command(self) -> None:
        t = SshTarget(alias="srv", config_path=CONFIG, user="root")
        result = t.display_ssh_command("echo hi")
        assert "ssh" in result
        assert "srv" in result

    def test_display_ssh_argv(self) -> None:
        t = SshTarget(alias="srv", config_path=CONFIG, user="root")
        result = t.display_ssh_argv(["echo", "hi"])
        assert "ssh" in result
        assert "srv" in result

    def test_display_ssh_bash_stdin(self) -> None:
        t = SshTarget(alias="srv", config_path=CONFIG, user="root")
        result = t.display_ssh_bash_stdin()
        assert "ssh" in result

    def test_display_scp_command(self) -> None:
        t = SshTarget(alias="srv", config_path=CONFIG, user="root")
        result = t.display_scp_command("/local", "/remote")
        assert "scp" in result
        assert "srv" in result


# ---------------------------------------------------------------------------
# Golden test
# ---------------------------------------------------------------------------


@pytest.mark.golden
class TestSshTargetGolden:
    def test_full_target_roundtrip(self) -> None:
        """SshTarget → connection_target → wrap_shell → ssh_args_for_shell."""
        t = SshTarget(
            alias="prod0",
            config_path=CONFIG,
            user="deploy",
            os_family="linux",
            environment="production",
        )
        assert t.connection_target == "deploy@prod0"
        assert t.requires_sudo is True
        assert t._tty_flag() == "-T"

        shell = t.wrap_shell("docker ps")
        assert shell.startswith("sudo ")
        assert "bash -lc" in shell

        args = t.ssh_args_for_shell("docker ps")
        assert args[0] == "ssh"
        assert "deploy@prod0" in args
