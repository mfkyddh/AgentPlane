"""Tests for runtime_deploy module - deploy/verify operations."""

from __future__ import annotations

import importlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


def _import_runtime_deploy():
    """Import runtime_deploy module lazily to avoid circular imports."""
    mod = importlib.import_module("agentplane.domain.app.runtime_deploy")
    return mod.deploy_app, mod.verify_app


def _create_mock_helpers():
    """Create a mock helpers dictionary for testing."""
    return {
        'next_operation_id': MagicMock(return_value="op-test-1"),
        '_local_backend_type': MagicMock(return_value="wsl"),
        'render_runtime': MagicMock(return_value={
            "compose_file": "/tmp/test-app/docker-compose.yml",
            "compose": "services:\n  test-app:\n    image: test:latest\n",
            "container_name": "test-app-prod",
        }),
        '_record_app_operation': MagicMock(return_value={"action": "deploy", "result": "planned"}),
        '_execute_step': MagicMock(return_value={"ok": True, "display": "docker compose up -d"}),
        '_target_ssh_target': MagicMock(),
        '_control_plane_transition_step': MagicMock(return_value=None),
        '_production_network_preflight': MagicMock(return_value={"ok": True}),
        '_healthcheck_url': MagicMock(return_value="http://localhost:8080/health"),
        '_runtime_container_name': MagicMock(return_value="test-app-prod"),
        '_origin_health_wait_command': MagicMock(return_value="docker inspect test-app-prod"),
        '_service_env_path': MagicMock(return_value=Path("/tmp/.env")),
        '_remote_compose_filename': MagicMock(return_value="docker-compose.yml"),
        '_remote_env_path': MagicMock(return_value="/opt/agentplane/.env"),
        '_remote_env_parent': MagicMock(return_value="/opt/agentplane"),
        '_payload_path': MagicMock(return_value="/tmp/.env"),
        'windows_path_to_wsl_posix': MagicMock(return_value="/mnt/tmp/.env"),
    }


def _make_contract(app_id: str = "test-app") -> dict:
    """Create a minimal contract dict for testing."""
    return {
        "app_id": app_id,
        "_meta": {"app_root": "/tmp/test-app"},
        "runtime": {
            "kind": "compose",
            "container_name": f"{app_id}-prod",
            "container_port": 8080,
            "healthcheck": {"path": "/health", "expected_status": 200},
        },
        "rollback": {"previous_control_plane": None},
    }


