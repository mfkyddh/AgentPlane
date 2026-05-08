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


