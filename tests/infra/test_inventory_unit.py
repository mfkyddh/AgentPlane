"""Unit tests for inventory module."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from agentplane.domain.infra.inventory import (
    _docker_container_rows,
    _load_existing_wsl_metadata,
    _load_json_file,
    _normalize_compose_label_paths,
    _strip_container_labels,
    _symlink_state,
    _tracked_wsl_snapshot,
    _wsl_backend_type,
    _wsl_inventory_file,
    _wsl_snapshot,
    generate_inventory_snapshot,
)

pytestmark = pytest.mark.unit


class TestRunCommand:
    """Tests for _run_command function."""

    def test_returns_completed_process(self) -> None:
        """Test that returns CompletedProcess."""
        from agentplane.domain.infra.inventory import _run_command

        result = _run_command(["echo", "hello"])
        assert result.returncode == 0
        assert "hello" in result.stdout


class TestDockerContainerRows:
    """Tests for _docker_container_rows function."""

    def test_returns_empty_on_failure(self) -> None:
        """Test that returns empty list on failure."""
        with patch("agentplane.domain.infra.inventory._run_command") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="")
            result = _docker_container_rows()

        assert result == []

    def test_parses_docker_output(self) -> None:
        """Test that parses docker output correctly."""
        with patch("agentplane.domain.infra.inventory._run_command") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="redis|redis:7|6379->6379|Up 1 minute|/path/to/docker-compose.yml\n"
            )
            result = _docker_container_rows()

        assert len(result) == 1
        assert result[0]["name"] == "redis"
        assert result[0]["image"] == "redis:7"
        assert result[0]["ports"] == "6379->6379"
        assert result[0]["status"] == "Up 1 minute"

    def test_skips_empty_lines(self) -> None:
        """Test that skips empty lines."""
        with patch("agentplane.domain.infra.inventory._run_command") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="redis|redis:7|6379->6379|Up 1 minute|\n\n\n")
            result = _docker_container_rows()

        assert len(result) == 1


class TestSymlinkState:
    """Tests for _symlink_state function."""

    def test_returns_state_for_existing_path(self, tmp_path: Path) -> None:
        """Test that returns state for existing path."""
        path = tmp_path / "test"
        path.mkdir()

        result = _symlink_state(path)

        assert result["path"] == str(path)
        assert result["exists"] is True
        assert result["is_symlink"] is False
        assert result["target"] is None

    def test_returns_state_for_missing_path(self, tmp_path: Path) -> None:
        """Test that returns state for missing path."""
        path = tmp_path / "missing"

        result = _symlink_state(path)

        assert result["path"] == str(path)
        assert result["exists"] is False
        assert result["is_symlink"] is False


class TestWslInventoryFile:
    """Tests for _wsl_inventory_file function."""

    def test_returns_correct_path(self, tmp_path: Path) -> None:
        """Test that returns correct path."""
        result = _wsl_inventory_file(tmp_path)

        assert result == tmp_path / "inventory" / "servers" / "wsl" / "inventory.json"


class TestLoadExistingWslMetadata:
    """Tests for _load_existing_wsl_metadata function."""

    def test_returns_empty_when_no_file(self, tmp_path: Path) -> None:
        """Test that returns empty dict when no file exists."""
        result = _load_existing_wsl_metadata(tmp_path)

        assert result == {}

    def test_returns_empty_on_invalid_json(self, tmp_path: Path) -> None:
        """Test that returns empty dict on invalid JSON."""
        inventory_file = tmp_path / "inventory" / "servers" / "wsl" / "inventory.json"
        inventory_file.parent.mkdir(parents=True)
        inventory_file.write_text("invalid json", encoding="utf-8")

        result = _load_existing_wsl_metadata(tmp_path)

        assert result == {}

    def test_returns_empty_on_non_dict(self, tmp_path: Path) -> None:
        """Test that returns empty dict on non-dict payload."""
        inventory_file = tmp_path / "inventory" / "servers" / "wsl" / "inventory.json"
        inventory_file.parent.mkdir(parents=True)
        inventory_file.write_text('["not", "a", "dict"]', encoding="utf-8")

        result = _load_existing_wsl_metadata(tmp_path)

        assert result == {}

    def test_preserves_automations(self, tmp_path: Path) -> None:
        """Test that preserves automations metadata."""
        inventory_file = tmp_path / "inventory" / "servers" / "wsl" / "inventory.json"
        inventory_file.parent.mkdir(parents=True)
        inventory_file.write_text(
            json.dumps({"automations": [{"name": "test"}]}),
            encoding="utf-8",
        )

        result = _load_existing_wsl_metadata(tmp_path)

        assert "automations" in result
        assert result["automations"][0]["name"] == "test"

    def test_preserves_services(self, tmp_path: Path) -> None:
        """Test that preserves services metadata."""
        inventory_file = tmp_path / "inventory" / "servers" / "wsl" / "inventory.json"
        inventory_file.parent.mkdir(parents=True)
        inventory_file.write_text(
            json.dumps({"services": {"redis": {"status": "running"}}}),
            encoding="utf-8",
        )

        result = _load_existing_wsl_metadata(tmp_path)

        assert "services" in result
        assert result["services"]["redis"]["status"] == "running"

    def test_preserves_host_truth(self, tmp_path: Path) -> None:
        """Test that preserves host_truth metadata."""
        inventory_file = tmp_path / "inventory" / "servers" / "wsl" / "inventory.json"
        inventory_file.parent.mkdir(parents=True)
        inventory_file.write_text(
            json.dumps({"host_truth": {"key": "value"}}),
            encoding="utf-8",
        )

        result = _load_existing_wsl_metadata(tmp_path)

        assert "host_truth" in result
        assert result["host_truth"]["key"] == "value"


class TestNormalizeComposeLabelPaths:
    """Tests for _normalize_compose_label_paths function."""

    def test_returns_empty_for_non_string(self) -> None:
        """Test that returns empty set for non-string."""
        assert _normalize_compose_label_paths(None) == set()
        assert _normalize_compose_label_paths(123) == set()

    def test_splits_comma_separated_paths(self) -> None:
        """Test that splits comma-separated paths."""
        result = _normalize_compose_label_paths("/path1,/path2,/path3")

        assert result == {"/path1", "/path2", "/path3"}

    def test_strips_whitespace(self) -> None:
        """Test that strips whitespace."""
        result = _normalize_compose_label_paths(" /path1 , /path2 ")

        assert result == {"/path1", "/path2"}

    def test_filters_empty_strings(self) -> None:
        """Test that filters empty strings."""
        result = _normalize_compose_label_paths("/path1,,/path2,")

        assert result == {"/path1", "/path2"}


class TestStripContainerLabels:
    """Tests for _strip_container_labels function."""

    def test_strips_labels(self) -> None:
        """Test that strips labels from container row."""
        row = {
            "name": "redis",
            "image": "redis:7",
            "ports": "6379->6379",
            "status": "Up 1 minute",
            "labels": {"com.docker.compose.project.config_files": "/path/to/compose"},
        }

        result = _strip_container_labels(row)

        assert result == {
            "name": "redis",
            "image": "redis:7",
            "ports": "6379->6379",
            "status": "Up 1 minute",
        }
        assert "labels" not in result

    def test_handles_missing_fields(self) -> None:
        """Test that handles missing fields."""
        row = {}

        result = _strip_container_labels(row)

        assert result == {
            "name": "",
            "image": "",
            "ports": "",
            "status": "",
        }


class TestWslSnapshot:
    """Tests for _wsl_snapshot function."""

    def test_returns_snapshot_payload(self, tmp_path: Path) -> None:
        """Test that returns snapshot payload."""
        compose_root = tmp_path / "infra" / "compose" / "redis"
        compose_root.mkdir(parents=True)

        with patch("agentplane.domain.infra.inventory._docker_container_rows", return_value=[]):
            result = _wsl_snapshot(tmp_path)

        assert result["label"] == "WSL 跳板机"
        assert result["target"] == "wsl"
        assert "hostname" in result
        assert "os" in result
        assert result["compose_services"] == ["redis"]

    def test_separates_managed_and_unmanaged_containers(self, tmp_path: Path) -> None:
        """Test that separates managed and unmanaged containers."""
        compose_root = tmp_path / "infra" / "compose" / "redis"
        compose_root.mkdir(parents=True)
        compose_file = compose_root / "docker-compose.wsl.yml"
        compose_file.touch()

        rows = [
            {
                "name": "redis",
                "image": "redis:7",
                "ports": "6379->6379",
                "status": "Up 1 minute",
                "labels": {"com.docker.compose.project.config_files": str(compose_file)},
            },
            {
                "name": "foreign",
                "image": "busybox",
                "ports": "",
                "status": "Up 1 minute",
                "labels": {"com.docker.compose.project.config_files": "/tmp/foreign/docker-compose.yml"},
            },
        ]

        with patch("agentplane.domain.infra.inventory._docker_container_rows", return_value=rows):
            result = _wsl_snapshot(tmp_path)

        assert len(result["docker_containers"]) == 1
        assert result["docker_containers"][0]["name"] == "redis"
        assert len(result["unmanaged_docker_containers"]) == 1
        assert result["unmanaged_docker_containers"][0]["name"] == "foreign"


class TestWslBackendType:
    """Tests for _wsl_backend_type function."""

    def test_returns_backend_type(self) -> None:
        """Test that returns backend type."""
        mock_profile = MagicMock()
        mock_resolver = MagicMock()
        mock_resolver.resolve.return_value = MagicMock(execution_backend="linux-native")

        with patch("agentplane.domain.infra.inventory.detect_host_profile", return_value=mock_profile):
            with patch("agentplane.domain.infra.inventory.TargetResolver", return_value=mock_resolver):
                result = _wsl_backend_type()

        assert result == "linux-native"


class TestTrackedWslSnapshot:
    """Tests for _tracked_wsl_snapshot function."""

    def test_returns_tracked_snapshot(self, tmp_path: Path) -> None:
        """Test that returns tracked snapshot."""
        inventory_file = tmp_path / "inventory" / "servers" / "wsl" / "inventory.json"
        inventory_file.parent.mkdir(parents=True)
        inventory_file.write_text(
            json.dumps({"label": "test"}),
            encoding="utf-8",
        )

        result = _tracked_wsl_snapshot(tmp_path)

        assert result["label"] == "test"
        assert result["target"] == "wsl"
        assert result["collection_mode"] == "tracked-snapshot"
        assert "live_collection_required" in result


class TestLoadJsonFile:
    """Tests for _load_json_file function."""

    def test_returns_missing_status(self, tmp_path: Path) -> None:
        """Test that returns missing status when file doesn't exist."""
        path = tmp_path / "missing.json"

        result = _load_json_file(path)

        assert result["status"] == "missing"
        assert result["inventory_file"] == str(path)

    def test_returns_invalid_json_status(self, tmp_path: Path) -> None:
        """Test that returns invalid_json status on parse error."""
        path = tmp_path / "invalid.json"
        path.write_text("invalid json", encoding="utf-8")

        result = _load_json_file(path)

        assert result["status"] == "invalid_json"
        assert "error" in result

    def test_returns_ok_status(self, tmp_path: Path) -> None:
        """Test that returns ok status with valid JSON."""
        path = tmp_path / "valid.json"
        path.write_text(json.dumps({"key": "value"}), encoding="utf-8")

        result = _load_json_file(path)

        assert result["status"] == "ok"
        assert result["key"] == "value"