class TestDeployAppWslPath:
    """Tests for deploy_app with target='wsl'."""

    @pytest.fixture
    def _deploy_patches(self):
        """Context manager yielding mock objects for wsl deploy path."""
        mock_helpers = _create_mock_helpers()
        with patch("agentplane.domain.app.runtime_deploy._get_runtime_helpers", return_value=mock_helpers):
            yield mock_helpers

    def test_wsl_dry_run_returns_planned_result(self, _deploy_patches) -> None:
        """Test wsl dry_run path returns planned result."""
        deploy_app, _ = _import_runtime_deploy()
        contract = _make_contract()

        result = deploy_app(
            contract,
            repo_root=Path("/tmp"),
            target="wsl",
            image_ref="test:latest",
            dry_run=True,
            execute=False,
        )

        assert result["dry_run"] is True
        assert result["container_name"] == "test-app-prod"
        assert "commands" in result
        assert "operation" in result

    def test_wsl_local_only_returns_local_result(self, _deploy_patches) -> None:
        """Test wsl non-execute path returns local-only result."""
        deploy_app, _ = _import_runtime_deploy()
        contract = _make_contract()

        result = deploy_app(
            contract,
            repo_root=Path("/tmp"),
            target="wsl",
            image_ref="test:latest",
            dry_run=False,
            execute=False,
        )

        assert result["dry_run"] is False
        assert result["container_name"] == "test-app-prod"
        assert "commands" in result

    def test_wsl_execute_runs_compose_and_returns_result(self, _deploy_patches, tmp_path) -> None:
        """Test wsl execute path runs docker compose and returns result."""
        deploy_app, _ = _import_runtime_deploy()
        contract = _make_contract()
        mock_helpers = _deploy_patches

        # Create a temporary compose file
        compose_dir = tmp_path / "test-app"
        compose_dir.mkdir()
        compose_file = compose_dir / "docker-compose.yml"
        compose_file.write_text("services:\n  test-app:\n    image: test:latest\n")

        # Update render_runtime mock to return the actual compose file path
        mock_helpers['render_runtime'].return_value = {
            "compose_file": str(compose_file),
            "compose": "services:\n  test-app:\n    image: test:latest\n",
            "container_name": "test-app-prod",
            "env_files": [],
        }

        # Mock yaml.safe_load to return a valid compose structure
        with patch("agentplane.domain.app.runtime_deploy.yaml.safe_load") as mock_yaml:
            mock_yaml.return_value = {
                "services": {
                    "test-app": {"image": "test:latest"},
                }
            }
            result = deploy_app(
                contract,
                repo_root=tmp_path,
                target="wsl",
                image_ref="test:latest",
                dry_run=False,
                execute=True,
            )

            assert result["dry_run"] is False
            assert result["ok"] is True
            assert "compose_file" in result
            assert "results" in result

    def test_wsl_execute_raises_when_both_dry_run_and_execute(self, _deploy_patches) -> None:
        """Test that deploy raises ValueError when both dry_run and execute are True."""
        deploy_app, _ = _import_runtime_deploy()
        contract = _make_contract()

        with pytest.raises(ValueError, match="deploy 不允许同时传 --dry-run 和 --execute"):
            deploy_app(
                contract,
                repo_root=Path("/tmp"),
                target="wsl",
                image_ref="test:latest",
                dry_run=True,
                execute=True,
            )


class TestDeployAppRemotePath:
    """Tests for deploy_app with remote target."""

    @pytest.fixture
    def _deploy_patches(self):
        """Context manager yielding mock objects for remote deploy path."""
        mock_helpers = _create_mock_helpers()
        mock_helpers['_local_backend_type'].return_value = "ssh"
        
        # Configure SSH target mock
        mock_ssh_target = MagicMock()
        mock_ssh_target.display_ssh_command.return_value = "ssh user@host 'cmd'"
        mock_ssh_target.display_scp_command.return_value = "scp file user@host:/path"
        mock_ssh_target.local_ssh_args_for_shell.return_value = ["ssh", "user@host", "cmd"]
        mock_ssh_target.local_scp_args.return_value = ["scp", "file", "user@host:/path"]
        mock_helpers['_target_ssh_target'].return_value = mock_ssh_target
        
        with patch("agentplane.domain.app.runtime_deploy._get_runtime_helpers", return_value=mock_helpers):
            yield mock_helpers

    def test_remote_dry_run_returns_planned_result(self, _deploy_patches) -> None:
        """Test remote dry_run path returns planned result."""
        deploy_app, _ = _import_runtime_deploy()
        contract = _make_contract()

        result = deploy_app(
            contract,
            repo_root=Path("/tmp"),
            target="prod0-main",
            image_ref="test:latest",
            dry_run=True,
            execute=False,
        )

        assert result["dry_run"] is True
        assert result["container_name"] == "test-app-prod"
        assert "remote_compose" in result
        assert "remote_env" in result
        assert "commands" in result

    def test_remote_raises_when_not_execute(self, _deploy_patches) -> None:
        """Test remote path raises ValueError when execute is False."""
        deploy_app, _ = _import_runtime_deploy()
        contract = _make_contract()

        with pytest.raises(ValueError, match="deploy 当前默认只生成计划"):
            deploy_app(
                contract,
                repo_root=Path("/tmp"),
                target="prod0-main",
                image_ref="test:latest",
                dry_run=False,
                execute=False,
            )

    def test_remote_execute_runs_steps_and_returns_result(self, _deploy_patches) -> None:
        """Test remote execute path runs all steps and returns result."""
        deploy_app, _ = _import_runtime_deploy()
        contract = _make_contract()
        mock_helpers = _deploy_patches

        # Mock env_path.is_file() to return True
        mock_env_path = MagicMock()
        mock_env_path.is_file.return_value = True
        mock_env_path.parent = MagicMock()
        mock_env_path.name = ".env"
        mock_helpers['_service_env_path'].return_value = mock_env_path

        result = deploy_app(
            contract,
            repo_root=Path("/tmp"),
            target="prod0-main",
            image_ref="test:latest",
            dry_run=False,
            execute=True,
        )

        assert result["dry_run"] is False
        assert result["ok"] is True
        assert "remote_compose" in result
        assert "remote_env" in result
        assert "results" in result
        assert "network_preflight" in result

    def test_remote_execute_raises_when_env_missing(self, _deploy_patches) -> None:
        """Test remote execute path raises ValueError when env file is missing."""
        deploy_app, _ = _import_runtime_deploy()
        contract = _make_contract()
        mock_helpers = _deploy_patches

        # Mock env_path.is_file() to return False
        mock_env_path = MagicMock()
        mock_env_path.is_file.return_value = False
        mock_env_path.parent = MagicMock()
        mock_env_path.name = ".env"
        mock_helpers['_service_env_path'].return_value = mock_env_path

        with pytest.raises(ValueError, match="缺少运行时 env 文件"):
            deploy_app(
                contract,
                repo_root=Path("/tmp"),
                target="prod0-main",
                image_ref="test:latest",
                dry_run=False,
                execute=True,
            )


