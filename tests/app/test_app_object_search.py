from __future__ import annotations

import importlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pytest
from tests.support.app_object import run_cli, write_inventory_with_app

pytestmark = pytest.mark.integration


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

