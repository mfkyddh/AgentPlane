"""Unit tests for agentplane.domain.app.object_handlers — expanded coverage.

Covers _canonical_ref, _object_payload, _inventory_entry, _summary_files,
_ledger_status, search_apps, get_app, refresh_app_ledger, discover_installed_apps.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agentplane.domain.app.models import AppCatalogEntry, AppObject
from agentplane.domain.app.object_handlers import (
    _canonical_ref,
    _contract_payload,
    _inventory_entry,
    _ledger_status,
    _object_payload,
    _resolved_summary_path,
    _summary_files,
    discover_installed_apps,
    get_app,
    refresh_app_ledger,
    search_apps,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_app_object(
    tmp_path: Path,
    *,
    app: str = "sub2api",
    target: str = "prod0-main",
    contract_content: str = "{}",
) -> AppObject:
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    contract = repo_root / "deploy" / "agentplane" / "contract.yaml"
    contract.parent.mkdir(parents=True, exist_ok=True)
    contract.write_text(contract_content, encoding="utf-8")
    return AppObject(
        app=app,
        target=target,
        repo_name="example",
        repo_root=repo_root.resolve(),
        service_key=app,
        contract_file=contract,
    )


def _write_catalog(repo_root: Path, entries: list[dict]) -> None:
    catalog_file = repo_root / "inventory" / "apps" / "catalog.json"
    catalog_file.parent.mkdir(parents=True, exist_ok=True)
    catalog_file.write_text(json.dumps({"apps": entries}, indent=2), encoding="utf-8")


def _write_server_inventory(repo_root: Path, target: str, payload: dict) -> None:
    inv_file = repo_root / "inventory" / "servers" / target / "inventory.json"
    inv_file.parent.mkdir(parents=True, exist_ok=True)
    inv_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# _canonical_ref
# ---------------------------------------------------------------------------


class TestCanonicalRef:
    def test_returns_formatted_ref(self, tmp_path: Path) -> None:
        obj = _make_app_object(tmp_path, app="myapp", target="wsl")
        assert _canonical_ref(obj) == "apps/myapp/contracts/wsl"


# ---------------------------------------------------------------------------
# _object_payload
# ---------------------------------------------------------------------------


class TestObjectPayload:
    def test_basic_fields(self, tmp_path: Path) -> None:
        obj = _make_app_object(tmp_path)
        entry = {"control_plane": "cp-url", "public_url": "https://example.com"}
        result = _object_payload(obj, entry, include_resolved_path=False)
        assert result["app"] == "sub2api"
        assert result["target"] == "prod0-main"
        assert result["control_plane"] == "cp-url"
        assert result["public_url"] == "https://example.com"
        assert "resolved_path" not in result
        assert "contract_file" not in result

    def test_includes_resolved_path_when_requested(self, tmp_path: Path) -> None:
        obj = _make_app_object(tmp_path)
        result = _object_payload(obj, {}, include_resolved_path=True)
        assert "resolved_path" in result
        assert "contract_file" in result

    def test_missing_entry_keys_default_to_empty(self, tmp_path: Path) -> None:
        obj = _make_app_object(tmp_path)
        result = _object_payload(obj, {}, include_resolved_path=False)
        assert result["control_plane"] == ""
        assert result["public_url"] == ""


# ---------------------------------------------------------------------------
# _inventory_entry
# ---------------------------------------------------------------------------


class TestInventoryEntry:
    def test_returns_service_entry(self, tmp_path: Path) -> None:
        _write_server_inventory(tmp_path, "prod0-main", {
            "services": {"sub2api": {"control_plane": "docker"}}
        })
        result = _inventory_entry(tmp_path, "prod0-main", "sub2api")
        assert result == {"control_plane": "docker"}

    def test_empty_when_no_services(self, tmp_path: Path) -> None:
        _write_server_inventory(tmp_path, "prod0-main", {})
        result = _inventory_entry(tmp_path, "prod0-main", "sub2api")
        assert result == {}

    def test_empty_when_services_not_dict(self, tmp_path: Path) -> None:
        _write_server_inventory(tmp_path, "prod0-main", {"services": "bad"})
        result = _inventory_entry(tmp_path, "prod0-main", "sub2api")
        assert result == {}

    def test_empty_when_entry_not_dict(self, tmp_path: Path) -> None:
        _write_server_inventory(tmp_path, "prod0-main", {"services": {"sub2api": "bad"}})
        result = _inventory_entry(tmp_path, "prod0-main", "sub2api")
        assert result == {}

    def test_empty_when_no_inventory_file(self, tmp_path: Path) -> None:
        result = _inventory_entry(tmp_path, "prod0-main", "sub2api")
        assert result == {}


# ---------------------------------------------------------------------------
# _summary_files
# ---------------------------------------------------------------------------


class TestSummaryFiles:
    def test_returns_empty_when_no_docs(self, tmp_path: Path) -> None:
        obj = _make_app_object(tmp_path, contract_content="app: test\n")
        assert _summary_files(obj) == []

    def test_app_summary_files_per_target(self, tmp_path: Path) -> None:
        obj = _make_app_object(
            tmp_path,
            contract_content=json.dumps({"docs": {"app_summary_files": {"prod0-main": "docs/summary.md"}}}),
        )
        (obj.repo_root / "docs").mkdir(parents=True, exist_ok=True)
        (obj.repo_root / "docs" / "summary.md").write_text("# summary", encoding="utf-8")
        result = _summary_files(obj)
        assert len(result) == 1
        assert result[0]["source"] == "docs.app_summary_files"
        assert result[0]["exists"] is True

    def test_app_summary_files_missing_file(self, tmp_path: Path) -> None:
        obj = _make_app_object(
            tmp_path,
            contract_content=json.dumps({"docs": {"app_summary_files": {"prod0-main": "docs/missing.md"}}}),
        )
        result = _summary_files(obj)
        assert len(result) == 1
        assert result[0]["exists"] is False

    def test_app_summary_file_generic(self, tmp_path: Path) -> None:
        obj = _make_app_object(
            tmp_path,
            contract_content=json.dumps({"docs": {"app_summary_file": "docs/deploy.md"}}),
        )
        (obj.repo_root / "docs").mkdir(parents=True, exist_ok=True)
        (obj.repo_root / "docs" / "deploy.md").write_text("# deploy", encoding="utf-8")
        result = _summary_files(obj)
        assert len(result) == 1
        assert result[0]["source"] == "docs.app_summary_file"

    def test_app_summary_file_path_escape(self, tmp_path: Path) -> None:
        obj = _make_app_object(
            tmp_path,
            contract_content=json.dumps({"docs": {"app_summary_file": "../escape.md"}}),
        )
        result = _summary_files(obj)
        assert result == []

    def test_wrong_target_in_per_target_map(self, tmp_path: Path) -> None:
        obj = _make_app_object(
            tmp_path,
            target="wsl",
            contract_content=json.dumps({"docs": {"app_summary_files": {"prod0-main": "docs/summary.md"}}}),
        )
        result = _summary_files(obj)
        assert result == []


# ---------------------------------------------------------------------------
# _ledger_status
# ---------------------------------------------------------------------------


class TestLedgerStatus:
    def test_all_present(self, tmp_path: Path) -> None:
        _write_server_inventory(tmp_path, "prod0-main", {
            "object_ledgers": {"ledgers": {"apps": "inventory/servers/prod0-main/ledgers/apps.json"}}
        })
        ledger_dir = tmp_path / "inventory" / "servers" / "prod0-main" / "ledgers"
        ledger_dir.mkdir(parents=True, exist_ok=True)
        (ledger_dir / "apps.json").write_text("{}", encoding="utf-8")
        (ledger_dir / "apps.md").write_text("# apps", encoding="utf-8")
        result = _ledger_status(tmp_path, "prod0-main")
        assert result["json_exists"] is True
        assert result["markdown_exists"] is True
        assert result["inventory_pointer_ok"] is True

    def test_missing_files(self, tmp_path: Path) -> None:
        result = _ledger_status(tmp_path, "prod0-main")
        assert result["json_exists"] is False
        assert result["markdown_exists"] is False
        assert result["inventory_pointer_ok"] is False

    def test_pointer_mismatch(self, tmp_path: Path) -> None:
        _write_server_inventory(tmp_path, "prod0-main", {
            "object_ledgers": {"ledgers": {"apps": "wrong/path.json"}}
        })
        result = _ledger_status(tmp_path, "prod0-main")
        assert result["inventory_pointer_ok"] is False


# ---------------------------------------------------------------------------
# search_apps
# ---------------------------------------------------------------------------


class TestSearchApps:
    def test_search_with_specific_app(self, tmp_path: Path) -> None:
        _write_catalog(tmp_path, [{
            "app": "sub2api",
            "repo_name": "example",
            "repo_root": str(tmp_path),
            "service_key": "sub2api",
            "contracts": {"prod0-main": "deploy/agentplane/contract.yaml"},
        }])
        contract = tmp_path / "deploy" / "agentplane" / "contract.yaml"
        contract.parent.mkdir(parents=True, exist_ok=True)
        contract.write_text("app: sub2api\n", encoding="utf-8")
        _write_server_inventory(tmp_path, "prod0-main", {"services": {}})

        with patch("agentplane.domain.app.object_handlers.resolve_app_contract_source") as mock_resolve:
            entry = AppCatalogEntry(
                app="sub2api", repo_name="example", repo_root=tmp_path.resolve(),
                service_key="sub2api", contracts={"prod0-main": "deploy/agentplane/contract.yaml"},
            )
            mock_resolve.return_value = (entry, contract)
            result = search_apps(tmp_path, "prod0-main", app="sub2api")

        assert result["target"] == "prod0-main"
        assert len(result["items"]) == 1
        assert result["items"][0]["app"] == "sub2api"

    def test_search_all_apps_from_catalog(self, tmp_path: Path) -> None:
        catalog_entries = [
            AppCatalogEntry(
                app="app1", repo_name="r1", repo_root=tmp_path.resolve(),
                service_key="app1", contracts={"prod0-main": "c1.yaml"},
            ),
            AppCatalogEntry(
                app="app2", repo_name="r2", repo_root=tmp_path.resolve(),
                service_key="app2", contracts={"wsl": "c2.yaml"},
            ),
        ]
        with patch("agentplane.domain.app.object_handlers.load_app_catalog", return_value=catalog_entries), \
             patch("agentplane.domain.app.object_handlers._object_from_entry") as mock_obj, \
             patch("agentplane.domain.app.object_handlers._inventory_entry", return_value={}):
            mock_obj.return_value = _make_app_object(tmp_path)
            result = search_apps(tmp_path, "prod0-main")

        # Only app1 has contracts for prod0-main
        assert result["target"] == "prod0-main"

    def test_search_empty_catalog(self, tmp_path: Path) -> None:
        with patch("agentplane.domain.app.object_handlers.load_app_catalog", side_effect=FileNotFoundError):
            result = search_apps(tmp_path, "prod0-main")
        assert result["items"] == []


# ---------------------------------------------------------------------------
# get_app
# ---------------------------------------------------------------------------


class TestGetApp:
    def test_returns_full_app_info(self, tmp_path: Path) -> None:
        contract = tmp_path / "deploy" / "agentplane" / "contract.yaml"
        contract.parent.mkdir(parents=True, exist_ok=True)
        contract.write_text(json.dumps({
            "docs": {"app_summary_file": "docs/summary.md"},
        }), encoding="utf-8")
        (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
        (tmp_path / "docs" / "summary.md").write_text("# s", encoding="utf-8")

        _write_server_inventory(tmp_path, "prod0-main", {
            "object_ledgers": {"ledgers": {"apps": "inventory/servers/prod0-main/ledgers/apps.json"}}
        })
        ledger_dir = tmp_path / "inventory" / "servers" / "prod0-main" / "ledgers"
        ledger_dir.mkdir(parents=True, exist_ok=True)
        (ledger_dir / "apps.json").write_text("{}", encoding="utf-8")
        (ledger_dir / "apps.md").write_text("# apps", encoding="utf-8")

        with patch("agentplane.domain.app.object_handlers.resolve_app_contract_source") as mock_resolve:
            entry = AppCatalogEntry(
                app="sub2api", repo_name="example", repo_root=tmp_path.resolve(),
                service_key="sub2api", contracts={"prod0-main": "deploy/agentplane/contract.yaml"},
            )
            mock_resolve.return_value = (entry, contract)
            result = get_app(tmp_path, "prod0-main", "sub2api")

        assert "app" in result
        assert "inventory_entry" in result
        assert "summary_files" in result
        assert "ledger_status" in result


# ---------------------------------------------------------------------------
# refresh_app_ledger
# ---------------------------------------------------------------------------


class TestRefreshAppLedger:
    def test_write_mode_creates_files(self, tmp_path: Path) -> None:
        with patch("agentplane.domain.app.object_handlers.search_apps") as mock_search:
            mock_search.return_value = {"target": "prod0-main", "items": [
                {"app": "sub2api", "canonical_ref": "apps/sub2api/contracts/prod0-main"},
            ]}
            result = refresh_app_ledger(tmp_path, "prod0-main", write=True)

        assert result["target"] == "prod0-main"
        assert result["count"] == 1
        json_path = Path(result["json_file"])
        assert json_path.exists()
        md_path = Path(result["markdown_file"])
        assert md_path.exists()
        md_content = md_path.read_text(encoding="utf-8")
        assert "sub2api" in md_content

    def test_dry_run_no_files_written(self, tmp_path: Path) -> None:
        with patch("agentplane.domain.app.object_handlers.search_apps") as mock_search:
            mock_search.return_value = {"target": "prod0-main", "items": []}
            result = refresh_app_ledger(tmp_path, "prod0-main", write=False)

        assert result["count"] == 0
        json_path = Path(result["json_file"])
        assert not json_path.exists()

    def test_empty_items_markdown(self, tmp_path: Path) -> None:
        with patch("agentplane.domain.app.object_handlers.search_apps") as mock_search:
            mock_search.return_value = {"target": "prod0-main", "items": []}
            result = refresh_app_ledger(tmp_path, "prod0-main", write=True)

        md_path = Path(result["markdown_file"])
        md_content = md_path.read_text(encoding="utf-8")
        assert "no active app catalog object" in md_content


# ---------------------------------------------------------------------------
# discover_installed_apps
# ---------------------------------------------------------------------------


class TestDiscoverInstalledApps:
    def test_classifies_managed_and_unmanaged(self, tmp_path: Path) -> None:
        _write_catalog(tmp_path, [{
            "app": "sub2api", "repo_name": "r", "repo_root": str(tmp_path),
            "service_key": "sub2api", "contracts": {"prod0-main": "c.yaml"},
        }])
        mock_provider = MagicMock()
        mock_provider.get_target.return_value = object()
        mock_provider.search_installed_apps.return_value = {
            "items": [
                {"id": 1, "name": "sub2api", "appKey": "sub2api", "status": "Running", "version": "1.0"},
                {"id": 2, "name": "redis", "appKey": "redis", "status": "Running", "version": "7.0"},
            ]
        }
        with patch("agentplane.domain.app.object_handlers.get_provider", return_value=mock_provider):
            result = discover_installed_apps(tmp_path, "prod0-main")

        assert result["total_installed"] == 2
        assert result["managed_count"] == 1
        assert result["unmanaged_count"] == 1
        assert result["unmanaged"][0]["app_key"] == "redis"

    def test_include_managed_flag(self, tmp_path: Path) -> None:
        _write_catalog(tmp_path, [{
            "app": "sub2api", "repo_name": "r", "repo_root": str(tmp_path),
            "service_key": "sub2api", "contracts": {"prod0-main": "c.yaml"},
        }])
        mock_provider = MagicMock()
        mock_provider.get_target.return_value = object()
        mock_provider.search_installed_apps.return_value = {
            "items": [{"id": 1, "name": "sub2api", "appKey": "sub2api", "status": "Running"}]
        }
        with patch("agentplane.domain.app.object_handlers.get_provider", return_value=mock_provider):
            result = discover_installed_apps(tmp_path, "prod0-main", include_managed=True)

        assert "managed" in result
        assert len(result["managed"]) == 1

    def test_empty_installed_apps(self, tmp_path: Path) -> None:
        mock_provider = MagicMock()
        mock_provider.get_target.return_value = object()
        mock_provider.search_installed_apps.return_value = {"items": [], "total": 0}
        with patch("agentplane.domain.app.object_handlers.get_provider", return_value=mock_provider):
            result = discover_installed_apps(tmp_path, "prod0-main")

        assert result["total_installed"] == 0
        assert result["unmanaged"] == []

    def test_handles_non_list_items(self, tmp_path: Path) -> None:
        mock_provider = MagicMock()
        mock_provider.get_target.return_value = object()
        mock_provider.search_installed_apps.return_value = {"items": "bad"}
        with patch("agentplane.domain.app.object_handlers.get_provider", return_value=mock_provider):
            result = discover_installed_apps(tmp_path, "prod0-main")

        assert result["total_installed"] == 0

    def test_handles_non_dict_items_in_list(self, tmp_path: Path) -> None:
        mock_provider = MagicMock()
        mock_provider.get_target.return_value = object()
        mock_provider.search_installed_apps.return_value = {"items": ["bad", 123]}
        with patch("agentplane.domain.app.object_handlers.get_provider", return_value=mock_provider):
            result = discover_installed_apps(tmp_path, "prod0-main")

        # total_installed counts all raw items; non-dicts are skipped in managed/unmanaged
        assert result["total_installed"] == 2
        assert result["managed_count"] == 0
        assert result["unmanaged_count"] == 0

    def test_empty_catalog_file_not_found(self, tmp_path: Path) -> None:
        mock_provider = MagicMock()
        mock_provider.get_target.return_value = object()
        mock_provider.search_installed_apps.return_value = {
            "items": [{"id": 1, "name": "app", "appKey": "app", "status": "Running"}]
        }
        with patch("agentplane.domain.app.object_handlers.get_provider", return_value=mock_provider):
            result = discover_installed_apps(tmp_path, "prod0-main")

        assert result["unmanaged_count"] == 1
