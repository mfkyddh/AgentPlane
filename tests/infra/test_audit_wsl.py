"""Unit tests for audit_wsl module."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from agentplane.domain.infra.audit_wsl import (
    _audit_wsl_host_state,
    _audit_wsl_host_state_via_backend,
    _audit_wsl_templates,
    _host_path_exists,
    _host_path_is_symlink,
    _inventory_compose_service_names,
    _wsl_backend_type,
    _wsl_required_compose_targets,
)

pytestmark = pytest.mark.unit


class TestInventoryComposeServiceNames:
    """Tests for _inventory_compose_service_names function."""

    def test_returns_empty_for_missing_file(self, tmp_path: Path) -> None:
        """Test that returns empty set for missing file."""
        path = tmp_path / "missing.json"

        result = _inventory_compose_service_names(path, target="wsl")

        assert result == set()

    def test_returns_empty_for_invalid_json(self, tmp_path: Path) -> None:
        """Test that returns empty set for invalid JSON."""
        path = tmp_path / "invalid.json"
        path.write_text("invalid", encoding="utf-8")

        result = _inventory_compose_service_names(path, target="wsl")

        assert result == set()

    def test_returns_empty_for_non_dict_services(self, tmp_path: Path) -> None:
        """Test that returns empty set for non-dict services."""
        path = tmp_path / "inventory.json"
        path.write_text(json.dumps({"services": "not-a-dict"}), encoding="utf-8")

        result = _inventory_compose_service_names(path, target="wsl")

        assert result == set()

    def test_returns_all_service_names_for_wsl_target(self, tmp_path: Path) -> None:
        """Test that returns all service names for wsl target."""
        path = tmp_path / "inventory.json"
        path.write_text(
            json.dumps(
                {
                    "services": {
                        "redis": {"status": "running"},
                        "postgres": {"status": "running"},
                    }
                }
            ),
            encoding="utf-8",
        )

        result = _inventory_compose_service_names(path, target="wsl")

        assert result == {"redis", "postgres"}

    def test_returns_only_compose_services_for_prod0_target(self, tmp_path: Path) -> None:
        """Test that returns only compose services for prod0-main target."""
        path = tmp_path / "inventory.json"
        path.write_text(
            json.dumps(
                {
                    "services": {
                        "redis": {"control_plane": "compose", "status": "running"},
                        "nginx": {"control_plane": "1panel", "status": "running"},
                    }
                }
            ),
            encoding="utf-8",
        )

        result = _inventory_compose_service_names(path, target="prod0-main")

        assert result == {"redis"}
        assert "nginx" not in result

    def test_skips_non_dict_service_payload(self, tmp_path: Path) -> None:
        """Test that skips non-dict service payload."""
        path = tmp_path / "inventory.json"
        path.write_text(
            json.dumps(
                {
                    "services": {
                        "redis": "not-a-dict",
                        "postgres": {"status": "running"},
                    }
                }
            ),
            encoding="utf-8",
        )

        result = _inventory_compose_service_names(path, target="wsl")

        assert result == {"postgres"}


class TestWslRequiredComposeTargets:
    """Tests for _wsl_required_compose_targets function."""

    def test_returns_both_targets(self, tmp_path: Path) -> None:
        """Test that returns both wsl and prod0-main targets."""
        wsl_dir = tmp_path / "inventory" / "servers" / "wsl"
        wsl_dir.mkdir(parents=True)
        (wsl_dir / "inventory.json").write_text(
            json.dumps({"services": {"redis": {}}}),
            encoding="utf-8",
        )

        prod0_dir = tmp_path / "inventory" / "servers" / "prod0-main"
        prod0_dir.mkdir(parents=True)
        (prod0_dir / "inventory.json").write_text(
            json.dumps({"services": {"postgres": {"control_plane": "compose"}}}),
            encoding="utf-8",
        )

        result = _wsl_required_compose_targets(tmp_path)

        assert "wsl" in result
        assert "prod0-main" in result
        assert "redis" in result["wsl"]
        assert "postgres" in result["prod0-main"]


class TestHostPathHelpers:
    """Tests for _host_path_exists and _host_path_is_symlink functions."""

    def test_host_path_exists_returns_true(self, tmp_path: Path) -> None:
        """Test that returns True for existing path."""
        path = tmp_path / "exists"
        path.mkdir()

        assert _host_path_exists(path) is True

    def test_host_path_exists_returns_false(self, tmp_path: Path) -> None:
        """Test that returns False for missing path."""
        path = tmp_path / "missing"

        assert _host_path_exists(path) is False

    def test_host_path_is_symlink_returns_false(self, tmp_path: Path) -> None:
        """Test that returns False for non-symlink."""
        path = tmp_path / "regular"
        path.mkdir()

        assert _host_path_is_symlink(path) is False


class TestAuditWslTemplates:
    """Tests for _audit_wsl_templates function."""

    def test_returns_empty_for_no_compose_root(self, tmp_path: Path) -> None:
        """Test that returns empty list when no compose root."""
        result = _audit_wsl_templates(tmp_path)

        assert result == []

    def test_detects_legacy_compose_yml(self, tmp_path: Path) -> None:
        """Test that detects legacy docker-compose.yml."""
        compose_root = tmp_path / "infra" / "compose" / "test-service"
        compose_root.mkdir(parents=True)
        (compose_root / "docker-compose.yml").touch()

        with patch(
            "agentplane.domain.infra.audit_wsl._wsl_required_compose_targets",
            return_value={"wsl": set(), "prod0-main": set()},
        ):
            result = _audit_wsl_templates(tmp_path)

        assert any("legacy.compose_entrypoint" in v["id"] for v in result)

    def test_detects_legacy_env_file(self, tmp_path: Path) -> None:
        """Test that detects legacy .env file."""
        compose_root = tmp_path / "infra" / "compose" / "test-service"
        compose_root.mkdir(parents=True)
        (compose_root / ".env").touch()

        with patch(
            "agentplane.domain.infra.audit_wsl._wsl_required_compose_targets",
            return_value={"wsl": set(), "prod0-main": set()},
        ):
            result = _audit_wsl_templates(tmp_path)

        assert any("legacy.env_file" in v["id"] for v in result)

    def test_detects_private_env_file(self, tmp_path: Path) -> None:
        """Test that detects private env file in compose directory."""
        compose_root = tmp_path / "infra" / "compose" / "test-service"
        compose_root.mkdir(parents=True)
        (compose_root / ".env.prod").touch()

        with patch(
            "agentplane.domain.infra.audit_wsl._wsl_required_compose_targets",
            return_value={"wsl": set(), "prod0-main": set()},
        ):
            result = _audit_wsl_templates(tmp_path)

        assert any("compose.private_env_file" in v["id"] for v in result)

    def test_skips_example_env_files(self, tmp_path: Path) -> None:
        """Test that skips .example env files."""
        compose_root = tmp_path / "infra" / "compose" / "test-service"
        compose_root.mkdir(parents=True)
        (compose_root / ".env.prod.example").touch()

        with patch(
            "agentplane.domain.infra.audit_wsl._wsl_required_compose_targets",
            return_value={"wsl": set(), "prod0-main": set()},
        ):
            result = _audit_wsl_templates(tmp_path)

        assert not any("private_env_file" in v["id"] for v in result)

    def test_detects_missing_wsl_compose(self, tmp_path: Path) -> None:
        """Test that detects missing docker-compose.wsl.yml."""
        compose_root = tmp_path / "infra" / "compose" / "test-service"
        compose_root.mkdir(parents=True)

        with patch(
            "agentplane.domain.infra.audit_wsl._wsl_required_compose_targets",
            return_value={"wsl": {"test-service"}, "prod0-main": set()},
        ):
            result = _audit_wsl_templates(tmp_path)

        assert any("missing.compose_wsl" in v["id"] for v in result)

    def test_detects_missing_prod0_compose(self, tmp_path: Path) -> None:
        """Test that detects missing docker-compose.prod0.yml."""
        compose_root = tmp_path / "infra" / "compose" / "test-service"
        compose_root.mkdir(parents=True)

        with patch(
            "agentplane.domain.infra.audit_wsl._wsl_required_compose_targets",
            return_value={"wsl": set(), "prod0-main": {"test-service"}},
        ):
            result = _audit_wsl_templates(tmp_path)

        assert any("missing.compose_prod0" in v["id"] for v in result)


class TestAuditWslHostState:
    """Tests for _audit_wsl_host_state function."""

    @patch("agentplane.domain.infra.audit_wsl._host_path_exists")
    def test_detects_forbidden_paths(self, mock_exists: MagicMock) -> None:
        """Test that detects forbidden paths."""

        def side_effect(path: Path) -> bool:
            return path.name == ".cli-proxy-api"

        mock_exists.side_effect = side_effect

        with patch("agentplane.domain.infra.audit_wsl._host_path_is_symlink", return_value=False):
            result = _audit_wsl_host_state()

        assert any("wsl.host.legacy_path" in v["id"] for v in result)

    @patch("agentplane.domain.infra.audit_wsl._host_path_exists", return_value=False)
    @patch("agentplane.domain.infra.audit_wsl._host_path_is_symlink", return_value=False)
    def test_returns_empty_when_no_violations(self, mock_symlink: MagicMock, mock_exists: MagicMock) -> None:
        """Test that returns empty when no violations."""
        result = _audit_wsl_host_state()

        # Should have violations for missing /data paths
        # but no forbidden path violations
        assert not any("legacy_path" in v["id"] for v in result)


class TestWslBackendType:
    """Tests for _wsl_backend_type function."""

    def test_returns_backend_type(self) -> None:
        """Test that returns backend type."""
        mock_profile = MagicMock()
        mock_resolver = MagicMock()
        mock_resolver.resolve.return_value = MagicMock(execution_backend="linux-native")

        with patch("agentplane.domain.infra.audit_wsl.detect_host_profile", return_value=mock_profile):
            with patch("agentplane.domain.infra.audit_wsl.TargetResolver", return_value=mock_resolver):
                result = _wsl_backend_type()

        assert result == "linux-native"


class TestAuditWslHostStateViaBackend:
    """Tests for _audit_wsl_host_state_via_backend function."""

    def test_returns_violations_from_backend(self, tmp_path: Path) -> None:
        """Test that returns violations from backend."""
        mock_runner = MagicMock()
        mock_result = MagicMock()
        mock_result.ok = True
        mock_result.stdout = json.dumps([{"kind": "test.violation", "message": "test"}])
        mock_runner.execute_spec.return_value = mock_result

        result = _audit_wsl_host_state_via_backend(tmp_path, backend_type="linux-native", runner=mock_runner)

        assert len(result) == 1
        assert result[0]["kind"] == "test.violation"

    def test_raises_on_backend_failure(self, tmp_path: Path) -> None:
        """Test that raises on backend failure."""
        mock_runner = MagicMock()
        mock_result = MagicMock()
        mock_result.ok = False
        mock_result.stdout = ""
        mock_result.stderr = "backend error"
        mock_runner.execute_spec.return_value = mock_result

        with pytest.raises(ValueError, match="backend error"):
            _audit_wsl_host_state_via_backend(tmp_path, backend_type="linux-native", runner=mock_runner)

    def test_raises_on_non_list_payload(self, tmp_path: Path) -> None:
        """Test that raises on non-list payload."""
        mock_runner = MagicMock()
        mock_result = MagicMock()
        mock_result.ok = True
        mock_result.stdout = json.dumps({"not": "a list"})
        mock_runner.execute_spec.return_value = mock_result

        with pytest.raises(ValueError, match="must be a list"):
            _audit_wsl_host_state_via_backend(tmp_path, backend_type="linux-native", runner=mock_runner)
