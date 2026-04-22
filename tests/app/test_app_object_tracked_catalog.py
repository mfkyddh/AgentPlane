import json
import unittest

from tests.support.app_object import REPO_ROOT, run_cli


class AppObjectTrackedCatalogTests(unittest.TestCase):
    def test_real_tracked_catalog_is_empty_after_offboarding_local_app_delivery(self) -> None:
        catalog_file = REPO_ROOT / "inventory" / "apps" / "catalog.json"

        payload = json.loads(catalog_file.read_text(encoding="utf-8"))

        self.assertEqual({"apps": []}, payload)

    def test_real_catalog_search_is_empty_for_prod0_main(self) -> None:
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
        self.assertEqual([], payload_json["payload"]["items"])

    def test_real_catalog_search_is_empty_for_wsl(self) -> None:
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
        self.assertEqual([], wsl_json["payload"]["items"])

    def test_real_tracked_apps_ledgers_are_empty(self) -> None:
        for target in ("wsl", "prod0-main", "prod2-main"):
            with self.subTest(target=target):
                ledger_json = json.loads(
                    (REPO_ROOT / "inventory" / "servers" / target / "ledgers" / "apps.json").read_text(encoding="utf-8")
                )
                self.assertEqual([], ledger_json["items"])
                self.assertEqual(0, ledger_json["count"])
                ledger_markdown = (
                    REPO_ROOT / "inventory" / "servers" / target / "ledgers" / "apps.md"
                ).read_text(encoding="utf-8")
                self.assertIn("no active app catalog object", ledger_markdown)

    def test_real_sub2api_inventory_keeps_none_previous_control_plane_rollback(self) -> None:
        inventory_payload = json.loads(
            (REPO_ROOT / "inventory" / "servers" / "prod0-main" / "inventory.json").read_text(encoding="utf-8")
        )
        self.assertIn("sub2api", inventory_payload["services"])
        self.assertEqual({"kind": "none"}, inventory_payload["services"]["sub2api"]["rollback_entry"])

    def test_real_wsl_sub2api_container_is_managed(self) -> None:
        inventory_payload = json.loads(
            (REPO_ROOT / "inventory" / "servers" / "wsl" / "inventory.json").read_text(encoding="utf-8")
        )

        managed_names = {item["name"] for item in inventory_payload["docker_containers"]}
        unmanaged_names = {item["name"] for item in inventory_payload["unmanaged_docker_containers"]}
        self.assertIn("sub2api-dev", managed_names)
        self.assertNotIn("sub2api-dev", unmanaged_names)


if __name__ == "__main__":
    unittest.main()
