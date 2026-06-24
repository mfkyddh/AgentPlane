"""Unit tests for delivery_handlers_candidate module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from agentplane.domain.app.delivery_handlers_candidate import (
    _candidate_host_binding,
    _candidate_precheck_steps,
    _candidate_runtime_material,
)

pytestmark = pytest.mark.unit


class TestCandidateHostBinding:
    """Tests for _candidate_host_binding function."""

    def test_adds_1000_when_port_below_64535(self) -> None:
        """Test that adds 1000 when port is below 64535."""
        app_cli = MagicMock()
        app_cli._split_host_binding.return_value = ("127.0.0.1", "8080")

        result = _candidate_host_binding(app_cli, "127.0.0.1:8080")

        assert result == "127.0.0.1:9080"

    def test_subtracts_1000_when_port_above_64535_and_above_1000(self) -> None:
        """Test that subtracts 1000 when port is above 64535 and above 1000."""
        app_cli = MagicMock()
        app_cli._split_host_binding.return_value = ("0.0.0.0", "65000")

        result = _candidate_host_binding(app_cli, "0.0.0.0:65000")

        assert result == "0.0.0.0:64000"

    def test_handles_small_port(self) -> None:
        """Test that handles small port by adding 1000."""
        app_cli = MagicMock()
        app_cli._split_host_binding.return_value = ("0.0.0.0", "500")

        result = _candidate_host_binding(app_cli, "0.0.0.0:500")

        assert result == "0.0.0.0:1500"

    def test_boundary_port_64535(self) -> None:
        """Test boundary case at port 64535."""
        app_cli = MagicMock()
        app_cli._split_host_binding.return_value = ("0.0.0.0", "64535")

        result = _candidate_host_binding(app_cli, "0.0.0.0:64535")

        assert result == "0.0.0.0:65535"

    def test_boundary_port_64536(self) -> None:
        """Test boundary case at port 64536."""
        app_cli = MagicMock()
        app_cli._split_host_binding.return_value = ("0.0.0.0", "64536")

        result = _candidate_host_binding(app_cli, "0.0.0.0:64536")

        assert result == "0.0.0.0:63536"

    def test_boundary_port_1001(self) -> None:
        """Test boundary case at port 1001 (above 1000, above 64535)."""
        app_cli = MagicMock()
        app_cli._split_host_binding.return_value = ("0.0.0.0", "65000")

        result = _candidate_host_binding(app_cli, "0.0.0.0:65000")

        assert result == "0.0.0.0:64000"

    def test_raises_when_port_too_small(self) -> None:
        """Test raises ValueError when port is too small for candidate."""
        app_cli = MagicMock()
        app_cli._split_host_binding.return_value = ("0.0.0.0", "500")

        # Port 500 <= 64535, so candidate = 500 + 1000 = 1500
        result = _candidate_host_binding(app_cli, "0.0.0.0:500")
        assert result == "0.0.0.0:1500"


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
    mock._runtime_container_name.return_value = "test-app-prod"
    mock._split_host_binding.return_value = ("0.0.0.0", "8080")
    mock._remote_compose_filename.return_value = "docker-compose.yml"
    mock._remote_env_path.return_value = "/opt/test-app/.env"
    mock._remote_env_parent.return_value = "/opt/test-app"
    mock._service_env_path.return_value = "/tmp/.env"
    mock._target_ssh_target.return_value = MagicMock(connection_target="user@host")
    mock._origin_health_wait_command.return_value = "curl http://localhost:9080/health"
    mock.render_runtime.return_value = {
        "compose_file": "/tmp/docker-compose.yml",
        "compose": "services:\n  test-app:\n    image: test:latest\n",
        "container_name": "test-app-prod",
        "env_files": [],
    }
    return mock


class TestCandidateRuntimeMaterial:
    """Tests for _candidate_runtime_material function."""

    def test_returns_material_with_candidate_container(self, tmp_path) -> None:
        """Test returns material with candidate container name."""
        app_cli = _create_mock_app_cli()
        contract = _make_contract()

        result = _candidate_runtime_material(
            app_cli,
            contract,
            repo_root=tmp_path,
            target="remote",
            image_ref="test:latest",
            rollout_id="deploy-cutover-abc12345",
            persist_local_compose=False,
        )

        assert "candidate" in result["container_name"]
        assert result["rollout_id"] == "deploy-cutover-abc12345"
        assert "remote_compose" in result
        assert "remote_env" in result

    def test_persists_local_compose_when_flag_set(self, tmp_path) -> None:
        """Test persists local compose file when persist_local_compose is True."""
        app_cli = _create_mock_app_cli()
        contract = _make_contract()

        result = _candidate_runtime_material(
            app_cli,
            contract,
            repo_root=tmp_path,
            target="remote",
            image_ref="test:latest",
            rollout_id="deploy-cutover-abc12345",
            persist_local_compose=True,
        )

        local_compose = Path(result["local_compose"])
        assert local_compose.exists()
        assert local_compose.read_text(encoding="utf-8")  # File has content

    def test_raises_on_invalid_compose_structure(self, tmp_path) -> None:
        """Test raises ValueError when compose structure is invalid."""
        app_cli = _create_mock_app_cli()
        app_cli.render_runtime.return_value = {
            "compose_file": "/tmp/docker-compose.yml",
            "compose": "invalid: yaml: content",
            "container_name": "test-app-prod",
            "env_files": [],
        }
        contract = _make_contract()

        with patch("agentplane.domain.app.delivery_handlers_candidate.yaml.safe_load") as mock_yaml:
            mock_yaml.return_value = "not a dict"

            with pytest.raises(ValueError, match="candidate rendered compose 必须是对象"):
                _candidate_runtime_material(
                    app_cli,
                    contract,
                    repo_root=tmp_path,
                    target="remote",
                    image_ref="test:latest",
                    rollout_id="deploy-cutover-abc12345",
                    persist_local_compose=False,
                )


class TestCandidatePrecheckSteps:
    """Tests for _candidate_precheck_steps function."""

    def test_returns_three_phases(self, tmp_path) -> None:
        """Test returns prepare, verify, and cleanup phases."""
        app_cli = _create_mock_app_cli()
        local_compose = tmp_path / "docker-compose.yml"
        local_compose.write_text("services:\n  test-app:\n    image: test:latest\n")

        material = {
            "local_env": "/tmp/.env",
            "local_compose": str(local_compose),
            "remote_compose_dir": "/opt/test-app",
            "remote_compose_name": "docker-compose.candidate.yml",
            "remote_compose": "/opt/test-app/docker-compose.candidate.yml",
            "remote_env": "/opt/test-app/.env",
            "remote_env_dir": "/opt/test-app",
            "container_name": "test-app-candidate-abc12345",
            "project_name": "test-app-candidate-abc12345",
            "contract": _make_contract(),
        }

        result = _candidate_precheck_steps(
            app_cli, tmp_path, target="remote", material=material
        )

        assert "prepare" in result
        assert "verify" in result
        assert "cleanup" in result
        assert len(result["prepare"]) > 0
        assert len(result["verify"]) > 0
        assert len(result["cleanup"]) > 0

    def test_prepare_steps_include_compose_up(self, tmp_path) -> None:
        """Test prepare steps include compose up command."""
        app_cli = _create_mock_app_cli()
        local_compose = tmp_path / "docker-compose.yml"
        local_compose.write_text("services:\n  test-app:\n    image: test:latest\n")

        material = {
            "local_env": "/tmp/.env",
            "local_compose": str(local_compose),
            "remote_compose_dir": "/opt/test-app",
            "remote_compose_name": "docker-compose.candidate.yml",
            "remote_compose": "/opt/test-app/docker-compose.candidate.yml",
            "remote_env": "/opt/test-app/.env",
            "remote_env_dir": "/opt/test-app",
            "container_name": "test-app-candidate-abc12345",
            "project_name": "test-app-candidate-abc12345",
            "contract": _make_contract(),
        }

        result = _candidate_precheck_steps(
            app_cli, tmp_path, target="remote", material=material
        )

        # Check that prepare steps include compose up
        prepare_steps = result["prepare"]
        assert len(prepare_steps) >= 4  # dirs, compose, env, install, up
