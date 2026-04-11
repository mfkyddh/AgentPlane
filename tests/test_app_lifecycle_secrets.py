import json
import tempfile
import unittest
from pathlib import Path

from agentplane.domain.app.resource_paths import app_resource_secret_dir, app_resource_secret_relative
from agentplane.domain.app.secrets_lifecycle import (
    apply_secret_allocation,
    apply_secret_retirement,
    plan_secret_allocation,
    plan_secret_retirement,
)


TARGET = "prod0-main"
APP = "phase5"


def _write_catalog(root: Path) -> None:
    catalog_dir = root / "inventory" / "apps"
    catalog_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "apps": [
            {
                "app": APP,
                "repo_name": "phase5-app",
                "repo_root": str(root),
                "service_key": APP,
                "contracts": {TARGET: "deploy/agentplane/contract.yaml"},
            }
        ]
    }
    (catalog_dir / "catalog.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_registry(root: Path) -> None:
    server_dir = root / "inventory" / "servers" / TARGET
    server_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        APP: {
            "owner_app": APP,
            "ledger_status": {
                "intent": "live-db-partition-ledger",
                "runtime_credential_model": "shared-runtime-credentials",
                "tenant_isolation": "logical-db-partition-not-strong-isolation",
                "local_secret_presence": "not-materialized-by-repo",
            },
            "postgres": {"database": "phase5_db", "user": "phase5_user"},
            "redis": {"db": 1, "key_prefix": "phase5:"},
            "secret_files": [],
        }
    }
    (server_dir / "app-resources.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class SecretLifecycleTests(unittest.TestCase):
    def test_allocate_and_retire_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_catalog(root)
            _write_registry(root)

            plan = plan_secret_allocation(root, TARGET, APP)
            self.assertEqual("allocate", plan["operation"])
            self.assertFalse(plan["guarded"])
            self.assertEqual({"postgres.env", "redis.env"}, {Path(item["relative"]).name for item in plan["files"]})
            self.assertSetEqual(
                {
                    app_resource_secret_relative(TARGET, APP, "postgres"),
                    app_resource_secret_relative(TARGET, APP, "redis"),
                },
                set(plan["missing_files"]),
            )

            allocation = apply_secret_allocation(root, TARGET, APP, execute=True)
            self.assertTrue(all(Path(path).is_file() for path in allocation["created_files"]))
            self.assertEqual(2, len(allocation["created_files"]))
            registry_path = root / "inventory" / "servers" / TARGET / "app-resources.json"
            updated = json.loads(registry_path.read_text(encoding="utf-8"))[APP]
            self.assertEqual("materialized-in-agentplane", updated["ledger_status"]["local_secret_presence"])
            self.assertEqual(
                [
                    app_resource_secret_relative(TARGET, APP, "postgres"),
                    app_resource_secret_relative(TARGET, APP, "redis"),
                ],
                updated["secret_files"],
            )

            plan_after = plan_secret_allocation(root, TARGET, APP)
            self.assertEqual([], plan_after["missing_files"])
            self.assertTrue(all(item["exists"] for item in plan_after["files"]))

            retirement_plan = plan_secret_retirement(root, TARGET, APP)
            self.assertTrue(retirement_plan["guarded"])
            self.assertFalse(retirement_plan["missing_files"])
            self.assertTrue(all(item["exists"] for item in retirement_plan["files"]))

            retired = apply_secret_retirement(root, TARGET, APP, execute=True)
            self.assertEqual(set(allocation["created_files"]), set(retired["removed_files"]))
            self.assertFalse((app_resource_secret_dir(root, TARGET, APP) / "postgres.env").exists())
            registry_final = json.loads(registry_path.read_text(encoding="utf-8"))[APP]
            self.assertEqual("retired", registry_final["ledger_status"]["local_secret_presence"])

            plan_after_retirement = plan_secret_retirement(root, TARGET, APP)
            self.assertTrue(plan_after_retirement["missing_files"])
            self.assertEqual(
                plan_after_retirement["missing_files"],
                [
                    app_resource_secret_relative(TARGET, APP, "postgres"),
                    app_resource_secret_relative(TARGET, APP, "redis"),
                ],
            )


if __name__ == "__main__":
    unittest.main()
