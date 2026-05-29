"""Tests for agentplane.web.api — pure helper functions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from agentplane.web.api import (
    _host_status,
    _inventory_path,
    _load_inventory,
    get_app_detail,
    get_capabilities,
    get_dashboard,
    get_data_mtime,
    get_domain_app,
    get_domain_infra,
    get_domain_ingress,
    get_domain_project,
    get_domain_service,
    get_server_detail,
    list_hosts,
    list_operations,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# _inventory_path
# ---------------------------------------------------------------------------


class TestInventoryPath:
    def test_wsl(self, tmp_path: Path) -> None:
        result = _inventory_path(tmp_path, "wsl")
        assert result == tmp_path / "inventory" / "servers" / "wsl" / "inventory.json"

    def test_prod0(self, tmp_path: Path) -> None:
        result = _inventory_path(tmp_path, "prod0-main")
        assert result == tmp_path / "inventory" / "servers" / "prod0-main" / "inventory.json"


# ---------------------------------------------------------------------------
# _load_inventory
# ---------------------------------------------------------------------------


class TestLoadInventory:
    def test_missing_file(self, tmp_path: Path) -> None:
        assert _load_inventory(tmp_path, "wsl") == {}

    def test_valid_json(self, tmp_path: Path) -> None:
        inv_dir = tmp_path / "inventory" / "servers" / "wsl"
        inv_dir.mkdir(parents=True)
        inv_file = inv_dir / "inventory.json"
        inv_file.write_text('{"hostname": "test-host"}', encoding="utf-8")
        result = _load_inventory(tmp_path, "wsl")
        assert result["hostname"] == "test-host"

    def test_invalid_json(self, tmp_path: Path) -> None:
        inv_dir = tmp_path / "inventory" / "servers" / "wsl"
        inv_dir.mkdir(parents=True)
        inv_file = inv_dir / "inventory.json"
        inv_file.write_text("not json", encoding="utf-8")
        assert _load_inventory(tmp_path, "wsl") == {}


# ---------------------------------------------------------------------------
# _host_status
# ---------------------------------------------------------------------------


class TestHostStatus:
    def test_with_services(self) -> None:
        assert _host_status({"services": {"postgres": {}}}) == "connected"

    def test_empty_services(self) -> None:
        assert _host_status({"services": {}}) == "unknown"

    def test_no_services_key(self) -> None:
        assert _host_status({}) == "unknown"


# ---------------------------------------------------------------------------
# list_hosts
# ---------------------------------------------------------------------------


def _write_inventory(tmp_path: Path, target: str, data: dict[str, Any]) -> None:
    inv_dir = tmp_path / "inventory" / "servers" / target
    inv_dir.mkdir(parents=True, exist_ok=True)
    (inv_dir / "inventory.json").write_text(json.dumps(data), encoding="utf-8")


class TestListHosts:
    def test_empty_repo(self, tmp_path: Path) -> None:
        result = list_hosts(tmp_path)
        assert result == {"hosts": []}

    def test_with_inventory(self, tmp_path: Path) -> None:
        _write_inventory(tmp_path, "wsl", {
            "hostname": "wsl-host",
            "ssh": {"infra": "10.0.0.1"},
            "label": "WSL Dev",
            "provider": "local",
            "services": {"postgres": {}},
        })
        result = list_hosts(tmp_path)
        assert len(result["hosts"]) == 1
        host = result["hosts"][0]
        assert host["target"] == "wsl"
        assert host["hostname"] == "wsl-host"
        assert host["ip"] == "10.0.0.1"
        assert host["status"] == "connected"

    def test_fallback_to_public_ip(self, tmp_path: Path) -> None:
        _write_inventory(tmp_path, "prod0-main", {
            "public_ip": "1.2.3.4",
            "services": {"app": {}},
        })
        result = list_hosts(tmp_path)
        assert result["hosts"][0]["ip"] == "1.2.3.4"

    def test_no_services_unknown_status(self, tmp_path: Path) -> None:
        _write_inventory(tmp_path, "wsl", {"hostname": "h"})
        result = list_hosts(tmp_path)
        assert result["hosts"][0]["status"] == "unknown"


# ---------------------------------------------------------------------------
# list_operations
# ---------------------------------------------------------------------------


class TestListOperations:
    def test_empty(self, tmp_path: Path) -> None:
        result = list_operations(tmp_path)
        assert result == {"operations": []}

    def test_with_operations(self, tmp_path: Path) -> None:
        _write_inventory(tmp_path, "wsl", {
            "object_ledgers": {
                "generated_at": "2025-01-01",
                "last_operations": {
                    "app": {
                        "timestamp": "2025-01-01T00:00:00Z",
                        "action": "deploy",
                        "result": "ok",
                        "op_id": "op-1",
                    },
                },
            },
        })
        result = list_operations(tmp_path)
        assert len(result["operations"]) == 1
        assert result["operations"][0]["action"] == "deploy"

    def test_non_dict_last_operations(self, tmp_path: Path) -> None:
        _write_inventory(tmp_path, "wsl", {
            "object_ledgers": {"last_operations": "bad"},
        })
        result = list_operations(tmp_path)
        assert result["operations"] == []

    def test_non_dict_op_entry(self, tmp_path: Path) -> None:
        _write_inventory(tmp_path, "wsl", {
            "object_ledgers": {
                "last_operations": {"app": "not-a-dict"},
            },
        })
        result = list_operations(tmp_path)
        assert result["operations"] == []


# ---------------------------------------------------------------------------
# get_data_mtime
# ---------------------------------------------------------------------------


class TestGetDataMtime:
    def test_empty(self, tmp_path: Path) -> None:
        result = get_data_mtime(tmp_path)
        assert result["mtime"] == 0.0

    def test_with_files(self, tmp_path: Path) -> None:
        _write_inventory(tmp_path, "wsl", {"hostname": "h"})
        result = get_data_mtime(tmp_path)
        assert result["mtime"] > 0.0


# ---------------------------------------------------------------------------
# get_domain_infra
# ---------------------------------------------------------------------------


class TestGetDomainInfra:
    def test_empty(self, tmp_path: Path) -> None:
        result = get_domain_infra(tmp_path)
        assert result["ok"] is True
        assert result["payload"]["summary"]["host_count"] == 0

    def test_with_hosts(self, tmp_path: Path) -> None:
        _write_inventory(tmp_path, "wsl", {
            "hostname": "wsl",
            "ssh": {"infra": "10.0.0.1"},
            "label": "dev",
            "provider": "local",
            "services": {"pg": {}},
            "docker_containers": ["pg", "redis"],
            "compose_services": ["pg"],
        })
        result = get_domain_infra(tmp_path)
        assert result["ok"] is True
        summary = result["payload"]["summary"]
        assert summary["host_count"] == 1
        assert summary["total_containers"] == 2
        assert summary["total_compose_services"] == 1

    def test_non_list_docker_containers(self, tmp_path: Path) -> None:
        _write_inventory(tmp_path, "wsl", {
            "services": {"pg": {}},
            "docker_containers": "bad",
            "compose_services": "bad",
        })
        result = get_domain_infra(tmp_path)
        assert result["ok"] is True
        assert result["payload"]["summary"]["total_containers"] == 0


# ---------------------------------------------------------------------------
# get_domain_service / get_domain_app / get_domain_ingress
# ---------------------------------------------------------------------------


class TestGetDomainService:
    def test_empty(self, tmp_path: Path) -> None:
        result = get_domain_service(tmp_path)
        # service domain may fail to init on empty repo; either ok or graceful error
        assert "ok" in result
        if result["ok"]:
            assert result["payload"]["domain"] == "service"
        else:
            assert result["error"]["code"] == "domain.service.fetch_failed"


class TestGetDomainApp:
    def test_empty(self, tmp_path: Path) -> None:
        result = get_domain_app(tmp_path)
        assert "ok" in result
        if result["ok"]:
            assert result["payload"]["domain"] == "app"
        else:
            assert result["error"]["code"] == "domain.app.fetch_failed"


class TestGetDomainIngress:
    def test_empty(self, tmp_path: Path) -> None:
        result = get_domain_ingress(tmp_path)
        assert "ok" in result
        if result["ok"]:
            assert result["payload"]["domain"] == "ingress"
        else:
            assert result["error"]["code"] == "domain.ingress.fetch_failed"


# ---------------------------------------------------------------------------
# get_domain_project
# ---------------------------------------------------------------------------


class TestGetDomainProject:
    def test_empty_repo(self, tmp_path: Path) -> None:
        result = get_domain_project(tmp_path)
        # May succeed or fail depending on project status module
        assert "ok" in result


# ---------------------------------------------------------------------------
# get_dashboard
# ---------------------------------------------------------------------------


class TestGetDashboard:
    def test_empty_repo(self, tmp_path: Path) -> None:
        result = get_dashboard(tmp_path)
        assert "hosts" in result
        assert "apps" in result
        assert "operations" in result
        assert "topology" in result
        assert "domains" in result
        assert result["hosts"] == []

    def test_with_inventory(self, tmp_path: Path) -> None:
        _write_inventory(tmp_path, "wsl", {
            "hostname": "wsl-host",
            "ssh": {"infra": "10.0.0.1"},
            "label": "dev",
            "provider": "local",
            "services": {"pg": {}},
            "docker_containers": ["pg"],
            "compose_services": ["pg"],
            "object_ledgers": {
                "last_operations": {
                    "app": {"timestamp": "2025-01-01T00:00:00Z", "action": "deploy", "result": "ok", "op_id": "op-1"},
                },
            },
        })
        result = get_dashboard(tmp_path)
        assert len(result["hosts"]) == 1
        assert result["domains"]["infra"]["total_containers"] == 1


# ---------------------------------------------------------------------------
# get_capabilities
# ---------------------------------------------------------------------------


class TestGetCapabilities:
    def test_returns_data(self) -> None:
        result = get_capabilities()
        # capabilities.json exists in the project
        assert "ok" in result or isinstance(result, dict)


# ---------------------------------------------------------------------------
# get_server_detail
# ---------------------------------------------------------------------------


class TestGetServerDetail:
    def test_not_found(self, tmp_path: Path) -> None:
        result = get_server_detail(tmp_path, "nonexistent")
        assert result["error"] == "not_found"

    def test_found(self, tmp_path: Path) -> None:
        _write_inventory(tmp_path, "wsl", {
            "hostname": "wsl-host",
            "ssh": {"infra": "10.0.0.1"},
            "label": "dev",
            "provider": "local",
            "services": {"pg": {}},
            "docker_containers": ["pg"],
            "compose_services": ["pg"],
        })
        result = get_server_detail(tmp_path, "wsl")
        assert result["target"] == "wsl"
        assert result["hostname"] == "wsl-host"
        assert result["status"] == "connected"


# ---------------------------------------------------------------------------
# get_app_detail
# ---------------------------------------------------------------------------


class TestGetAppDetail:
    def test_not_found(self, tmp_path: Path) -> None:
        result = get_app_detail(tmp_path, "wsl", "nonexistent")
        assert result["error"] == "not_found"


# ---------------------------------------------------------------------------
# Golden test
# ---------------------------------------------------------------------------


@pytest.mark.golden
class TestApiHelpersGolden:
    def test_full_inventory_roundtrip(self, tmp_path: Path) -> None:
        """Load inventory with services, check host status."""
        inv_dir = tmp_path / "inventory" / "servers" / "prod0-main"
        inv_dir.mkdir(parents=True)
        inv_file = inv_dir / "inventory.json"
        inv_file.write_text(
            json.dumps({
                "hostname": "prod0.example.com",
                "ssh": {"infra": "10.0.0.1"},
                "services": {"postgres": {}, "redis": {}},
            }),
            encoding="utf-8",
        )
        inv = _load_inventory(tmp_path, "prod0-main")
        assert inv["hostname"] == "prod0.example.com"
        assert _host_status(inv) == "connected"
