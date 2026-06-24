"""Unit tests for delivery_handlers_planning module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from agentplane.domain.app.delivery_handlers_planning import (
    _execute_origin_verify,
    _plan_delivery_rollback_steps,
    _plan_delivery_verify_steps,
    _plan_production_rollback,
    _plan_production_verify,
    _plan_remote_deploy_steps,
    _plan_wsl_deploy_steps,
)

pytestmark = pytest.mark.unit


class TestPlanDeliveryRollbackSteps:
    """Tests for _plan_delivery_rollback_steps function."""

    def test_returns_empty_for_wsl_target(self) -> None:
        """Test that returns empty steps for wsl target."""
        app_cli = MagicMock()
        contract = {
            "app_id": "test-app",
            "rollback": {
                "previous_control_plane": {"kind": "compose", "image_ref": "test:v1"},
            },
        }

        steps, rollback_entry = _plan_delivery_rollback_steps(app_cli, contract, repo_root=Path("/tmp"), target="wsl")

        assert steps == []
        assert rollback_entry == {"kind": "compose", "image_ref": "test:v1"}

    def test_returns_empty_for_none_rollback(self) -> None:
        """Test that returns empty steps for none rollback kind."""
        app_cli = MagicMock()
        contract = {
            "app_id": "test-app",
            "rollback": {
                "previous_control_plane": {"kind": "none"},
            },
        }

        steps, rollback_entry = _plan_delivery_rollback_steps(
            app_cli, contract, repo_root=Path("/tmp"), target="prod0-main"
        )

        assert steps == []
        assert rollback_entry == {"kind": "none"}

    def test_returns_steps_for_remote_target(self) -> None:
        """Test that returns steps for remote target with compose rollback."""
        app_cli = MagicMock()
        app_cli._target_ssh_target.return_value = MagicMock()
        app_cli._remote_compose_filename.return_value = "docker-compose.prod0.yml"
        app_cli._control_plane_transition_step.return_value = (["echo", "stop"], "stop")

        contract = {
            "app_id": "test-app",
            "rollback": {
                "previous_control_plane": {"kind": "compose", "image_ref": "test:v1"},
            },
        }

        with patch("agentplane.domain.app.delivery_handlers_shared.detect_host_profile") as mock_detect:
            mock_detect.return_value = MagicMock(linux_backend="linux-native")

            with patch("agentplane.domain.app.delivery_handlers_shared.plan_local_backend_step") as mock_plan:
                mock_plan.return_value = MagicMock()

                steps, rollback_entry = _plan_delivery_rollback_steps(
                    app_cli, contract, repo_root=Path("/tmp"), target="prod0-main"
                )

        assert len(steps) >= 1
        assert rollback_entry == {"kind": "compose", "image_ref": "test:v1"}


class TestPlanProductionRollback:
    """Tests for _plan_production_rollback function."""

    def test_returns_not_applicable_for_wsl(self) -> None:
        """Test that returns not-applicable status for wsl target."""
        app_cli = MagicMock()
        app_cli.render_rollback_entry.return_value = "rollback info"
        contract = {
            "app_id": "test-app",
            "rollback": {
                "previous_control_plane": {"kind": "compose", "image_ref": "test:v1"},
            },
        }

        result = _plan_production_rollback(app_cli, contract, repo_root=Path("/tmp"), target="wsl")

        assert result["status"] == "not-applicable"
        assert result["commands"] == []
        assert "rollback_entry" in result

    def test_returns_not_applicable_for_none_rollback(self) -> None:
        """Test that returns not-applicable status for none rollback."""
        app_cli = MagicMock()
        app_cli.render_rollback_entry.return_value = "none"
        contract = {
            "app_id": "test-app",
            "rollback": {
                "previous_control_plane": {"kind": "none"},
            },
        }

        result = _plan_production_rollback(app_cli, contract, repo_root=Path("/tmp"), target="prod0-main")

        assert result["status"] == "not-applicable"
        assert result["commands"] == []


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
    mock.render_runtime.return_value = {
        "compose_file": "/tmp/docker-compose.yml",
        "compose": "services:\n  test-app:\n    image: test:latest\n",
        "container_name": "test-app-prod",
        "env_files": [],
    }
    mock._target_ssh_target.return_value = MagicMock(connection_target="user@host")
    mock._service_env_path.return_value = "/tmp/.env"
    mock._remote_compose_filename.return_value = "docker-compose.yml"
    mock._remote_env_path.return_value = "/opt/test-app/.env"
    mock._remote_env_parent.return_value = "/opt/test-app"
    mock._payload_path.return_value = "/tmp/.env"
    mock._control_plane_transition_step.return_value = None
    mock._runtime_container_name.return_value = "test-app-prod"
    mock._healthcheck_url.return_value = "http://localhost:8080/health"
    mock._origin_health_wait_command.return_value = "curl http://localhost:8080/health"
    mock._production_network_preflight.return_value = None
    mock.has_public_ingress.return_value = False
    mock.public_sites.return_value = []
    return mock


class TestPlanWslDeploySteps:
    """Tests for _plan_wsl_deploy_steps function."""

    def test_returns_steps_and_metadata(self) -> None:
        """Test returns steps and metadata for wsl deploy."""
        app_cli = _create_mock_app_cli()
        contract = _make_contract()

        with patch("agentplane.domain.app.delivery_handlers_planning.detect_host_profile") as mock_detect:
            mock_detect.return_value = MagicMock(linux_backend="wsl")

            steps, metadata = _plan_wsl_deploy_steps(
                app_cli, contract, repo_root=Path("/tmp"), target="wsl", image_ref="test:latest"
            )

        assert len(steps) == 1
        assert "container_name" in metadata
        assert "compose_file" in metadata


class TestPlanRemoteDeploySteps:
    """Tests for _plan_remote_deploy_steps function."""

    def test_returns_steps_and_metadata(self) -> None:
        """Test returns steps and metadata for remote deploy."""
        app_cli = _create_mock_app_cli()
        contract = _make_contract()

        steps, metadata = _plan_remote_deploy_steps(
            app_cli, contract, repo_root=Path("/tmp"), target="remote", image_ref="test:latest"
        )

        assert len(steps) >= 4  # dirs, compose, env, install, up
        assert "container_name" in metadata
        assert "remote_compose" in metadata
        assert "remote_env" in metadata

    def test_includes_transition_step_when_present(self) -> None:
        """Test includes transition step when present."""
        app_cli = _create_mock_app_cli()
        app_cli._control_plane_transition_step.return_value = (["echo", "stop"], "stop")
        contract = _make_contract()

        with patch("agentplane.domain.app.delivery_handlers_planning._transition_step_to_execution") as mock_transition:
            mock_transition.return_value = MagicMock()

            steps, _ = _plan_remote_deploy_steps(
                app_cli, contract, repo_root=Path("/tmp"), target="remote", image_ref="test:latest"
            )

        assert len(steps) >= 5  # dirs, compose, env, install, transition, up


class TestPlanDeliveryVerifySteps:
    """Tests for _plan_delivery_verify_steps function."""

    def test_returns_wsl_verify_steps(self) -> None:
        """Test returns verify steps for wsl target."""
        app_cli = _create_mock_app_cli()
        contract = _make_contract()

        with patch("agentplane.domain.app.delivery_handlers_planning.detect_host_profile") as mock_detect:
            mock_detect.return_value = MagicMock(linux_backend="wsl")

            steps, container_name = _plan_delivery_verify_steps(
                app_cli, contract, repo_root=Path("/tmp"), target="wsl", include_public=False
            )

        assert len(steps) == 1
        assert container_name == "test-app-prod"

    def test_returns_remote_verify_steps(self) -> None:
        """Test returns verify steps for remote target."""
        app_cli = _create_mock_app_cli()
        contract = _make_contract()

        steps, container_name = _plan_delivery_verify_steps(
            app_cli, contract, repo_root=Path("/tmp"), target="remote", include_public=False
        )

        assert len(steps) == 2  # inspect, health
        assert container_name == "test-app-prod"

    def test_includes_public_steps_when_enabled(self) -> None:
        """Test includes public steps when include_public is True and has public ingress."""
        app_cli = _create_mock_app_cli()
        app_cli.has_public_ingress.return_value = True
        app_cli.public_sites.return_value = [{"public_url": "https://example.com"}]
        contract = _make_contract()

        with patch("agentplane.domain.app.delivery_handlers_planning.detect_host_profile") as mock_detect:
            mock_detect.return_value = MagicMock(linux_backend="linux-native")

            steps, _ = _plan_delivery_verify_steps(
                app_cli, contract, repo_root=Path("/tmp"), target="remote", include_public=True
            )

        assert len(steps) == 4  # inspect, health, public health, public headers


class TestPlanProductionVerify:
    """Tests for _plan_production_verify function."""

    def test_returns_planned_result(self) -> None:
        """Test returns planned result with commands."""
        app_cli = _create_mock_app_cli()
        contract = _make_contract()

        with (
            patch("agentplane.domain.app.delivery_handlers_planning._plan_delivery_verify_steps") as mock_plan,
            patch("agentplane.domain.app.delivery_handlers_planning._render_execution_steps") as mock_render,
        ):
            mock_plan.return_value = ([MagicMock()], "test-app-prod")
            mock_render.return_value = [{"backend": {"display_command": "curl http://localhost:8080/health"}}]

            result = _plan_production_verify(
                app_cli, contract, repo_root=Path("/tmp"), target="remote", include_public=False
            )

        assert result["status"] == "planned"
        assert "commands" in result
        assert "execution_steps" in result


class TestExecuteOriginVerify:
    """Tests for _execute_origin_verify function."""

    def test_returns_verification_result(self) -> None:
        """Test returns verification result with checks."""
        app_cli = _create_mock_app_cli()
        contract = _make_contract()

        with (
            patch("agentplane.domain.app.delivery_handlers_planning._plan_delivery_verify_steps") as mock_plan,
            patch("agentplane.domain.app.delivery_handlers_planning._execute_steps") as mock_exec,
        ):
            mock_plan.return_value = ([MagicMock()], "test-app-prod")
            mock_exec.return_value = [{"ok": True, "display": "curl http://localhost:8080/health"}]

            result = _execute_origin_verify(
                app_cli, contract, repo_root=Path("/tmp"), target="remote"
            )

        assert result["ok"] is True
        assert "checks" in result
        assert "commands" in result

    def test_returns_failed_when_checks_fail(self) -> None:
        """Test returns failed result when checks fail."""
        app_cli = _create_mock_app_cli()
        contract = _make_contract()

        with (
            patch("agentplane.domain.app.delivery_handlers_planning._plan_delivery_verify_steps") as mock_plan,
            patch("agentplane.domain.app.delivery_handlers_planning._execute_steps") as mock_exec,
        ):
            mock_plan.return_value = ([MagicMock()], "test-app-prod")
            mock_exec.return_value = [{"ok": False, "display": "curl failed"}]

            result = _execute_origin_verify(
                app_cli, contract, repo_root=Path("/tmp"), target="remote"
            )

        assert result["ok"] is False
