from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pytest
from tests.support.app_object import run_cli, write_inventory_with_app

pytestmark = pytest.mark.integration


class AppObjectCliTests(unittest.TestCase):
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