class TestVerifyAppWslPath:
    """Tests for verify_app with target='wsl'."""

    @pytest.fixture
    def _verify_patches(self):
        """Context manager yielding mock objects for wsl verify path."""
        mock_helpers = _create_mock_helpers()
        mock_helpers['_local_backend_type'].return_value = "wsl"
        mock_helpers['_healthcheck_url'].return_value = "http://localhost:8080/health"
        mock_helpers['_runtime_container_name'].return_value = "test-app-prod"
        mock_helpers['_execute_step'].return_value = {"ok": True, "display": "curl -fsS http://localhost:8080/health"}
        
        with patch("agentplane.domain.app.runtime_deploy._get_runtime_helpers", return_value=mock_helpers):
            yield mock_helpers

    def test_wsl_dry_run_returns_planned_result(self, _verify_patches) -> None:
        """Test wsl dry_run path returns planned result."""
        _, verify_app = _import_runtime_deploy()
        contract = _make_contract()

        result = verify_app(
            contract,
            repo_root=Path("/tmp"),
            target="wsl",
            dry_run=True,
            execute=False,
        )

        assert result["dry_run"] is True
        assert result["container_name"] == "test-app-prod"
        assert "commands" in result
        assert "operation" in result

    def test_wsl_local_only_returns_local_result(self, _verify_patches) -> None:
        """Test wsl non-execute path returns local-only result."""
        _, verify_app = _import_runtime_deploy()
        contract = _make_contract()

        result = verify_app(
            contract,
            repo_root=Path("/tmp"),
            target="wsl",
            dry_run=False,
            execute=False,
        )

        assert result["dry_run"] is False
        assert result["container_name"] == "test-app-prod"
        assert "commands" in result

    def test_wsl_execute_runs_curl_and_returns_result(self, _verify_patches) -> None:
        """Test wsl execute path runs curl and returns result."""
        _, verify_app = _import_runtime_deploy()
        contract = _make_contract()

        result = verify_app(
            contract,
            repo_root=Path("/tmp"),
            target="wsl",
            dry_run=False,
            execute=True,
        )

        assert result["dry_run"] is False
        assert result["ok"] is True
        assert "results" in result
        assert "backend_type" in result

    def test_wsl_execute_raises_when_both_dry_run_and_execute(self, _verify_patches) -> None:
        """Test that verify raises ValueError when both dry_run and execute are True."""
        _, verify_app = _import_runtime_deploy()
        contract = _make_contract()

        with pytest.raises(ValueError, match="verify 不允许同时传 --dry-run 和 --execute"):
            verify_app(
                contract,
                repo_root=Path("/tmp"),
                target="wsl",
                dry_run=True,
                execute=True,
            )


