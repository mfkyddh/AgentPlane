import json
import unittest

import pytest

from tests.support.app_object import REPO_ROOT, expected_real_contract_path as _expected_real_contract_path, run_cli


class AppObjectTrackedCatalogTests(unittest.TestCase):
    def test_real_tracked_catalog_freezes_sub2api_only(self) -> None:
        catalog_file = REPO_ROOT / "inventory" / "apps" / "catalog.json"

        payload = json.loads(catalog_file.read_text(encoding="utf-8"))

        self.assertEqual(
            {
                "apps": [
                    {
                        "app": "sub2api",
                        "repo_name": "sub2api",
                        "repo_ref": "apps/sub2api",
                        "service_key": "sub2api",
                        "contracts": {
                            "wsl": "apps/sub2api/contracts/wsl",
                            "prod0-main": "apps/sub2api/contracts/prod0-main",
                            "prod2-main": "apps/sub2api/contracts/prod2-main",
                        },
                    },
                ]
            },
            payload,
        )

    def test_real_catalog_resolves_sub2api_for_prod0_main(self) -> None:
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
        self.assertEqual(["sub2api"], [item["app"] for item in payload_json["payload"]["items"]])
        self.assertEqual(
            "apps/sub2api/contracts/prod0-main",
            payload_json["payload"]["items"][0]["canonical_ref"],
        )
        self.assertEqual(
            _expected_real_contract_path("prod0-main"),
            payload_json["payload"]["items"][0]["contract_file"],
        )

    def test_real_catalog_resolves_sub2api_for_prod2_main_and_wsl(self) -> None:
        prod2_payload = run_cli(
            "app",
            "object",
            "get",
            "--target",
            "prod2-main",
            "--app",
            "sub2api",
            "--repo-root",
            str(REPO_ROOT),
        )

        self.assertEqual(0, prod2_payload.returncode, msg=prod2_payload.stderr)
        prod2_json = json.loads(prod2_payload.stdout)
        self.assertEqual(
            "apps/sub2api/contracts/prod2-main",
            prod2_json["payload"]["app"]["canonical_ref"],
        )
        self.assertEqual(
            _expected_real_contract_path("prod2-main"),
            prod2_json["payload"]["app"]["contract_file"],
        )

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
        self.assertEqual(["sub2api"], [item["app"] for item in wsl_json["payload"]["items"]])
        self.assertEqual(
            "apps/sub2api/contracts/wsl",
            wsl_json["payload"]["items"][0]["canonical_ref"],
        )
        self.assertEqual(
            _expected_real_contract_path("wsl"),
            wsl_json["payload"]["items"][0]["contract_file"],
        )

    @pytest.mark.external_app
    def test_real_formal_catalog_sub2api_keeps_none_previous_control_plane(self) -> None:
        for target in ("wsl", "prod0-main", "prod2-main"):
            with self.subTest(target=target):
                payload = run_cli(
                    "app",
                    "delivery",
                    "validate-contract",
                    "--target",
                    target,
                    "--app",
                    "sub2api",
                    "--repo-root",
                    str(REPO_ROOT),
                )

                self.assertEqual(0, payload.returncode, msg=payload.stderr)
                payload_json = json.loads(payload.stdout)
                self.assertEqual(2, payload_json["payload"]["schema_version"])
                self.assertTrue(payload_json["payload"]["_meta"]["artifact_first"])
                self.assertEqual("dist/oplinux", payload_json["payload"]["artifact"]["output_path"])
                self.assertEqual("linux", payload_json["payload"]["artifact"]["runtime_os"])
                self.assertEqual("amd64", payload_json["payload"]["artifact"]["runtime_arch"])
                self.assertEqual("wsl-linux", payload_json["payload"]["packaging"]["backend"])
                self.assertEqual(
                    "bash deploy/package-runtime-image.sh",
                    payload_json["payload"]["packaging"]["package_command"],
                )
                self.assertEqual("none", payload_json["payload"]["rollback"]["previous_control_plane"]["kind"])

    def test_real_catalog_has_no_newapi_or_sub2apipay_entries(self) -> None:
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
        self.assertEqual(["sub2api"], [item["app"] for item in payload_json["payload"]["items"]])
        self.assertNotIn("newapi", [item["app"] for item in payload_json["payload"]["items"]])
        self.assertNotIn("sub2apipay", [item["app"] for item in payload_json["payload"]["items"]])

    def test_real_tracked_apps_ledgers_only_include_sub2api(self) -> None:
        for target, canonical_ref in (
            ("prod0-main", "apps/sub2api/contracts/prod0-main"),
            ("prod2-main", "apps/sub2api/contracts/prod2-main"),
        ):
            with self.subTest(target=target):
                ledger_json = json.loads(
                    (REPO_ROOT / "inventory" / "servers" / target / "ledgers" / "apps.json").read_text(encoding="utf-8")
                )
                items = ledger_json["items"]
                self.assertEqual(["sub2api"], [item["app"] for item in items])
                self.assertEqual(canonical_ref, items[0]["canonical_ref"])
                self.assertNotIn("resolved_path", items[0])
                self.assertNotIn("contract_file", items[0])
                ledger_markdown = (
                    REPO_ROOT / "inventory" / "servers" / target / "ledgers" / "apps.md"
                ).read_text(encoding="utf-8")
                self.assertIn("`sub2api` / `compose`", ledger_markdown)
                self.assertNotIn("`newapi` / `compose`", ledger_markdown)
                self.assertNotIn("`sub2apipay` / `compose`", ledger_markdown)

    def test_real_sub2api_inventory_keeps_none_previous_control_plane_rollback(self) -> None:
        inventory_payload = json.loads(
            (REPO_ROOT / "inventory" / "servers" / "prod0-main" / "inventory.json").read_text(encoding="utf-8")
        )
        self.assertIn("sub2api", inventory_payload["services"])
        self.assertEqual({"kind": "none"}, inventory_payload["services"]["sub2api"]["rollback_entry"])


if __name__ == "__main__":
    unittest.main()
