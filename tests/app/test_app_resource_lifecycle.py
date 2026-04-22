from __future__ import annotations

import unittest

from agentplane.domain.app.truth_lifecycle import (
    find_orphaned_inventory_app_resource_summaries,
    find_orphaned_registry_keys,
    make_app_resource_registry_entry,
    plan_app_resource_registry_offboard,
    plan_app_resource_registry_onboard,
)


class AppResourceLifecycleTests(unittest.TestCase):
    def test_registry_onboard_requires_phase1_key_and_owner(self) -> None:
        registry: dict[str, object] = {}
        entry = make_app_resource_registry_entry(
            app_id="sampleapi",
            resources={"redis": {"db": 2, "key_prefix": "sampleapi:"}},
            secret_files=("secrets/services/sampleapi/redis.env",),
        )
        next_registry, evidence = plan_app_resource_registry_onboard(registry, app_id="sampleapi", entry=entry)
        self.assertEqual("upsert", evidence["action"])
        self.assertIn("sampleapi", next_registry)
        self.assertEqual("sampleapi", next_registry["sampleapi"]["owner_app"])

        with self.assertRaises(ValueError):
            plan_app_resource_registry_onboard(registry, app_id="sampleapi", entry=entry, registry_key="alias")

        with self.assertRaises(ValueError):
            plan_app_resource_registry_onboard(registry, app_id="sampleapi", entry={"owner_app": "sub2api"})

    def test_registry_offboard_removes_by_key_and_owner_app(self) -> None:
        registry = {
            "sampleapi": {"owner_app": "sampleapi", "redis": {"db": 2, "key_prefix": "sampleapi:"}},
            "legacy-alias": {"owner_app": "sampleapi", "redis": {"db": 2, "key_prefix": "sampleapi:"}},
            "sub2api": {"owner_app": "sub2api", "redis": {"db": 1, "key_prefix": "sub2api:"}},
        }
        next_registry, evidence = plan_app_resource_registry_offboard(registry, app_id="sampleapi")
        self.assertEqual(["legacy-alias", "sampleapi"], sorted(evidence["removed_keys"]))
        self.assertNotIn("sampleapi", next_registry)
        self.assertNotIn("legacy-alias", next_registry)
        self.assertIn("sub2api", next_registry)

    def test_find_orphans_from_registry_and_inventory_summary(self) -> None:
        catalog_apps = {"sub2api"}
        registry = {"sampleapi": {"owner_app": "sampleapi"}, "sub2api": {"owner_app": "sub2api"}}
        self.assertEqual(["sampleapi"], find_orphaned_registry_keys(registry, catalog_apps=catalog_apps))

        inventory_payload = {
            "services": {
                "sub2api": {"app_resource_summary": {"redis": {"db": 1}}},
                "sampleapi": {"app_resource_summary": {"redis": {"db": 2}}},
                "other": {"something": 1},
            }
        }
        self.assertEqual(
            ["sampleapi"],
            find_orphaned_inventory_app_resource_summaries(inventory_payload, catalog_keys={"sub2api"}),
        )