class TestVerifyAppRemotePath:
    """Tests for verify_app with remote target."""

    @pytest.fixture
    def _verify_patches(self):
        """Context manager yielding mock objects for remote verify path."""
        mock_helpers = _create_mock_helpers()
        mock_helpers['_local_backend_type'].return_value = "ssh"
        mock_helpers['_healthcheck_url'].return_value = "http://prod0-main:8080/health"
        mock_helpers['_runtime_container_name'].return_value = "test-app-prod"
        mock_helpers['_origin_health_wait_command'].return_value = "docker inspect test-app-prod && curl -fsS http://localhost:8080/health"
        mock_helpers['_execute_step'].return_value = {"ok": True, "display": "ssh user@host 'cmd'"}
        mock_helpers['_production_network_preflight'].return_value = {"ok": True}
        
        # Configure SSH target mock
        mock_ssh_target = MagicMock()
        mock_ssh_target.display_ssh_command.return_value = "ssh user@host 'cmd'"
        mock_helpers['_target_ssh_target'].return_value = mock_ssh_target
        
        with patch("agentplane.domain.app.runtime_deploy._get_runtime_helpers", return_value=mock_helpers):
            # Also mock has_public_ingress and public_sites for this fixture
            with patch("agentplane.domain.app.runtime_deploy.has_public_ingress", return_value=False):
                yield mock_helpers

    def test_remote_dry_run_returns_planned_result(self, _verify_patches) -> None:
        """Test remote dry_run path returns planned result."""
        _, verify_app = _import_runtime_deploy()
        contract = _make_contract()

        result = verify_app(
            contract,
            repo_root=Path("/tmp"),
            target="prod0-main",
            dry_run=True,
            execute=False,
        )

        assert result["dry_run"] is True
        assert result["container_name"] == "test-app-prod"
        assert "commands" in result
        assert "operation" in result

    def test_remote_execute_runs_checks_and_returns_result(self, _verify_patches) -> None:
        """Test remote execute path runs all checks and returns result."""
        _, verify_app = _import_runtime_deploy()
        contract = _make_contract()

        result = verify_app(
            contract,
            repo_root=Path("/tmp"),
            target="prod0-main",
            dry_run=False,
            execute=True,
        )

        assert result["dry_run"] is False
        assert result["ok"] is True
        assert "checks" in result
        assert "origin" in result["checks"]
        assert "network_preflight" in result

    def test_remote_execute_with_public_ingress_adds_public_checks(self, _verify_patches) -> None:
        """Test remote execute path adds public checks when has_public_ingress is True."""
        _, verify_app = _import_runtime_deploy()
        contract = _make_contract()
        contract["ingress"] = {
            "public_sites": [{"public_url": "https://example.com"}],
        }

        with patch("agentplane.domain.app.runtime_deploy.has_public_ingress") as mock_ingress:
            mock_ingress.return_value = True
            with patch("agentplane.domain.app.runtime_deploy.public_sites") as mock_sites:
                mock_sites.return_value = [{"public_url": "https://example.com"}]

                result = verify_app(
                    contract,
                    repo_root=Path("/tmp"),
                    target="prod0-main",
                    dry_run=False,
                    execute=True,
                )

                assert result["dry_run"] is False
                assert result["ok"] is True
                assert "public" in result["checks"]