class TestGenerateInventorySnapshot:
    """Tests for generate_inventory_snapshot function."""

    def test_raises_on_unsupported_target(self, tmp_path: Path) -> None:
        """Test that raises ValueError on unsupported target."""
        with pytest.raises(ValueError, match="Unsupported inventory target"):
            generate_inventory_snapshot(tmp_path, "unsupported")

    def test_wsl_target_with_linux_backend(self, tmp_path: Path) -> None:
        """Test that wsl target with linux backend returns snapshot."""
        with patch("agentplane.domain.infra.inventory._wsl_backend_type", return_value="linux-native"):
            with patch("agentplane.domain.infra.inventory._wsl_snapshot", return_value={"test": "data"}):
                result = generate_inventory_snapshot(tmp_path, "wsl")

        assert result["command"] == "inventory"
        assert result["target"] == "wsl"
        assert result["payload"] == {"test": "data"}

    def test_wsl_target_with_windows_backend_and_runner(self, tmp_path: Path) -> None:
        """Test that wsl target with windows backend and runner returns snapshot."""
        mock_runner = MagicMock()

        with patch("agentplane.domain.infra.inventory._wsl_backend_type", return_value="windows-wsl"):
            with patch("agentplane.domain.infra.inventory._wsl_snapshot_via_backend", return_value={"test": "data"}):
                result = generate_inventory_snapshot(tmp_path, "wsl", runner=mock_runner)

        assert result["command"] == "inventory"
        assert result["target"] == "wsl"
        assert result["payload"] == {"test": "data"}

    def test_wsl_target_with_windows_backend_no_runner(self, tmp_path: Path) -> None:
        """Test that wsl target with windows backend and no runner returns tracked snapshot."""
        with patch("agentplane.domain.infra.inventory._wsl_backend_type", return_value="windows-wsl"):
            with patch("agentplane.domain.infra.inventory._tracked_wsl_snapshot", return_value={"test": "data"}):
                result = generate_inventory_snapshot(tmp_path, "wsl")

        assert result["command"] == "inventory"
        assert result["target"] == "wsl"
        assert result["payload"] == {"test": "data"}

    def test_wsl_target_with_windows_backend_write_raises(self, tmp_path: Path) -> None:
        """Test that wsl target with windows backend and write raises ValueError."""
        with patch("agentplane.domain.infra.inventory._wsl_backend_type", return_value="windows-wsl"):
            with pytest.raises(ValueError, match="live WSL inventory write requires"):
                generate_inventory_snapshot(tmp_path, "wsl", write=True)

    def test_prod0_target(self, tmp_path: Path) -> None:
        """Test that prod0-main target returns inventory."""
        inventory_file = tmp_path / "inventory" / "servers" / "prod0-main" / "inventory.json"
        inventory_file.parent.mkdir(parents=True)
        inventory_file.write_text(json.dumps({"test": "data"}), encoding="utf-8")

        result = generate_inventory_snapshot(tmp_path, "prod0-main")

        assert result["command"] == "inventory"
        assert result["target"] == "prod0-main"
        assert result["payload"]["test"] == "data"

    def test_write_creates_file(self, tmp_path: Path) -> None:
        """Test that write=True creates inventory file."""
        with patch("agentplane.domain.infra.inventory._wsl_backend_type", return_value="linux-native"):
            with patch("agentplane.domain.infra.inventory._wsl_snapshot", return_value={"test": "data"}):
                generate_inventory_snapshot(tmp_path, "wsl", write=True)

        inventory_file = tmp_path / "inventory" / "servers" / "wsl" / "inventory.json"
        assert inventory_file.exists()
        assert json.loads(inventory_file.read_text(encoding="utf-8")) == {"test": "data"}
