from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

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
from tests.support.cli import run_agentplane_cli as run_cli

pytestmark = pytest.mark.e2e


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




class AppResourceCliTests(unittest.TestCase):
    def test_app_resource_search_lists_declared_registry_objects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_registry(root)

            result = run_cli("app", "resource", "search", "--target", "prod0-main", "--repo-root", str(root))

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("app", payload["command"])
            self.assertEqual("resource.search", payload["action"])
            self.assertEqual(
                [
                    {
                        "app": "sub2api",
                        "owner_app": "sub2api",
                        "resource_kinds": ["minio", "postgres", "redis"],
                    }
                ],
                payload["payload"]["items"],
            )

    def test_app_resource_get_aggregates_declared_projection_and_secret_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_registry(root)
            write_resource_secrets(root)

            result = run_cli(
                "app", "resource", "get", "--target", "prod0-main", "--app", "sub2api", "--repo-root", str(root)
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("resource.get", payload["action"])
            self.assertEqual("sub2api", payload["payload"]["resource"]["app"])
            self.assertTrue(payload["payload"]["projection"]["found"])

    def test_app_resource_verify_reports_projection_drift(self) -> None:
        from unittest.mock import patch

        from agentplane.domain.app.resource_handlers import verify_app_resource

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root, projection_drift=True)
            write_registry(root)
            write_resource_secrets(root)

            with patch("agentplane.domain.app.resource_handlers._live_database_evidence", return_value=None):
                payload = verify_app_resource(root, "prod0-main", "sub2api")

            self.assertFalse(payload["ok"])
            self.assertEqual(["inventory_projection"], payload["failures"])

    def test_app_resource_verify_ignores_legacy_tenant_truth_fields(self) -> None:
        from unittest.mock import patch

        from agentplane.domain.app.resource_handlers import verify_app_resource

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_registry(root)
            registry_file = root / "inventory" / "servers" / "prod0-main" / "app-resources.json"
            registry_payload = json.loads(registry_file.read_text(encoding="utf-8"))
            entry = registry_payload["sub2api"]
            entry["tenant_app"] = "legacy-sub2api"
            entry["tenant_resources"] = {
                "postgres": {"database": "legacy_db", "user": "legacy_user"},
                "redis": {"db": 9, "key_prefix": "legacy:"},
                "minio": {"bucket": "legacy-bucket", "access_key": "legacy-user"},
            }
            registry_file.write_text(json.dumps(registry_payload, ensure_ascii=False, indent=2), encoding="utf-8")
            write_resource_secrets(root)

            with patch("agentplane.domain.app.resource_handlers._live_database_evidence", return_value=None):
                verify_payload = verify_app_resource(root, "prod0-main", "sub2api")
            search = run_cli("app", "resource", "search", "--target", "prod0-main", "--repo-root", str(root))

            self.assertTrue(verify_payload["ok"])
            self.assertEqual("sub2api", verify_payload["resource"]["owner_app"])
            expected_projection = verify_payload["checks"]["inventory_projection"]["expected"]
            self.assertEqual(1, expected_projection["redis"]["db"])
            self.assertEqual("sub2api:", expected_projection["redis"]["key_prefix"])

            self.assertEqual(search.returncode, 0, msg=search.stderr)
            search_payload = json.loads(search.stdout)
            self.assertEqual("sub2api", search_payload["payload"]["items"][0]["owner_app"])

    def test_app_resource_refresh_ledger_updates_app_resource_projection_without_mutating_registry(self) -> None:
        from agentplane.cli.apps import handle_app_command

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_registry(root)
            write_resource_secrets(root)

            args = SimpleNamespace(
                app_surface="resource",
                app_resource_action="refresh-ledger",
                target="prod0-main",
                repo_root=str(root),
                write=True,
            )

            payload = handle_app_command(args)

            self.assertEqual("app", payload["command"])
            self.assertEqual("resource.refresh-ledger", payload["action"])
            self.assertEqual(1, payload["payload"]["counts"]["app_resources"])

    def test_app_resource_get_maps_legacy_registry_key_to_catalog_owner_app(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app_id = "sample-register-v2"
            service_key = "chatgpt-register"
            write_catalog(root, app=app_id, service_key=service_key)
            write_inventory(root)
            write_resource_secrets(root)
            write_registry(root)
            registry_file = root / "inventory" / "servers" / "prod0-main" / "app-resources.json"
            registry_payload = json.loads(registry_file.read_text(encoding="utf-8"))
            registry_payload["legacy-chatgpt-register"] = registry_payload.pop("sub2api")
            registry_payload["legacy-chatgpt-register"]["owner_app"] = app_id
            registry_file.write_text(json.dumps(registry_payload, ensure_ascii=False, indent=2), encoding="utf-8")
            inventory_file = root / "inventory" / "servers" / "prod0-main" / "inventory.json"
            inventory_payload = json.loads(inventory_file.read_text(encoding="utf-8"))
            inventory_payload["services"] = {
                service_key: inventory_payload["services"].pop("sub2api"),
            }
            inventory_payload["services"][service_key]["app_resource_summary"]["redis"]["key_prefix"] = "sub2api:"
            inventory_file.write_text(json.dumps(inventory_payload, ensure_ascii=False, indent=2), encoding="utf-8")

            get = run_cli("app", "resource", "get", "--target", "prod0-main", "--app", app_id, "--repo-root", str(root))

            self.assertEqual(0, get.returncode, msg=get.stderr + get.stdout)
            payload = json.loads(get.stdout)
            self.assertEqual(app_id, payload["payload"]["resource"]["app"])
            self.assertEqual(app_id, payload["payload"]["resource"]["owner_app"])
            projection = payload["payload"]["projection"]
            self.assertEqual(service_key, projection["service_key"])



# ======================================================================
# From: test_app_resource_object_cli.py
# ======================================================================


class AppResourceObjectCliTests(unittest.TestCase):
    def test_resource_registry_lists_declared_app_resources(self) -> None:
        from agentplane.domain.app.resource_registry import available_app_resources

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_registry(root)

            items = available_app_resources(root, "prod0-main")

            self.assertEqual(
                [
                    {
                        "app": "sub2api",
                        "owner_app": "sub2api",
                        "resource_kinds": ["minio", "postgres", "redis"],
                    }
                ],
                [
                    {
                        "app": definition.app,
                        "owner_app": definition.owner_app,
                        "resource_kinds": list(definition.resource_kinds),
                    }
                    for definition, _ in items
                ],
            )

    def test_resource_get_aggregates_declared_projection_and_secret_files(self) -> None:
        from agentplane.domain.app.resource_handlers import get_app_resource

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_registry(root)
            write_resource_secrets(root)

            payload = get_app_resource(root, "prod0-main", "sub2api")

            self.assertEqual("sub2api", payload["resource"]["app"])
            self.assertEqual("sub2api", payload["declared"]["owner_app"])
            self.assertTrue(payload["projection"]["found"])
            self.assertEqual(1, payload["projection"]["app_resource_summary"]["redis"]["db"])
            self.assertEqual(
                [True, True, True],
                [item["exists"] for item in payload["secret_files"]],
            )

    def test_resource_verify_reports_projection_drift(self) -> None:
        from unittest.mock import patch

        from agentplane.domain.app.resource_handlers import verify_app_resource

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root, projection_drift=True)
            write_registry(root)
            write_resource_secrets(root)

            with patch("agentplane.domain.app.resource_handlers._live_database_evidence", return_value=None):
                payload = verify_app_resource(root, "prod0-main", "sub2api")

            self.assertFalse(payload["ok"])
            self.assertTrue(payload["checks"]["secret_files"]["ok"])
            self.assertFalse(payload["checks"]["inventory_projection"]["ok"])
            self.assertEqual(["inventory_projection"], payload["failures"])

    def test_resource_verify_separates_ledger_fields_and_observation(self) -> None:
        from unittest.mock import patch

        from agentplane.domain.app.resource_handlers import verify_app_resource

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_registry(root)
            write_resource_secrets(root)

            with patch("agentplane.domain.app.resource_handlers._live_database_evidence", return_value=None):
                payload = verify_app_resource(root, "prod0-main", "sub2api")

            self.assertTrue(payload["ok"])
            self.assertEqual("targets/prod0-main/app-resources/sub2api", payload["canonical_ref"])
            self.assertEqual("targets/prod0-main/app-resources/sub2api", payload["ledger_fields"]["canonical_ref"])
            self.assertEqual("sub2api", payload["ledger_fields"]["app"])
            self.assertNotIn("declared", payload["ledger_fields"])
            self.assertIn("declared", payload["verification_fields"])
            self.assertIn("projection", payload["verification_fields"])
            self.assertIn("secret_files", payload["verification_fields"])

    def test_resource_verify_reports_secret_scope_and_missing_file_findings(self) -> None:
        from unittest.mock import patch

        from agentplane.domain.app.resource_handlers import verify_app_resource

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_registry(
                root,
                secret_file=resource_relative("prod0-main", "sub2api", "redis").replace(
                    "/redis.env", "/../otherapp/redis.env"
                ),
            )
            write_resource_secrets(root, include_redis=False)

            with patch("agentplane.domain.app.resource_handlers._live_database_evidence", return_value=None):
                payload = verify_app_resource(root, "prod0-main", "sub2api")

            self.assertFalse(payload["ok"])
            self.assertFalse(payload["checks"]["secret_files"]["ok"])
            self.assertEqual(["secret_files"], payload["failures"])
            self.assertEqual("app.resource.secret_file_scope", payload["checks"]["secret_files"]["findings"][0]["id"])

    def test_app_resource_refresh_ledger_updates_app_resource_projection_without_mutating_registry(self) -> None:
        from agentplane.cli.apps import handle_app_command

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_registry(root)
            write_resource_secrets(root)

            args = SimpleNamespace(
                app_surface="resource",
                app_resource_action="refresh-ledger",
                target="prod0-main",
                repo_root=str(root),
                write=True,
            )

            payload = handle_app_command(args)

            self.assertEqual("app", payload["command"])
            self.assertEqual("resource.refresh-ledger", payload["action"])
            self.assertEqual(1, payload["payload"]["counts"]["app_resources"])
            self.assertTrue(
                (root / "inventory" / "servers" / "prod0-main" / "ledgers" / "app_resources.json").is_file()
            )
            persisted_registry = json.loads(
                (root / "inventory" / "servers" / "prod0-main" / "app-resources.json").read_text(encoding="utf-8")
            )
            self.assertEqual("sub2api", persisted_registry["sub2api"]["owner_app"])
            persisted_inventory = json.loads(
                (root / "inventory" / "servers" / "prod0-main" / "inventory.json").read_text(encoding="utf-8")
            )
            self.assertEqual(1, persisted_inventory["object_ledgers"]["counts"]["app_resources"])

    def test_app_resource_help_lists_object_actions(self) -> None:
        result = run_cli("app", "resource", "--help")

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("search", result.stdout)
        self.assertIn("get", result.stdout)
        self.assertIn("verify", result.stdout)
        self.assertIn("refresh-ledger", result.stdout)
