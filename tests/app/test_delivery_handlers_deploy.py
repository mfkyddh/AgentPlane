"""Tests for agentplane.domain.app.delivery_handlers_deploy.deploy_for_app."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


def _make_contract(app_id: str = "test-app") -> dict:
    """Create a minimal contract dict for testing."""
    return {
        "app_id": app_id,
        "_meta": {"app_root": "/tmp/test-app"},
        "runtime": {
            "kind": "compose",
            "container_name": f"{app_id}-prod",
            "container_port": 8080,
            "host_binding": "0.0.0.0:8080",
            "healthcheck": {"path": "/health", "expected_status": 200},
        },
        "rollback": {"previous_control_plane": {"kind": "none"}},
    }


def _create_mock_app_cli() -> MagicMock:
    """Create a mock app_cli object."""
    mock = MagicMock()
    mock.deploy_app.return_value = {
        "ok": True,
        "container_name": "test-app-prod",
        "compose_file": "/tmp/test-app/docker-compose.yml",
        "commands": ["docker compose up -d"],
        "results": [{"ok": True, "display": "docker compose up -d"}],
        "operation": {"op_id": "op-test-1", "result": "executed"},
        "dry_run": False,
        "backend_type": "wsl",
    }
    mock.next_operation_id.return_value = "op-test-1"
    mock._payload_path.return_value = "/tmp/.env"
    mock._target_ssh_target.return_value = MagicMock(connection_target="user@host")
    mock._production_network_preflight.return_value = None
    mock._split_host_binding.return_value = ("0.0.0.0", "8080")
    return mock


class TestDeployForAppWslPath:
    """Tests for deploy_for_app with target='wsl'."""

    @pytest.fixture
    def _deploy_patches(self):
        """Fixture providing mock objects for wsl deploy path."""
        mock_app_cli = _create_mock_app_cli()
        mock_contract = _make_contract()

        with (
            patch("agentplane.domain.app.delivery_handlers_deploy._load_validated_contract") as mock_load,
            patch("agentplane.domain.app.delivery_handlers_deploy._check_delivery_preconditions") as mock_precond,
            patch("agentplane.domain.app.delivery_handlers_deploy._run_delivery_post_actions") as mock_post,
        ):
            mock_load.return_value = (mock_app_cli, mock_contract, None)
            mock_precond.return_value = {"ok": True, "preconditions": {}}
            mock_post.return_value = {"ok": True}
            yield mock_app_cli, mock_contract

    def test_wsl_dry_run_returns_planned_result(self, _deploy_patches) -> None:
        """Test wsl dry_run path returns planned result with execution steps."""
        from agentplane.domain.app.delivery_handlers_deploy import deploy_for_app

        mock_app_cli, _ = _deploy_patches
        mock_app_cli.deploy_app.return_value = {
            "ok": True,
            "container_name": "test-app-prod",
            "dry_run": True,
        }

        with (
            patch("agentplane.domain.app.delivery_handlers_deploy._plan_wsl_deploy_steps") as mock_plan,
            patch("agentplane.domain.app.delivery_handlers_deploy._render_execution_steps") as mock_render,
        ):
            mock_step = MagicMock()
            mock_step.spec.backend_type = "wsl"
            mock_plan.return_value = ([mock_step], {})
            mock_render.return_value = [{"backend": {"display_command": "docker compose up -d"}}]

            result = deploy_for_app(
                Path("/tmp"),
                target="wsl",
                app="test-app",
                image_ref="test:latest",
                dry_run=True,
                execute=False,
            )

        assert result["command"] == "app"
        assert result["action"] == "deploy"
        assert result["target"] == "wsl"
        assert result["payload"]["dry_run"] is True
        assert "execution_steps" in result["payload"]

    def test_wsl_execute_returns_result(self, _deploy_patches) -> None:
        """Test wsl execute path returns result with post actions."""
        from agentplane.domain.app.delivery_handlers_deploy import deploy_for_app

        mock_app_cli, _ = _deploy_patches

        result = deploy_for_app(
            Path("/tmp"),
            target="wsl",
            app="test-app",
            image_ref="test:latest",
            dry_run=False,
            execute=True,
        )

        assert result["command"] == "app"
        assert result["action"] == "deploy"
        assert result["payload"]["ok"] is True
        assert "post_actions" in result["payload"]
        assert result["payload"]["rollback_state"]["status"] == "not-applicable"

    def test_wsl_local_only_returns_result(self, _deploy_patches) -> None:
        """Test wsl local-only path (not dry_run, not execute) returns result."""
        from agentplane.domain.app.delivery_handlers_deploy import deploy_for_app

        mock_app_cli, _ = _deploy_patches
        mock_app_cli.deploy_app.return_value = {
            "ok": True,
            "container_name": "test-app-prod",
            "dry_run": False,
        }

        result = deploy_for_app(
            Path("/tmp"),
            target="wsl",
            app="test-app",
            image_ref="test:latest",
            dry_run=False,
            execute=False,
        )

        assert result["command"] == "app"
        assert result["payload"]["ok"] is True

    def test_wsl_execute_fails_when_post_actions_fail(self, _deploy_patches) -> None:
        """Test wsl execute path fails when post actions fail."""
        from agentplane.domain.app.delivery_handlers_deploy import deploy_for_app

        mock_app_cli, _ = _deploy_patches

        with patch("agentplane.domain.app.delivery_handlers_deploy._run_delivery_post_actions") as mock_post:
            mock_post.return_value = {"ok": False, "error": "post action failed"}

            result = deploy_for_app(
                Path("/tmp"),
                target="wsl",
                app="test-app",
                image_ref="test:latest",
                dry_run=False,
                execute=True,
            )

        assert result["payload"]["ok"] is False

    def test_wsl_precondition_failed_returns_error(self, _deploy_patches) -> None:
        """Test wsl execute path returns error when preconditions fail."""
        from agentplane.domain.app.delivery_handlers_deploy import deploy_for_app

        with patch("agentplane.domain.app.delivery_handlers_deploy._check_delivery_preconditions") as mock_precond:
            mock_precond.return_value = {
                "ok": False,
                "preconditions": {"object_verify": False},
            }

            result = deploy_for_app(
                Path("/tmp"),
                target="wsl",
                app="test-app",
                image_ref="test:latest",
                dry_run=False,
                execute=True,
            )

        assert result["payload"]["ok"] is False
        assert result["payload"]["error"]["code"] == "app.delivery.precondition_failed"


class TestDeployForAppRemotePath:
    """Tests for deploy_for_app with target='remote'."""

    @pytest.fixture
    def _deploy_patches(self):
        """Fixture providing mock objects for remote deploy path."""
        mock_app_cli = _create_mock_app_cli()
        mock_contract = _make_contract()

        with (
            patch("agentplane.domain.app.delivery_handlers_deploy._load_validated_contract") as mock_load,
            patch("agentplane.domain.app.delivery_handlers_deploy._check_delivery_preconditions") as mock_precond,
            patch("agentplane.domain.app.delivery_handlers_deploy._candidate_runtime_material") as mock_material,
            patch("agentplane.domain.app.delivery_handlers_deploy._candidate_precheck_steps") as mock_precheck,
            patch("agentplane.domain.app.delivery_handlers_deploy._render_execution_steps") as mock_render,
            patch("agentplane.domain.app.delivery_handlers_deploy._plan_production_rollback") as mock_rollback,
            patch("agentplane.domain.app.delivery_handlers_deploy._delayed_cleanup_state") as mock_cleanup,
            patch("agentplane.domain.app.delivery_handlers_deploy._run_delivery_post_actions") as mock_post,
        ):
            mock_load.return_value = (mock_app_cli, mock_contract, None)
            mock_precond.return_value = {"ok": True, "preconditions": {}}
            mock_material.return_value = {
                "container_name": "test-app-candidate",
                "project_name": "test-app-candidate",
                "host_binding": "0.0.0.0:9080",
                "health_url": "http://localhost:9080/health",
                "local_compose": Path("/tmp/docker-compose.yml"),
                "local_env": Path("/tmp/.env"),
                "remote_compose": "/opt/test-app/docker-compose.yml",
                "remote_env": "/opt/test-app/.env",
                "image_ref": "test:latest",
            }
            mock_precheck.return_value = {
                "prepare": [MagicMock()],
                "verify": [MagicMock()],
                "cleanup": [MagicMock()],
            }
            mock_render.return_value = [{"backend": {"display_command": "echo test"}}]
            mock_rollback.return_value = {"commands": ["echo rollback"], "steps": []}
            mock_cleanup.return_value = {"status": "not-applicable"}
            mock_post.return_value = {"ok": True}
            yield mock_app_cli, mock_contract

    def test_remote_dry_run_returns_planned_result(self, _deploy_patches) -> None:
        """Test remote dry_run path returns planned result with rollback state."""
        from agentplane.domain.app.delivery_handlers_deploy import deploy_for_app

        mock_app_cli, _ = _deploy_patches
        mock_app_cli.deploy_app.return_value = {
            "ok": True,
            "container_name": "test-app-prod",
            "dry_run": True,
        }

        with (
            patch("agentplane.domain.app.delivery_handlers_deploy._plan_remote_deploy_steps") as mock_remote,
            patch("agentplane.domain.app.delivery_handlers_deploy._plan_production_verify") as mock_verify,
            patch("agentplane.domain.app.delivery_handlers_deploy._rollback_state_payload") as mock_state,
        ):
            mock_remote.return_value = ([MagicMock()], {})
            mock_verify.return_value = {"commands": ["curl http://localhost/health"], "steps": []}
            mock_state.return_value = {"status": "planned"}

            result = deploy_for_app(
                Path("/tmp"),
                target="remote",
                app="test-app",
                image_ref="test:latest",
                dry_run=True,
                execute=False,
            )

        assert result["command"] == "app"
        assert result["action"] == "deploy"
        assert result["target"] == "remote"
        assert result["payload"]["dry_run"] is True
        assert result["payload"]["deployment_model"] == "formal-rollback-state"

    def test_remote_execute_runs_full_orchestration(self, _deploy_patches, tmp_path) -> None:
        """Test remote execute path runs full orchestration with cutover."""
        from agentplane.domain.app.delivery_handlers_deploy import deploy_for_app

        mock_app_cli, _ = _deploy_patches

        # Create a temporary env file
        env_file = tmp_path / ".env"
        env_file.write_text("APP_ENV=production\n")

        # Update mock to return actual path
        _deploy_patches[0]._payload_path.return_value = str(env_file)

        with (
            patch("agentplane.domain.app.delivery_handlers_deploy._execute_steps") as mock_exec,
            patch("agentplane.domain.app.delivery_handlers_deploy._execute_origin_verify") as mock_verify,
            patch("agentplane.domain.app.delivery_handlers_deploy._plan_production_verify") as mock_plan_verify,
            patch("agentplane.domain.app.delivery_handlers_deploy._candidate_runtime_material") as mock_material,
        ):
            mock_exec.return_value = [{"ok": True, "display": "echo test"}]
            mock_verify.return_value = {"ok": True}
            mock_plan_verify.return_value = {"commands": [], "steps": []}
            mock_material.return_value = {
                "container_name": "test-app-candidate",
                "project_name": "test-app-candidate",
                "host_binding": "0.0.0.0:9080",
                "health_url": "http://localhost:9080/health",
                "local_compose": Path("/tmp/docker-compose.yml"),
                "local_env": str(env_file),
                "remote_compose": "/opt/test-app/docker-compose.yml",
                "remote_env": "/opt/test-app/.env",
                "image_ref": "test:latest",
            }

            mock_stream = MagicMock()
            mock_stream.return_value = MagicMock(ok=True)

            result = deploy_for_app(
                tmp_path,
                target="remote",
                app="test-app",
                image_ref="test:latest",
                dry_run=False,
                execute=True,
                _streamer=mock_stream,
            )

        assert result["command"] == "app"
        assert result["action"] == "deploy"
        assert result["payload"]["ok"] is True

    def test_remote_local_only_returns_result(self, _deploy_patches) -> None:
        """Test remote local-only path returns result without execution."""
        from agentplane.domain.app.delivery_handlers_deploy import deploy_for_app

        mock_app_cli, _ = _deploy_patches
        mock_app_cli.deploy_app.return_value = {
            "ok": True,
            "container_name": "test-app-prod",
            "dry_run": False,
        }

        result = deploy_for_app(
            Path("/tmp"),
            target="remote",
            app="test-app",
            image_ref="test:latest",
            dry_run=False,
            execute=False,
        )

        assert result["command"] == "app"
        assert result["payload"]["ok"] is True

    def test_remote_execute_raises_on_stream_failure(self, _deploy_patches) -> None:
        """Test remote execute path raises when image stream fails."""
        from agentplane.domain.app.delivery_handlers_deploy import deploy_for_app

        mock_app_cli, _ = _deploy_patches

        mock_stream = MagicMock()
        mock_stream.return_value = MagicMock(ok=False, stderr="stream failed")

        with pytest.raises(ValueError, match="流式镜像传输失败"):
            deploy_for_app(
                Path("/tmp"),
                target="remote",
                app="test-app",
                image_ref="test:latest",
                dry_run=False,
                execute=True,
                _streamer=mock_stream,
            )

    def test_remote_precondition_failed_returns_error(self, _deploy_patches) -> None:
        """Test remote execute path returns error when preconditions fail."""
        from agentplane.domain.app.delivery_handlers_deploy import deploy_for_app

        with patch("agentplane.domain.app.delivery_handlers_deploy._check_delivery_preconditions") as mock_precond:
            mock_precond.return_value = {
                "ok": False,
                "preconditions": {"object_verify": False},
            }

            result = deploy_for_app(
                Path("/tmp"),
                target="remote",
                app="test-app",
                image_ref="test:latest",
                dry_run=False,
                execute=True,
            )

        assert result["payload"]["ok"] is False
        assert result["payload"]["error"]["code"] == "app.delivery.precondition_failed"
