"""Unit tests for delivery_handlers_planning module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from agentplane.domain.app.delivery_handlers_planning import (
    _plan_delivery_rollback_steps,
    _plan_production_rollback,
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
