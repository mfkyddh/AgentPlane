from __future__ import annotations

import importlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from agentplane.domain.app.models import AppCatalogEntry
from agentplane.domain.app.truth_lifecycle import offboard_catalog_entry, onboard_catalog_entry
from tests.support.app_object import REPO_ROOT, run_cli, write_inventory_with_app

pytestmark = pytest.mark.e2e


class AppObjectCliTests(unittest.TestCase):
    def test_app_catalog_module_exists_for_object_and_delivery_resolution(self) -> None:
        catalog = importlib.import_module("agentplane.domain.app.catalog")

        self.assertTrue(callable(getattr(catalog, "resolve_app_contract", None)))

    def test_app_catalog_normalizes_wsl_repo_root_for_windows_host(self) -> None:
        catalog = importlib.import_module("agentplane.domain.app.catalog")

        with patch.object(catalog.os, "name", "nt"):
            normalized = catalog._normalize_repo_root_for_current_host("/work/sub2api")

        self.assertEqual(r"\\wsl.localhost\Ubuntu\work\sub2api", normalized)

    def test_app_object_search_returns_empty_items_when_catalog_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            server_root = root / "inventory" / "servers" / "prod0-main"
            server_root.mkdir(parents=True, exist_ok=True)
            (server_root / "inventory.json").write_text(
                json.dumps({"services": {}}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            payload = run_cli("app", "object", "search", "--target", "prod0-main", "--repo-root", str(root))

            self.assertEqual(0, payload.returncode, msg=payload.stderr)
            payload_json = json.loads(payload.stdout)
            self.assertEqual([], payload_json["payload"]["items"])

    def test_app_object_search_emits_namespaced_action(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory_with_app(root)

            payload = run_cli("app", "object", "search", "--target", "prod0-main", "--repo-root", str(root))

            self.assertEqual(0, payload.returncode, msg=payload.stderr)
            payload_json = json.loads(payload.stdout)
            self.assertEqual("app", payload_json["command"])
            self.assertEqual("object.search", payload_json["action"])
            self.assertEqual("prod0-main", payload_json["target"])
            self.assertIn("items", payload_json["payload"])
            self.assertEqual("sub2api", payload_json["payload"]["items"][0]["app"])
            self.assertEqual(
                "apps/sub2api/contracts/prod0-main",
                payload_json["payload"]["items"][0]["canonical_ref"],
            )
            self.assertEqual(
                str((root / "sub2api" / "deploy" / "agentplane" / "contract.yaml").resolve()),
                payload_json["payload"]["items"][0]["resolved_path"],
            )

    def test_app_object_get_returns_named_app_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory_with_app(root)

            payload = run_cli(
                "app",
                "object",
                "get",
                "--target",
                "prod0-main",
                "--app",
                "sub2api",
                "--repo-root",
                str(root),
            )

            self.assertEqual(0, payload.returncode, msg=payload.stderr)
            payload_json = json.loads(payload.stdout)
            self.assertEqual("app", payload_json["command"])
            self.assertEqual("object.get", payload_json["action"])
            self.assertIn("app", payload_json["payload"])
            self.assertEqual("sub2api", payload_json["payload"]["app"]["app"])
            self.assertEqual("compose", payload_json["payload"]["app"]["control_plane"])
            self.assertEqual("apps/sub2api/contracts/prod0-main", payload_json["payload"]["app"]["canonical_ref"])
            self.assertEqual(
                str((root / "sub2api" / "deploy" / "agentplane" / "contract.yaml").resolve()),
                payload_json["payload"]["app"]["resolved_path"],
            )

    def test_app_object_get_returns_summary_files_and_ledger_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory_with_app(root)
            app_root = root / "sub2api"
            (app_root / "deploy" / "agentplane").mkdir(parents=True, exist_ok=True)
            (app_root / "deploy" / "agentplane" / "contract.yaml").write_text(
                json.dumps({"docs": {"app_summary_files": {"prod0-main": "docs/AGENTPLANE_DEPLOYMENT.prod0-main.md"}}}),
                encoding="utf-8",
            )
            summary_file = app_root / "docs" / "AGENTPLANE_DEPLOYMENT.prod0-main.md"
            summary_file.parent.mkdir(parents=True, exist_ok=True)
            summary_file.write_text("# summary\n", encoding="utf-8")

            payload = run_cli(
                "app",
                "object",
                "get",
                "--target",
                "prod0-main",
                "--app",
                "sub2api",
                "--repo-root",
                str(root),
            )

            self.assertEqual(0, payload.returncode, msg=payload.stderr)
            payload_json = json.loads(payload.stdout)
            self.assertEqual(
                [
                    {
                        "target": "prod0-main",
                        "path": str(summary_file),
                        "source": "docs.app_summary_files",
                        "exists": True,
                    }
                ],
                payload_json["payload"]["summary_files"],
            )
            self.assertEqual(
                {
                    "json_file": str(root / "inventory" / "servers" / "prod0-main" / "ledgers" / "apps.json"),
                    "markdown_file": str(root / "inventory" / "servers" / "prod0-main" / "ledgers" / "apps.md"),
                    "inventory_pointer": "",
                    "expected_pointer": "inventory/servers/prod0-main/ledgers/apps.json",
                    "json_exists": True,
                    "markdown_exists": False,
                    "inventory_pointer_ok": False,
                },
                payload_json["payload"]["ledger_status"],
            )

    def test_app_object_get_accepts_nested_inventory_ledger_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory_with_app(root)
            inventory_file = root / "inventory" / "servers" / "prod0-main" / "inventory.json"
            inventory_payload = json.loads(inventory_file.read_text(encoding="utf-8"))
            inventory_payload["object_ledgers"] = {
                "ledgers": {"apps": "inventory/servers/prod0-main/ledgers/apps.json"}
            }
            inventory_file.write_text(
                json.dumps(inventory_payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            payload = run_cli(
                "app",
                "object",
                "get",
                "--target",
                "prod0-main",
                "--app",
                "sub2api",
                "--repo-root",
                str(root),
            )

            self.assertEqual(0, payload.returncode, msg=payload.stderr)
            payload_json = json.loads(payload.stdout)
            self.assertTrue(payload_json["payload"]["ledger_status"]["inventory_pointer_ok"])
            self.assertEqual(
                "inventory/servers/prod0-main/ledgers/apps.json",
                payload_json["payload"]["ledger_status"]["inventory_pointer"],
            )
            self.assertEqual(
                "inventory/servers/prod0-main/ledgers/apps.json",
                payload_json["payload"]["ledger_status"]["expected_pointer"],
            )

    def test_app_object_get_falls_back_to_single_summary_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory_with_app(root)
            app_root = root / "sub2api"
            (app_root / "deploy" / "agentplane").mkdir(parents=True, exist_ok=True)
            (app_root / "deploy" / "agentplane" / "contract.yaml").write_text(
                json.dumps({"docs": {"app_summary_file": "docs/AGENTPLANE_DEPLOYMENT.md"}}),
                encoding="utf-8",
            )
            summary_file = app_root / "docs" / "AGENTPLANE_DEPLOYMENT.md"
            summary_file.parent.mkdir(parents=True, exist_ok=True)
            summary_file.write_text("# summary fallback\n", encoding="utf-8")

            payload = run_cli(
                "app",
                "object",
                "get",
                "--target",
                "prod0-main",
                "--app",
                "sub2api",
                "--repo-root",
                str(root),
            )

            self.assertEqual(0, payload.returncode, msg=payload.stderr)
            payload_json = json.loads(payload.stdout)
            self.assertEqual(
                [
                    {
                        "target": "prod0-main",
                        "path": str(summary_file),
                        "source": "docs.app_summary_file",
                        "exists": True,
                    }
                ],
                payload_json["payload"]["summary_files"],
            )

    def test_app_object_get_prefers_target_specific_summary_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory_with_app(root)
            app_root = root / "sub2api"
            (app_root / "deploy" / "agentplane").mkdir(parents=True, exist_ok=True)
            (app_root / "deploy" / "agentplane" / "contract.yaml").write_text(
                json.dumps(
                    {
                        "docs": {
                            "app_summary_files": {"prod0-main": "docs/AGENTPLANE_DEPLOYMENT.prod0-main.md"},
                            "app_summary_file": "docs/AGENTPLANE_DEPLOYMENT.md",
                        }
                    }
                ),
                encoding="utf-8",
            )
            summary_file = app_root / "docs" / "AGENTPLANE_DEPLOYMENT.prod0-main.md"
            summary_file.parent.mkdir(parents=True, exist_ok=True)
            summary_file.write_text("# target specific summary\n", encoding="utf-8")
            fallback_file = app_root / "docs" / "AGENTPLANE_DEPLOYMENT.md"
            fallback_file.write_text("# fallback summary\n", encoding="utf-8")

            payload = run_cli(
                "app",
                "object",
                "get",
                "--target",
                "prod0-main",
                "--app",
                "sub2api",
                "--repo-root",
                str(root),
            )

            self.assertEqual(0, payload.returncode, msg=payload.stderr)
            payload_json = json.loads(payload.stdout)
            self.assertEqual(
                [
                    {
                        "target": "prod0-main",
                        "path": str(summary_file),
                        "source": "docs.app_summary_files",
                        "exists": True,
                    }
                ],
                payload_json["payload"]["summary_files"],
            )

    def test_app_object_get_tolerates_malformed_contract_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory_with_app(root)
            app_root = root / "sub2api"
            (app_root / "deploy" / "agentplane").mkdir(parents=True, exist_ok=True)
            (app_root / "deploy" / "agentplane" / "contract.yaml").write_text(
                "docs: [broken",
                encoding="utf-8",
            )

            payload = run_cli(
                "app",
                "object",
                "get",
                "--target",
                "prod0-main",
                "--app",
                "sub2api",
                "--repo-root",
                str(root),
            )

            self.assertEqual(0, payload.returncode, msg=payload.stderr)
            payload_json = json.loads(payload.stdout)
            self.assertEqual("sub2api", payload_json["payload"]["app"]["app"])
            self.assertEqual([], payload_json["payload"]["summary_files"])
            self.assertIn("ledger_status", payload_json["payload"])

    def test_app_object_get_ignores_summary_file_outside_repo_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory_with_app(root)
            app_root = root / "sub2api"
            outside_file = root / "outside-summary.md"
            outside_file.write_text("# outside\n", encoding="utf-8")
            (app_root / "deploy" / "agentplane").mkdir(parents=True, exist_ok=True)
            (app_root / "deploy" / "agentplane" / "contract.yaml").write_text(
                json.dumps(
                    {
                        "docs": {
                            "app_summary_files": {"prod0-main": "../outside-summary.md"},
                        }
                    }
                ),
                encoding="utf-8",
            )

            payload = run_cli(
                "app",
                "object",
                "get",
                "--target",
                "prod0-main",
                "--app",
                "sub2api",
                "--repo-root",
                str(root),
            )

            self.assertEqual(0, payload.returncode, msg=payload.stderr)
            payload_json = json.loads(payload.stdout)
            self.assertEqual([], payload_json["payload"]["summary_files"])

    def test_app_object_get_falls_back_when_target_specific_summary_path_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory_with_app(root)
            app_root = root / "sub2api"
            (app_root / "deploy" / "agentplane").mkdir(parents=True, exist_ok=True)
            (app_root / "deploy" / "agentplane" / "contract.yaml").write_text(
                json.dumps(
                    {
                        "docs": {
                            "app_summary_files": {"prod0-main": "../outside-summary.md"},
                            "app_summary_file": "docs/AGENTPLANE_DEPLOYMENT.md",
                        }
                    }
                ),
                encoding="utf-8",
            )
            fallback_file = app_root / "docs" / "AGENTPLANE_DEPLOYMENT.md"
            fallback_file.parent.mkdir(parents=True, exist_ok=True)
            fallback_file.write_text("# fallback summary\n", encoding="utf-8")

            payload = run_cli(
                "app",
                "object",
                "get",
                "--target",
                "prod0-main",
                "--app",
                "sub2api",
                "--repo-root",
                str(root),
            )

            self.assertEqual(0, payload.returncode, msg=payload.stderr)
            payload_json = json.loads(payload.stdout)
            self.assertEqual(
                [
                    {
                        "target": "prod0-main",
                        "path": str(fallback_file),
                        "source": "docs.app_summary_file",
                        "exists": True,
                    }
                ],
                payload_json["payload"]["summary_files"],
            )

    def test_app_object_get_tolerates_invalid_utf8_contract_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory_with_app(root)
            app_root = root / "sub2api"
            (app_root / "deploy" / "agentplane").mkdir(parents=True, exist_ok=True)
            (app_root / "deploy" / "agentplane" / "contract.yaml").write_bytes(b"\xff\xfe\xfa")

            payload = run_cli(
                "app",
                "object",
                "get",
                "--target",
                "prod0-main",
                "--app",
                "sub2api",
                "--repo-root",
                str(root),
            )

            self.assertEqual(0, payload.returncode, msg=payload.stderr)
            payload_json = json.loads(payload.stdout)
            self.assertEqual([], payload_json["payload"]["summary_files"])

    def test_app_object_verify_fails_when_summary_file_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory_with_app(root)
            app_root = root / "sub2api"
            (app_root / "deploy" / "agentplane").mkdir(parents=True, exist_ok=True)
            (app_root / "deploy" / "agentplane" / "contract.yaml").write_text(
                json.dumps({"docs": {"app_summary_files": {"prod0-main": "docs/AGENTPLANE_DEPLOYMENT.prod0-main.md"}}}),
                encoding="utf-8",
            )
            inventory_file = root / "inventory" / "servers" / "prod0-main" / "inventory.json"
            inventory_payload = json.loads(inventory_file.read_text(encoding="utf-8"))
            inventory_payload["object_ledgers"] = {
                "ledgers": {"apps": "inventory/servers/prod0-main/ledgers/apps.json"}
            }
            inventory_file.write_text(
                json.dumps(inventory_payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            ledger_root = root / "inventory" / "servers" / "prod0-main" / "ledgers"
            (ledger_root / "apps.md").write_text("# apps\n", encoding="utf-8")

            payload = run_cli(
                "app",
                "object",
                "verify",
                "--target",
                "prod0-main",
                "--app",
                "sub2api",
                "--repo-root",
                str(root),
            )

            self.assertEqual(1, payload.returncode, msg=payload.stderr)
            payload_json = json.loads(payload.stdout)
            self.assertIn("summary_files", payload_json["payload"]["failures"])
            self.assertFalse(payload_json["payload"]["checks"]["summary_files"]["ok"])
            self.assertTrue(payload_json["payload"]["checks"]["ledger_status"]["ok"])

    def test_app_object_verify_fails_when_inventory_pointer_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory_with_app(root)
            app_root = root / "sub2api"
            (app_root / "deploy" / "agentplane").mkdir(parents=True, exist_ok=True)
            (app_root / "deploy" / "agentplane" / "contract.yaml").write_text(
                json.dumps({"docs": {"app_summary_files": {"prod0-main": "docs/AGENTPLANE_DEPLOYMENT.prod0-main.md"}}}),
                encoding="utf-8",
            )
            summary_file = app_root / "docs" / "AGENTPLANE_DEPLOYMENT.prod0-main.md"
            summary_file.parent.mkdir(parents=True, exist_ok=True)
            summary_file.write_text("# summary\n", encoding="utf-8")
            ledger_root = root / "inventory" / "servers" / "prod0-main" / "ledgers"
            (ledger_root / "apps.md").write_text("# apps\n", encoding="utf-8")

            payload = run_cli(
                "app",
                "object",
                "verify",
                "--target",
                "prod0-main",
                "--app",
                "sub2api",
                "--repo-root",
                str(root),
            )

            self.assertEqual(1, payload.returncode, msg=payload.stderr)
            payload_json = json.loads(payload.stdout)
            self.assertIn("ledger_status", payload_json["payload"]["failures"])
            self.assertFalse(payload_json["payload"]["checks"]["ledger_status"]["ok"])
            self.assertTrue(payload_json["payload"]["checks"]["summary_files"]["ok"])

    def test_app_object_verify_reports_false_when_projection_cannot_be_trusted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory_with_app(root)

            payload = run_cli(
                "app",
                "object",
                "verify",
                "--target",
                "prod0-main",
                "--app",
                "sub2api",
                "--repo-root",
                str(root),
            )

            self.assertEqual(1, payload.returncode, msg=payload.stderr)
            payload_json = json.loads(payload.stdout)
            self.assertEqual("app", payload_json["command"])
            self.assertEqual("object.verify", payload_json["action"])
            self.assertIn("ok", payload_json["payload"])
            self.assertIn("checks", payload_json["payload"])
            self.assertIn("failures", payload_json["payload"])
            self.assertFalse(payload_json["payload"]["ok"])

    def test_app_object_refresh_ledger_writes_inventory_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory_with_app(root)
            app_root = root / "sub2api"
            (app_root / "deploy" / "agentplane").mkdir(parents=True, exist_ok=True)
            (app_root / "deploy" / "agentplane" / "contract.yaml").write_text("{}", encoding="utf-8")

            payload = run_cli(
                "app",
                "object",
                "refresh-ledger",
                "--target",
                "prod0-main",
                "--repo-root",
                str(root),
                "--write",
            )

            self.assertEqual(0, payload.returncode, msg=payload.stderr)
            payload_json = json.loads(payload.stdout)
            self.assertEqual(
                "inventory/servers/prod0-main/ledgers/apps.json",
                payload_json["payload"]["inventory_pointer"],
            )
            inventory = json.loads(
                (root / "inventory" / "servers" / "prod0-main" / "inventory.json").read_text(encoding="utf-8")
            )
            ledger = json.loads(
                (root / "inventory" / "servers" / "prod0-main" / "ledgers" / "apps.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                "inventory/servers/prod0-main/ledgers/apps.json",
                inventory["object_ledgers"]["ledgers"]["apps"],
            )
            self.assertEqual("apps/sub2api/contracts/prod0-main", ledger["items"][0]["canonical_ref"])
            self.assertNotIn("resolved_path", ledger["items"][0])
            self.assertNotIn("contract_file", ledger["items"][0])

    def test_app_object_discovers_unmanaged_installed_apps(self) -> None:
        from agentplane.cli.apps import handle_app_command

        fake_installed = {
            "items": [
                {"id": 3, "name": "openresty", "appKey": "openresty", "status": "Running", "version": "1.27.1"},
                {"id": 5, "name": "redis", "appKey": "redis", "status": "Running", "version": "7.2"},
                {"id": 7, "name": "my-custom-app", "appKey": "custom", "status": "Running", "version": "1.0"},
            ],
            "total": 3,
        }
        fake_executor = object()
        fake_gateway = SimpleNamespace(
            onepanel_target_executor=lambda target: fake_executor,
            search_onepanel_installed_apps=lambda executor, name="": fake_installed,
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory_with_app(root)

            with patch("agentplane.domain.app.object_handlers.default_provider_gateway", return_value=fake_gateway):
                args = SimpleNamespace(
                    app_surface="object",
                    app_object_action="discover",
                    target="prod0-main",
                    repo_root=str(root),
                    name="",
                    include_managed=False,
                )
                payload = handle_app_command(args)

            self.assertEqual("app", payload["command"])
            self.assertEqual("object.discover", payload["action"])
            self.assertEqual(3, payload["payload"]["total_installed"])
            self.assertEqual(0, payload["payload"]["managed_count"])
            self.assertEqual(3, payload["payload"]["unmanaged_count"])
            unmanaged_keys = [item["app_key"] for item in payload["payload"]["unmanaged"]]
            self.assertIn("openresty", unmanaged_keys)
            self.assertIn("redis", unmanaged_keys)
            self.assertIn("custom", unmanaged_keys)

    def test_app_object_discover_classifies_catalog_apps_as_managed(self) -> None:
        from agentplane.cli.apps import handle_app_command

        fake_installed = {
            "items": [
                {"id": 3, "name": "openresty", "appKey": "openresty", "status": "Running"},
                {"id": 5, "name": "sub2api", "appKey": "sub2api", "status": "Running"},
            ],
            "total": 2,
        }
        fake_executor = object()
        fake_gateway = SimpleNamespace(
            onepanel_target_executor=lambda target: fake_executor,
            search_onepanel_installed_apps=lambda executor, name="": fake_installed,
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory_with_app(root)

            with patch("agentplane.domain.app.object_handlers.default_provider_gateway", return_value=fake_gateway):
                args = SimpleNamespace(
                    app_surface="object",
                    app_object_action="discover",
                    target="prod0-main",
                    repo_root=str(root),
                    name="",
                    include_managed=True,
                )
                payload = handle_app_command(args)

            self.assertEqual("app", payload["command"])
            self.assertEqual("object.discover", payload["action"])
            self.assertEqual(2, payload["payload"]["total_installed"])
            self.assertEqual(1, payload["payload"]["managed_count"])
            self.assertEqual(1, payload["payload"]["unmanaged_count"])
            managed_keys = [item["app_key"] for item in payload["payload"]["managed"]]
            self.assertIn("sub2api", managed_keys)
            unmanaged_keys = [item["app_key"] for item in payload["payload"]["unmanaged"]]
            self.assertIn("openresty", unmanaged_keys)

    def test_app_object_discover_handles_empty_installed_apps(self) -> None:
        from agentplane.cli.apps import handle_app_command

        fake_executor = object()
        fake_gateway = SimpleNamespace(
            onepanel_target_executor=lambda target: fake_executor,
            search_onepanel_installed_apps=lambda executor, name="": {"items": [], "total": 0},
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory_with_app(root)

            with patch("agentplane.domain.app.object_handlers.default_provider_gateway", return_value=fake_gateway):
                args = SimpleNamespace(
                    app_surface="object",
                    app_object_action="discover",
                    target="prod0-main",
                    repo_root=str(root),
                    name="",
                    include_managed=False,
                )
                payload = handle_app_command(args)

            self.assertEqual("app", payload["command"])
            self.assertEqual("object.discover", payload["action"])
            self.assertEqual(0, payload["payload"]["total_installed"])
            self.assertEqual(0, payload["payload"]["unmanaged_count"])
            self.assertEqual([], payload["payload"]["unmanaged"])


# ======================================================================
# From: test_app_object_repo_root_cli.py
# ======================================================================


