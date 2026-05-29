"""Tests for agentplane.domain.project.topology — inventory loading and graph building."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from agentplane.domain.project.topology import (
    _extract_dependencies,
    _host_status,
    _load_inventory,
    build_topology,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# _load_inventory
# ---------------------------------------------------------------------------


class TestLoadInventory:
    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        assert _load_inventory(tmp_path, "wsl") == {}

    def test_valid_inventory(self, tmp_path: Path) -> None:
        inv_dir = tmp_path / "inventory" / "servers" / "wsl"
        inv_dir.mkdir(parents=True)
        data = {"hostname": "box", "ssh": {"infra": "10.0.0.1"}, "services": ["nginx"]}
        (inv_dir / "inventory.json").write_text(json.dumps(data), encoding="utf-8")
        result = _load_inventory(tmp_path, "wsl")
        assert result["hostname"] == "box"
        assert result["ssh"]["infra"] == "10.0.0.1"

    def test_corrupt_json_returns_empty(self, tmp_path: Path) -> None:
        inv_dir = tmp_path / "inventory" / "servers" / "wsl"
        inv_dir.mkdir(parents=True)
        (inv_dir / "inventory.json").write_text("not-json", encoding="utf-8")
        assert _load_inventory(tmp_path, "wsl") == {}


# ---------------------------------------------------------------------------
# _host_status
# ---------------------------------------------------------------------------


class TestHostStatus:
    def test_connected_with_services(self) -> None:
        assert _host_status({"services": ["nginx"]}) == "connected"

    def test_unknown_without_services(self) -> None:
        assert _host_status({"services": []}) == "unknown"

    def test_unknown_missing_services_key(self) -> None:
        assert _host_status({}) == "unknown"


# ---------------------------------------------------------------------------
# _extract_dependencies
# ---------------------------------------------------------------------------


class TestExtractDependencies:
    def test_healthcheck_dependency(self) -> None:
        contract = {"runtime": {"healthcheck": {"path": "/health"}}}
        deps = _extract_dependencies(contract)
        assert len(deps) == 1
        assert deps[0] == {"kind": "healthcheck", "path": "/health"}

    def test_no_runtime(self) -> None:
        assert _extract_dependencies({}) == []

    def test_runtime_not_dict(self) -> None:
        assert _extract_dependencies({"runtime": "bad"}) == []

    def test_no_healthcheck_path(self) -> None:
        contract = {"runtime": {"healthcheck": {}}}
        assert _extract_dependencies(contract) == []


# ---------------------------------------------------------------------------
# build_topology
# ---------------------------------------------------------------------------


class TestBuildTopology:
    def test_empty_repo(self, tmp_path: Path) -> None:
        result = build_topology(tmp_path)
        assert result["targets"] == []
        assert "generated_at" in result

    def test_with_inventory_no_apps(self, tmp_path: Path) -> None:
        inv_dir = tmp_path / "inventory" / "servers" / "wsl"
        inv_dir.mkdir(parents=True)
        (inv_dir / "inventory.json").write_text(
            json.dumps({
                "hostname": "wsl-box",
                "ssh": {"infra": "10.0.0.1"},
                "os": "ubuntu",
                "services": ["nginx"],
            }),
            encoding="utf-8",
        )
        result = build_topology(tmp_path)
        assert len(result["targets"]) == 1
        t = result["targets"][0]
        assert t["target"] == "wsl"
        assert t["hostname"] == "wsl-box"
        assert t["ip"] == "10.0.0.1"
        assert t["status"] == "connected"
        assert t["apps"] == []
        assert t["services"] == []

    def test_generated_at_iso_format(self, tmp_path: Path) -> None:
        result = build_topology(tmp_path)
        # Should be a valid ISO timestamp
        from datetime import datetime

        datetime.fromisoformat(result["generated_at"].replace("Z", "+00:00"))


# ---------------------------------------------------------------------------
# Golden test
# ---------------------------------------------------------------------------


@pytest.mark.golden
class TestTopologyGolden:
    def test_topology_shape(self, tmp_path: Path) -> None:
        """build_topology returns the expected top-level shape."""
        result = build_topology(tmp_path)
        assert "targets" in result
        assert "generated_at" in result
        assert isinstance(result["targets"], list)
        assert isinstance(result["generated_at"], str)
