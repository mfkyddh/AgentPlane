import json
import tempfile
import unittest
from pathlib import Path

from agentplane.domain.service import lifecycle as service_lifecycle


class ServiceLifecycleTests(unittest.TestCase):
    def test_plan_onboard_and_offboard_cycles(self):
        base_services = {
            "postgres": {"container_name": "postgres18"},
        }
        next_services, evidence = service_lifecycle.plan_service_registry_onboard(
            base_services,
            service_key="newapi",
            entry={"container_name": "newapi-prod", "control_plane": "compose"},
        )
        self.assertIn("newapi", next_services)
        self.assertEqual(next_services["newapi"]["container_name"], "newapi-prod")
        self.assertFalse(evidence["replaced"])
        self.assertEqual(evidence["action"], "upsert")

        replaced_services, replaced_evidence = service_lifecycle.plan_service_registry_onboard(
            next_services,
            service_key="newapi",
            entry={"container_name": "newapi-prod", "control_plane": "compose"},
            allow_replace=True,
        )
        self.assertTrue(replaced_evidence["replaced"])
        self.assertEqual(replaced_services["newapi"]["container_name"], "newapi-prod")

        offboarded_services, remove_evidence = service_lifecycle.plan_service_registry_offboard(
            replaced_services,
            service_key="newapi",
        )
        self.assertNotIn("newapi", offboarded_services)
        self.assertEqual(remove_evidence["action"], "remove")
        self.assertEqual(remove_evidence["service_key"], "newapi")

        with self.assertRaises(ValueError):
            service_lifecycle.plan_service_registry_offboard(
                offboarded_services,
                service_key="newapi",
            )

    def test_plan_rejects_invalid_entries(self):
        base_services = {}
        with self.assertRaises(ValueError):
            service_lifecycle.plan_service_registry_onboard(
                base_services,
                service_key="docker",
                entry={"container_name": "ignored"},
            )
        with self.assertRaises(ValueError):
            service_lifecycle.plan_service_registry_onboard(
                base_services,
                service_key="newapi",
                entry={"container_name": " ", "control_plane": "compose"},
            )
        with self.assertRaises(ValueError):
            service_lifecycle.plan_service_registry_onboard(
                base_services,
                service_key="newapi",
                entry={"container_name": "foo", "control_plane": "invalid"},
            )

    def test_apply_round_trip_updates_inventory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            target = "wsl"
            inventory_file = self._write_inventory(repo_root, target, {"postgres": {"container_name": "postgres18"}})

            onboard_result = service_lifecycle.apply_service_onboard(
                repo_root=repo_root,
                target=target,
                service_key="newapi",
                entry={"container_name": " newapi-prod ", "control_plane": "compose"},
            )
            self.assertTrue(onboard_result.changed)
            payload = json.loads(inventory_file.read_text(encoding="utf-8").strip())
            self.assertIn("newapi", payload["services"])
            self.assertEqual(payload["services"]["newapi"]["container_name"], "newapi-prod")

            offboard_result = service_lifecycle.apply_service_offboard(
                repo_root=repo_root,
                target=target,
                service_key="newapi",
            )
            self.assertTrue(offboard_result.changed)
            payload_after = json.loads(inventory_file.read_text(encoding="utf-8").strip())
            self.assertNotIn("newapi", payload_after["services"])

    def _write_inventory(self, repo_root: Path, target: str, services: dict[str, dict[str, str]]) -> Path:
        server_dir = repo_root / "inventory" / "servers" / target
        server_dir.mkdir(parents=True, exist_ok=True)
        inventory_file = server_dir / "inventory.json"
        payload = {"services": services}
        inventory_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return inventory_file
