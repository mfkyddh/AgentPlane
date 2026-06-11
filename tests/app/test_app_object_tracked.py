from __future__ import annotations

import json
import unittest

import pytest
from tests.support.app_object import REPO_ROOT, run_cli

pytestmark = pytest.mark.integration


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
