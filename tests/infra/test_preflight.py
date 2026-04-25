from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from agentplane.cli.preflight import (
    PreflightCheck,
    PreflightReport,
    _check_ssh_config_exists,
    _check_ssh_key_permissions,
    _check_ssh_reachable,
    _check_wsl_available,
    execute_remote_preflight,
)


class TestCheckWslAvailable:
    @patch("agentplane.cli.preflight.subprocess.run")
    def test_wsl_ok(self, mock_run: MagicMock) -> None:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "ok\n"
        mock_run.return_value.stderr = ""
        check = _check_wsl_available()
        assert check.status == "ok"
        assert "WSL is running" in check.message

    @patch("agentplane.cli.preflight.subprocess.run")
    def test_wsl_failed(self, mock_run: MagicMock) -> None:
        mock_run.return_value.returncode = 1
        mock_run.return_value.stdout = ""
        mock_run.return_value.stderr = "Error"
        check = _check_wsl_available()
        assert check.status == "failed"

    @patch("agentplane.cli.preflight.subprocess.run", side_effect=FileNotFoundError)
    def test_wsl_not_found(self, _mock: MagicMock) -> None:
        check = _check_wsl_available()
        assert check.status == "failed"
        assert "wsl.exe not found" in check.message


class TestCheckSshConfigExists:
    def test_config_exists(self, tmp_path: pytest.TempPathFactory) -> None:
        config = tmp_path / "ssh" / "config"
        config.parent.mkdir(parents=True)
        config.write_text("Host test\n")
        ssh_target = MagicMock()
        ssh_target.config_path = config
        check = _check_ssh_config_exists(ssh_target)
        assert check.status == "ok"

    def test_config_missing(self, tmp_path: pytest.TempPathFactory) -> None:
        ssh_target = MagicMock()
        ssh_target.config_path = tmp_path / "missing"
        check = _check_ssh_config_exists(ssh_target)
        assert check.status == "failed"


class TestCheckSshKeyPermissions:
    def test_key_with_good_permissions(self, tmp_path: pytest.TempPathFactory) -> None:
        config = tmp_path / "ssh" / "config"
        config.parent.mkdir(parents=True)
        key = tmp_path / "ssh" / "id_rsa"
        key.write_text("secret")
        key.chmod(0o600)
        config.write_text(f"Host test\n  IdentityFile {key}\n")
        ssh_target = MagicMock()
        ssh_target.config_path = config
        ssh_target.alias = "test"
        check = _check_ssh_key_permissions(ssh_target)
        # On Windows chmod does not set Unix permission bits; accept ok or warning
        assert check.status in ("ok", "warning")

    def test_key_with_open_permissions(self, tmp_path: pytest.TempPathFactory) -> None:
        config = tmp_path / "ssh" / "config"
        config.parent.mkdir(parents=True)
        key = tmp_path / "ssh" / "id_rsa"
        key.write_text("secret")
        key.chmod(0o644)
        config.write_text(f"Host test\n  IdentityFile {key}\n")
        ssh_target = MagicMock()
        ssh_target.config_path = config
        ssh_target.alias = "test"
        check = _check_ssh_key_permissions(ssh_target)
        assert check.status == "warning"
        assert "too open" in check.message

    def test_missing_key(self, tmp_path: pytest.TempPathFactory) -> None:
        config = tmp_path / "ssh" / "config"
        config.parent.mkdir(parents=True)
        config.write_text("Host test\n  IdentityFile /nonexistent/key\n")
        ssh_target = MagicMock()
        ssh_target.config_path = config
        ssh_target.alias = "test"
        check = _check_ssh_key_permissions(ssh_target)
        assert check.status == "failed"


