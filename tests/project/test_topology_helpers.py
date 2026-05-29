"""Tests for agentplane.domain.project.topology — pure helper functions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from agentplane.domain.project.topology import (
    _extract_dependencies,
    _host_status,
    _load_inventory,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# _extract_dependencies
# ---------------------------------------------------------------------------


class TestExtractDependencies:
    def test_with_healthcheck(self) -> None:
        contract: dict[str, Any] = {"runtime": {"healthcheck": {"path": "/health"}}}
        deps = _extract_dependencies(contract)
        assert len(deps) == 1
        assert deps[0]["kind"] == "healthcheck"
        assert deps[0]["path"] == "/health"

    def test_no_healthcheck(self) -> None:
        contract: dict[str, Any] = {"runtime": {}}
        deps = _extract_dependencies(contract)
        assert deps == []

    def test_no_runtime(self) -> None:
        deps = _extract_dependencies({})
        assert deps == []

    def test_runtime_not_dict(self) -> None:
        deps = _extract_dependencies({"runtime": "invalid"})
        assert deps == []

    def test_healthcheck_no_path(self) -> None:
        contract: dict[str, Any] = {"runtime": {"healthcheck": {}}}
        deps = _extract_dependencies(contract)
        assert deps == []


# ---------------------------------------------------------------------------
# _load_inventory
# ---------------------------------------------------------------------------


class TestTopologyLoadInventory:
    def test_valid(self, tmp_path: Path) -> None:
        inv_dir = tmp_path / "inventory" / "servers" / "wsl"
        inv_dir.mkdir(parents=True)
        inv_file = inv_dir / "inventory.json"
        inv_file.write_text('{"hostname": "test"}', encoding="utf-8")
        result = _load_inventory(tmp_path, "wsl")
        assert result["hostname"] == "test"

    def test_missing(self, tmp_path: Path) -> None:
        result = _load_inventory(tmp_path, "wsl")
        assert result == {}

    def test_invalid_json(self, tmp_path: Path) -> None:
        inv_dir = tmp_path / "inventory" / "servers" / "wsl"
        inv_dir.mkdir(parents=True)
        inv_file = inv_dir / "inventory.json"
        inv_file.write_text("not json", encoding="utf-8")
        result = _load_inventory(tmp_path, "wsl")
        assert result == {}


# ---------------------------------------------------------------------------
# _host_status
# ---------------------------------------------------------------------------


class TestTopologyHostStatus:
    def test_with_services(self) -> None:
        assert _host_status({"services": {"postgres": {}}}) == "connected"

    def test_empty_services(self) -> None:
        assert _host_status({"services": {}}) == "unknown"

    def test_no_services(self) -> None:
        assert _host_status({}) == "unknown"


# ---------------------------------------------------------------------------
# Golden test
# ---------------------------------------------------------------------------


@pytest.mark.golden
class TestTopologyGolden:
    def test_full_dependency_extraction(self) -> None:
        """Contract with multiple runtime fields extracts healthcheck only."""
        contract: dict[str, Any] = {
            "runtime": {
                "container_port": 3000,
                "healthcheck": {"path": "/api/health", "interval": 30},
                "environment": {"LOG_LEVEL": "info"},
            }
        }
        deps = _extract_dependencies(contract)
        assert len(deps) == 1
        assert deps[0]["kind"] == "healthcheck"
        assert deps[0]["path"] == "/api/health"
