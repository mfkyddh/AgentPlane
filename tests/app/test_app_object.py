from __future__ import annotations

import importlib
import json
import tempfile
import unittest
from pathlib import Path
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


# ======================================================================
# From: test_app_object_repo_root_cli.py
# ======================================================================


class AppObjectRepoRootCliTests(unittest.TestCase):
    def test_app_object_search_prefers_explicit_app_repo_root_over_catalog_repo_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            repo_root = tmp_root / "oplinux"
            canonical_root = tmp_root / "sub2api"
            worktree_root = tmp_root / "sub2api.worktree"
            repo_root.mkdir(parents=True, exist_ok=True)
            canonical_root.mkdir(parents=True, exist_ok=True)
            worktree_root.mkdir(parents=True, exist_ok=True)

            server_root = repo_root / "inventory" / "servers" / "prod0-main"
            server_root.mkdir(parents=True, exist_ok=True)
            (server_root / "inventory.json").write_text(
                json.dumps(
                    {
                        "services": {
                            "sub2api": {
                                "app": "sub2api",
                                "control_plane": "compose",
                                "public_url": "https://token.example.net:8443",
                            }
                        }
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            catalog_root = repo_root / "inventory" / "apps"
            catalog_root.mkdir(parents=True, exist_ok=True)
            (catalog_root / "catalog.json").write_text(
                json.dumps(
                    {
                        "apps": [
                            {
                                "app": "sub2api",
                                "repo_name": "sub2api",
                                "repo_root": str(canonical_root),
                                "service_key": "sub2api",
                                "contracts": {"prod0-main": "deploy/agentplane/contract.yaml"},
                            }
                        ]
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            for app_root in (canonical_root, worktree_root):
                (app_root / "deploy" / "agentplane").mkdir(parents=True, exist_ok=True)
                (app_root / "deploy" / "agentplane" / "contract.yaml").write_text("{}", encoding="utf-8")

            payload = run_cli(
                "app",
                "object",
                "search",
                "--target",
                "prod0-main",
                "--app",
                "sub2api",
                "--repo-root",
                str(repo_root),
                "--app-repo-root",
                str(worktree_root),
            )

            self.assertEqual(0, payload.returncode, msg=payload.stderr)
            payload_json = json.loads(payload.stdout)
            self.assertEqual(
                [
                    {
                        "app": "sub2api",
                        "target": "prod0-main",
                        "repo_name": "sub2api.worktree",
                        "service_key": "sub2api",
                        "canonical_ref": "apps/sub2api/contracts/prod0-main",
                        "resolved_path": str((worktree_root / "deploy" / "agentplane" / "contract.yaml").resolve()),
                        "contract_file": str((worktree_root / "deploy" / "agentplane" / "contract.yaml").resolve()),
                        "control_plane": "compose",
                        "public_url": "https://token.example.net:8443",
                    }
                ],
                payload_json["payload"]["items"],
            )

    def test_app_object_get_prefers_explicit_app_repo_root_over_catalog_repo_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            repo_root = tmp_root / "oplinux"
            canonical_root = tmp_root / "sub2api"
            worktree_root = tmp_root / "sub2api.worktree"
            repo_root.mkdir(parents=True, exist_ok=True)
            canonical_root.mkdir(parents=True, exist_ok=True)
            worktree_root.mkdir(parents=True, exist_ok=True)

            server_root = repo_root / "inventory" / "servers" / "prod0-main"
            server_root.mkdir(parents=True, exist_ok=True)
            (server_root / "inventory.json").write_text(
                json.dumps(
                    {
                        "services": {
                            "sub2api": {
                                "app": "sub2api",
                                "control_plane": "compose",
                                "public_url": "https://token.example.net:8443",
                            }
                        }
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            catalog_root = repo_root / "inventory" / "apps"
            catalog_root.mkdir(parents=True, exist_ok=True)
            (catalog_root / "catalog.json").write_text(
                json.dumps(
                    {
                        "apps": [
                            {
                                "app": "sub2api",
                                "repo_name": "sub2api",
                                "repo_root": str(canonical_root),
                                "service_key": "sub2api",
                                "contracts": {"prod0-main": "deploy/agentplane/contract.yaml"},
                            }
                        ]
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            for app_root, marker in ((canonical_root, "canonical"), (worktree_root, "worktree")):
                (app_root / "deploy" / "agentplane").mkdir(parents=True, exist_ok=True)
                (app_root / "deploy" / "agentplane" / "contract.yaml").write_text(
                    json.dumps({"docs": {"app_summary_file": f"docs/{marker.upper()}.md"}}),
                    encoding="utf-8",
                )
                summary_file = app_root / "docs" / f"{marker.upper()}.md"
                summary_file.parent.mkdir(parents=True, exist_ok=True)
                summary_file.write_text(f"# {marker}\n", encoding="utf-8")

            payload = run_cli(
                "app",
                "object",
                "get",
                "--target",
                "prod0-main",
                "--app",
                "sub2api",
                "--repo-root",
                str(repo_root),
                "--app-repo-root",
                str(worktree_root),
            )

            self.assertEqual(0, payload.returncode, msg=payload.stderr)
            payload_json = json.loads(payload.stdout)
            self.assertEqual(
                str((worktree_root / "deploy" / "agentplane" / "contract.yaml").resolve()),
                payload_json["payload"]["app"]["contract_file"],
            )
            self.assertEqual(
                [
                    {
                        "target": "prod0-main",
                        "path": str((worktree_root / "docs" / "WORKTREE.md").resolve()),
                        "source": "docs.app_summary_file",
                        "exists": True,
                    }
                ],
                payload_json["payload"]["summary_files"],
            )

    def test_app_object_verify_prefers_explicit_app_repo_root_over_catalog_repo_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            repo_root = tmp_root / "oplinux"
            canonical_root = tmp_root / "sub2api"
            worktree_root = tmp_root / "sub2api.worktree"
            repo_root.mkdir(parents=True, exist_ok=True)
            canonical_root.mkdir(parents=True, exist_ok=True)
            worktree_root.mkdir(parents=True, exist_ok=True)

            server_root = repo_root / "inventory" / "servers" / "prod0-main"
            server_root.mkdir(parents=True, exist_ok=True)
            (server_root / "inventory.json").write_text(
                json.dumps(
                    {
                        "services": {
                            "sub2api": {
                                "app": "sub2api",
                                "control_plane": "compose",
                                "public_url": "https://token.example.net:8443",
                            }
                        },
                        "object_ledgers": {"ledgers": {"apps": "inventory/servers/prod0-main/ledgers/apps.json"}},
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            ledger_root = server_root / "ledgers"
            ledger_root.mkdir(parents=True, exist_ok=True)
            (ledger_root / "apps.json").write_text(
                json.dumps({"count": 1}, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            (ledger_root / "apps.md").write_text("# apps\n", encoding="utf-8")
            catalog_root = repo_root / "inventory" / "apps"
            catalog_root.mkdir(parents=True, exist_ok=True)
            (catalog_root / "catalog.json").write_text(
                json.dumps(
                    {
                        "apps": [
                            {
                                "app": "sub2api",
                                "repo_name": "sub2api",
                                "repo_root": str(canonical_root),
                                "service_key": "sub2api",
                                "contracts": {"prod0-main": "deploy/agentplane/contract.yaml"},
                            }
                        ]
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            (canonical_root / "deploy" / "agentplane").mkdir(parents=True, exist_ok=True)
            (canonical_root / "deploy" / "agentplane" / "contract.yaml").write_text(
                json.dumps({"docs": {"app_summary_file": "docs/CANONICAL.md"}}),
                encoding="utf-8",
            )

            (worktree_root / "deploy" / "agentplane").mkdir(parents=True, exist_ok=True)
            (worktree_root / "deploy" / "agentplane" / "contract.yaml").write_text(
                json.dumps({"docs": {"app_summary_file": "docs/WORKTREE.md"}}),
                encoding="utf-8",
            )
            summary_file = worktree_root / "docs" / "WORKTREE.md"
            summary_file.parent.mkdir(parents=True, exist_ok=True)
            summary_file.write_text("# worktree\n", encoding="utf-8")

            payload = run_cli(
                "app",
                "object",
                "verify",
                "--target",
                "prod0-main",
                "--app",
                "sub2api",
                "--repo-root",
                str(repo_root),
                "--app-repo-root",
                str(worktree_root),
            )

            self.assertEqual(0, payload.returncode, msg=payload.stderr)
            payload_json = json.loads(payload.stdout)
            self.assertTrue(payload_json["payload"]["ok"])
            self.assertEqual(
                [
                    {
                        "target": "prod0-main",
                        "path": str(summary_file.resolve()),
                        "source": "docs.app_summary_file",
                        "exists": True,
                    }
                ],
                payload_json["payload"]["checks"]["summary_files"]["items"],
            )


# ======================================================================
# From: test_app_object_lifecycle.py
# ======================================================================


def _write_catalog(repo_root: Path, payload: dict) -> None:
    path = repo_root / "inventory" / "apps" / "catalog.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_catalog(repo_root: Path) -> dict:
    path = repo_root / "inventory" / "apps" / "catalog.json"
    return json.loads(path.read_text(encoding="utf-8"))


class AppObjectLifecycleCatalogTests(unittest.TestCase):
    def test_onboard_adds_entry_and_sorts_by_app_id(self) -> None:
        with tempfile.TemporaryDirectory(prefix="oplinux-app-catalog-") as tmp:
            repo_root = Path(tmp)

            _write_catalog(
                repo_root,
                {
                    "apps": [
                        {
                            "app": "sub2api",
                            "repo_name": "sub2api",
                            "repo_root": "/work/sub2api",
                            "service_key": "sub2api",
                            "contracts": {"prod0-main": "deploy/agentplane/contract.yaml"},
                        }
                    ]
                },
            )

            entry = AppCatalogEntry(
                app="sampleapi",
                repo_name="new-api",
                repo_root=Path("/work/new-api"),
                service_key="sampleapi",
                contracts={"prod0-main": "deploy/agentplane/contract.yaml"},
            )

            result = onboard_catalog_entry(repo_root, entry, write=True)
            self.assertTrue(result.changed)
            payload = _read_catalog(repo_root)
            apps = payload["apps"]
            self.assertEqual(["sampleapi", "sub2api"], [item["app"] for item in apps])
            self.assertEqual("sampleapi", apps[0]["service_key"])

    def test_onboard_rejects_service_key_alias(self) -> None:
        with tempfile.TemporaryDirectory(prefix="oplinux-app-catalog-") as tmp:
            repo_root = Path(tmp)
            _write_catalog(repo_root, {"apps": []})

            entry = AppCatalogEntry(
                app="sampleapi",
                repo_name="new-api",
                repo_root=Path("/work/new-api"),
                service_key="new-api",
                contracts={"prod0-main": "deploy/agentplane/contract.yaml"},
            )
            with self.assertRaises(ValueError):
                onboard_catalog_entry(repo_root, entry, write=True)

    def test_offboard_removes_entry(self) -> None:
        with tempfile.TemporaryDirectory(prefix="oplinux-app-catalog-") as tmp:
            repo_root = Path(tmp)
            _write_catalog(
                repo_root,
                {
                    "apps": [
                        {
                            "app": "sampleapi",
                            "repo_name": "new-api",
                            "repo_root": "/work/new-api",
                            "service_key": "sampleapi",
                            "contracts": {"prod0-main": "deploy/agentplane/contract.yaml"},
                        }
                    ]
                },
            )

            result = offboard_catalog_entry(repo_root, app_id="sampleapi", write=True)
            self.assertTrue(result.changed)
            payload = _read_catalog(repo_root)
            self.assertEqual([], payload["apps"])


# ======================================================================
# From: test_app_object_tracked_catalog.py
# ======================================================================


class AppObjectTrackedCatalogTests(unittest.TestCase):
    def test_real_tracked_catalog_contains_sub2api(self) -> None:
        catalog_file = REPO_ROOT / "inventory" / "apps" / "catalog.json"

        payload = json.loads(catalog_file.read_text(encoding="utf-8"))

        apps = [entry["app"] for entry in payload.get("apps", [])]
        self.assertIn("sub2api", apps)

    def test_real_catalog_search_returns_sub2api_for_prod0_main(self) -> None:
        payload = run_cli(
            "app",
            "object",
            "search",
            "--target",
            "prod0-main",
            "--repo-root",
            str(REPO_ROOT),
        )

        self.assertEqual(0, payload.returncode, msg=payload.stderr)
        payload_json = json.loads(payload.stdout)
        apps = [item["app"] for item in payload_json["payload"]["items"]]
        self.assertIn("sub2api", apps)

    def test_real_catalog_search_returns_sub2api_for_wsl(self) -> None:
        wsl_payload = run_cli(
            "app",
            "object",
            "search",
            "--target",
            "wsl",
            "--repo-root",
            str(REPO_ROOT),
        )

        self.assertEqual(0, wsl_payload.returncode, msg=wsl_payload.stderr)
        wsl_json = json.loads(wsl_payload.stdout)
        apps = [item["app"] for item in wsl_json["payload"]["items"]]
        self.assertIn("sub2api", apps)