class TestCheckSshReachable:
    @patch("agentplane.cli.preflight.subprocess.run")
    def test_ssh_ok(self, mock_run: MagicMock) -> None:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "ok\n"
        mock_run.return_value.stderr = ""
        ssh_target = MagicMock()
        ssh_target.local_ssh_args_for_argv.return_value = ["ssh", "test"]
        ssh_target.connection_target = "test"
        check = _check_ssh_reachable(ssh_target)
        assert check.status == "ok"

    @patch("agentplane.cli.preflight.subprocess.run")
    def test_ssh_auth_failure(self, mock_run: MagicMock) -> None:
        mock_run.return_value.returncode = 255
        mock_run.return_value.stdout = ""
        mock_run.return_value.stderr = "Permission denied (publickey)"
        ssh_target = MagicMock()
        ssh_target.local_ssh_args_for_argv.return_value = ["ssh", "test"]
        ssh_target.connection_target = "test"
        check = _check_ssh_reachable(ssh_target)
        assert check.status == "failed"
        assert "authentication failed" in check.message.lower()

    @patch("agentplane.cli.preflight.subprocess.run")
    def test_ssh_network_failure(self, mock_run: MagicMock) -> None:
        mock_run.return_value.returncode = 255
        mock_run.return_value.stdout = ""
        mock_run.return_value.stderr = "ssh: connect to host bad port 22: Connection refused"
        ssh_target = MagicMock()
        ssh_target.local_ssh_args_for_argv.return_value = ["ssh", "bad"]
        ssh_target.connection_target = "bad"
        check = _check_ssh_reachable(ssh_target)
        assert check.status == "failed"
        assert "network failure" in check.message.lower()


class TestExecuteRemotePreflight:
    @patch("agentplane.cli.preflight.detect_host_profile")
    @patch("agentplane.cli.preflight.TargetResolver")
    def test_local_wsl_preflight(self, mock_resolver_cls: MagicMock, mock_detect: MagicMock) -> None:
        mock_detect.return_value = MagicMock()
        mock_resolver = MagicMock()
        mock_resolver.resolve.return_value = MagicMock(is_local=True, execution_backend="windows-wsl")
        mock_resolver_cls.return_value = mock_resolver

        with patch("agentplane.cli.preflight._check_wsl_available", return_value=PreflightCheck("wsl", "ok", "ok")):
            report = execute_remote_preflight("/fake/repo", "wsl")
        assert report.overall == "ok"
        assert report.target == "wsl"

    @patch("agentplane.cli.preflight.detect_host_profile")
    @patch("agentplane.cli.preflight.TargetResolver")
    @patch("agentplane.cli.preflight.resolve_ssh_target")
    def test_remote_preflight(self, mock_resolve_ssh: MagicMock, mock_resolver_cls: MagicMock, mock_detect: MagicMock) -> None:
        mock_detect.return_value = MagicMock()
        mock_resolver = MagicMock()
        mock_resolver.resolve.return_value = MagicMock(is_local=False, ssh_alias="prod0-main")
        mock_resolver_cls.return_value = mock_resolver
        ssh_target = MagicMock()
        ssh_target.config_path.exists.return_value = True
        mock_resolve_ssh.return_value = ssh_target

        with patch("agentplane.cli.preflight._check_ssh_config_exists", return_value=PreflightCheck("config", "ok", "ok")):
            with patch("agentplane.cli.preflight._check_ssh_key_permissions", return_value=PreflightCheck("key", "ok", "ok")):
                with patch("agentplane.cli.preflight._check_ssh_reachable", return_value=PreflightCheck("ssh", "ok", "ok")):
                    report = execute_remote_preflight("/fake/repo", "prod0-main")
        assert report.overall == "ok"

    def test_preflight_report_payload(self) -> None:
        report = PreflightReport(
            target="wsl",
            overall="warning",
            checks=[
                PreflightCheck("a", "ok", "fine"),
                PreflightCheck("b", "warning", "careful"),
            ],
        )
        payload = report.to_payload()
        assert payload["overall"] == "warning"
        assert len(payload["checks"]) == 2
