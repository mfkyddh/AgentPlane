from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pytest
import yaml
from agentplane.domain.app.truth_lifecycle import (
    find_orphaned_inventory_app_resource_summaries,
    find_orphaned_registry_keys,
    make_app_resource_registry_entry,
    plan_app_resource_registry_offboard,
    plan_app_resource_registry_onboard,
)
from tests.support.app_delivery_cli import run_app_delivery_cli
from tests.support.app_delivery_contracts import write_contract
from tests.support.app_delivery_targets import (
    baseline_tenant_resources,
)
from tests.support.app_delivery_targets import (
    write_inventory as write_delivery_inventory,
)
from tests.support.app_delivery_targets import (
    write_tenant_secret_files as write_delivery_tenant_secret_files,
)
from tests.support.app_resources import resource_relative, resource_root

pytestmark = pytest.mark.integration


def write_inventory(root: Path, *, projection_drift: bool = False) -> None:
    server_root = root / "inventory" / "servers" / "prod0-main"
    server_root.mkdir(parents=True, exist_ok=True)
    (server_root / "README.md").write_text("# prod0-main 摘要\n", encoding="utf-8")
    app_resource_summary = {
        "postgres": {
            "database": "sub2api_prod0",
            "user": "sub2api_prod0",
            "secret_file": resource_relative("prod0-main", "sub2api", "postgres"),
        },
        "redis": {
            "db": 1 if not projection_drift else 9,
            "key_prefix": "sub2api:",
            "secret_file": resource_relative("prod0-main", "sub2api", "redis"),
        },
        "minio": {
            "bucket": "prod0-sub2api",
            "access_key": "sub2api_prod0",
            "policy_name": "prod0-sub2api-rw",
            "policy_scope": "bucket-only",
            "isolation_level": "bucket-scoped-rw",
            "secret_file": resource_relative("prod0-main", "sub2api", "minio"),
        },
    }
    (server_root / "inventory.json").write_text(
        json.dumps(
            {
                "services": {
                    "sub2api": {
                        "control_plane": "compose",
                        "container_name": "sub2api-prod",
                        "app_resource_summary": app_resource_summary,
                    }
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def write_registry(root: Path, *, secret_file: str | None = None) -> None:
    registry_file = root / "inventory" / "servers" / "prod0-main" / "app-resources.json"
    registry_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "sub2api": {
            "owner_app": "sub2api",
            "ledger_status": {
                "intent": "live-db-partition-ledger",
                "runtime_credential_model": "shared-runtime-credentials",
                "tenant_isolation": "logical-db-partition-not-strong-isolation",
                "local_secret_presence": "materialized-in-agentplane",
            },
            "postgres": {
                "database": "sub2api_prod0",
                "user": "sub2api_prod0",
            },
            "redis": {
                "db": 1,
                "key_prefix": "sub2api:",
            },
            "minio": {
                "bucket": "prod0-sub2api",
                "access_key": "sub2api_prod0",
                "policy_name": "prod0-sub2api-rw",
                "policy_scope": "bucket-only",
                "isolation_level": "bucket-scoped-rw",
            },
            "secret_files": [
                resource_relative("prod0-main", "sub2api", "postgres"),
                secret_file or resource_relative("prod0-main", "sub2api", "redis"),
                resource_relative("prod0-main", "sub2api", "minio"),
            ],
        }
    }
    registry_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_resource_secrets(root: Path, *, include_redis: bool = True) -> None:
    resource_dir = resource_root(root, "prod0-main", "sub2api")
    resource_dir.mkdir(parents=True, exist_ok=True)
    (resource_dir / "postgres.env").write_text(
        "PGHOST=postgres18-prod\nPGPORT=5432\nPGDATABASE=sub2api_prod0\nPGUSER=sub2api_prod0\nPGPASSWORD=secret\n",
        encoding="utf-8",
    )
    if include_redis:
        (resource_dir / "redis.env").write_text(
            "REDIS_HOST=redis7-prod\nREDIS_PORT=6379\nREDIS_PASSWORD=secret\nREDIS_DB=1\nREDIS_KEY_PREFIX=sub2api:\nREDIS_ENABLE_TLS=false\n",
            encoding="utf-8",
        )
    (resource_dir / "minio.env").write_text(
        "MINIO_BUCKET=prod0-sub2api\nMINIO_ACCESS_KEY=sub2api_prod0\nMINIO_SECRET_KEY=secret\n",
        encoding="utf-8",
    )


def write_catalog(
    root: Path,
    *,
    app: str = "sub2api",
    service_key: str = "sub2api",
) -> None:
    catalog_root = root / "inventory" / "apps"
    catalog_root.mkdir(parents=True, exist_ok=True)
    (catalog_root / "catalog.json").write_text(
        json.dumps(
            {
                "apps": [
                    {
                        "app": app,
                        "repo_name": app,
                        "repo_root": f"/tmp/{app}",
                        "service_key": service_key,
                        "contracts": {"prod0-main": "deploy/agentplane/contract.yaml"},
                    }
                ]
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )




# ======================================================================
# From: test_app_resource_lifecycle.py
# ======================================================================


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



# ======================================================================
# From: test_app_artifact_contract.py
# ======================================================================


class AppArtifactContractTests(unittest.TestCase):
    def test_validate_contract_accepts_schema2_artifact_first_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_delivery_inventory(root)
            write_delivery_tenant_secret_files(root, target="wsl")
            write_contract(
                root,
                schema_version=2,
                tenant_resources=baseline_tenant_resources(target="wsl"),
                build_command="bash deploy/build-runtime-artifacts.sh",
                package_command="bash deploy/package-runtime-image.sh",
                packaging_backend="wsl-linux",
            )

            result = run_app_delivery_cli("validate-contract", repo_root=root, app="sub2api", target="wsl")

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)["payload"]
            self.assertEqual("v2", payload["_meta"]["contract_mode"])
            self.assertTrue(payload["_meta"]["artifact_first"])

    def test_validate_contract_rejects_schema2_contract_missing_packaging_backend(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_delivery_inventory(root)
            write_delivery_tenant_secret_files(root)
            contract_file = write_contract(
                root,
                schema_version=2,
                tenant_resources=baseline_tenant_resources(),
                build_command="bash deploy/build-runtime-artifacts.sh",
                package_command="bash deploy/package-runtime-image.sh",
            )
            payload = yaml.safe_load(contract_file.read_text(encoding="utf-8"))
            del payload["packaging"]["backend"]
            contract_file.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8")

            result = run_app_delivery_cli("validate-contract", repo_root=root, app="sub2api")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("packaging.backend", result.stderr)
