from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pytest
from tests.support.app_delivery_cli import run_app_delivery_cli
from tests.support.app_delivery_contracts import (
    ERROR_ID_TENANT_REGISTRY_MISMATCH,
    ERROR_ID_TENANT_RESOURCES_REQUIRED,
    ERROR_ID_TENANT_SECRET_FILE_MISSING,
    ERROR_ID_TENANT_SECRET_FILE_SCOPE,
    write_contract,
)
from tests.support.app_delivery_targets import (
    baseline_app_resource_registry_payload,
    baseline_tenant_resources,
    write_app_resource_registry,
    write_inventory,
    write_tenant_secret_files,
)
from tests.support.app_resources import resource_relative, resource_root

pytestmark = pytest.mark.integration


class TestAppDeliveryValidateResourcesCliTests(unittest.TestCase):
    def test_validate_contract_tenant_requires_tenant_resources_for_infra_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_app_resource_registry(root, baseline_app_resource_registry_payload())
            write_contract(root)

            result = run_app_delivery_cli("validate-contract", repo_root=root, app="sub2api")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(ERROR_ID_TENANT_RESOURCES_REQUIRED, result.stdout + result.stderr)

    def test_validate_contract_tenant_requires_tenant_resources_even_when_registry_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            # Intentionally do NOT write inventory/servers/<target>/app-resources.json.
            # Even without a tenant registry, contracts that depend on shared infra
            # (PG/Redis/MinIO) must still declare infra.tenant_resources.
            write_contract(root)

            result = run_app_delivery_cli("validate-contract", repo_root=root, app="sub2api")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(ERROR_ID_TENANT_RESOURCES_REQUIRED, result.stdout + result.stderr)

    def test_validate_contract_tenant_rejects_cross_app_secret_file_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_app_resource_registry(root, baseline_app_resource_registry_payload())
            # Ensure the referenced secret files exist so the test is stable against
            # future validation ordering (we want to lock in the scope error).
            bad_pg = resource_root(root, "prod0-main", "sampleapi") / "postgres.env"
            bad_pg.parent.mkdir(parents=True, exist_ok=True)
            bad_pg.write_text("PGDATABASE=sub2api_prod0\nPGUSER=sub2api_prod0\n", encoding="utf-8")
            bad_redis = resource_root(root, "prod0-main", "sampleapi") / "redis.env"
            bad_redis.parent.mkdir(parents=True, exist_ok=True)
            bad_redis.write_text("REDIS_USER=sub2api_prod0\nREDIS_DB=1\nREDIS_KEY_PREFIX=sub2api:\n", encoding="utf-8")
            write_contract(
                root,
                tenant_resources={
                    "postgres": {
                        "required": True,
                        "database": "sub2api_prod0",
                        "user": "sub2api_prod0",
                        "secret_file": resource_relative("prod0-main", "sampleapi", "postgres"),
                    },
                    "redis": {
                        "required": True,
                        "user": "sub2api_prod0",
                        "db": 1,
                        "key_prefix": "sub2api:",
                        "secret_file": resource_relative("prod0-main", "sampleapi", "redis"),
                    },
                },
            )

            result = run_app_delivery_cli("validate-contract", repo_root=root, app="sub2api")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(ERROR_ID_TENANT_SECRET_FILE_SCOPE, result.stdout + result.stderr)

    def test_validate_contract_rejects_registry_secret_file_scope_before_deploy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            registry_payload = baseline_app_resource_registry_payload()
            registry_payload["sub2api"]["secret_files"] = [
                resource_relative("prod0-main", "sampleapi", "postgres"),
                resource_relative("prod0-main", "sampleapi", "redis"),
            ]
            write_app_resource_registry(root, registry_payload)
            write_tenant_secret_files(root)
            write_contract(root, tenant_resources=baseline_tenant_resources())

            result = run_app_delivery_cli("validate-contract", repo_root=root, app="sub2api")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(ERROR_ID_TENANT_SECRET_FILE_SCOPE, result.stdout + result.stderr)

    def test_validate_contract_tenant_rejects_missing_tenant_secret_file_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_app_resource_registry(root, baseline_app_resource_registry_payload())
            # The secret_file path is in-scope but the file is intentionally missing.
            # This must fail on the contract side (app validate-contract), not only on
            # app resource verify / host audit.
            write_contract(
                root,
                tenant_resources={
                    "postgres": {
                        "required": True,
                        "database": "sub2api_prod0",
                        "user": "sub2api_prod0",
                        "secret_file": resource_relative("prod0-main", "sub2api", "postgres"),
                    },
                    "redis": {
                        "required": True,
                        "user": "sub2api_prod0",
                        "db": 1,
                        "key_prefix": "sub2api:",
                        "secret_file": resource_relative("prod0-main", "sub2api", "redis"),
                    },
                },
            )

            result = run_app_delivery_cli("validate-contract", repo_root=root, app="sub2api")

            self.assertNotEqual(result.returncode, 0)
            combined = result.stdout + result.stderr
            # Lock on stable error ids instead of brittle message fragments.
            self.assertIn(ERROR_ID_TENANT_SECRET_FILE_MISSING, combined)
            self.assertIn(resource_relative("prod0-main", "sub2api", "postgres"), combined)
            # When validate emits JSON, prefer schema-level assertions.
            try:
                payload = json.loads(result.stdout)
            except json.JSONDecodeError:
                payload = None
            if isinstance(payload, dict):
                items = payload.get("errors") or payload.get("violations") or payload.get("findings") or []
                if isinstance(items, list):
                    ids = {item.get("id") for item in items if isinstance(item, dict)}
                    self.assertIn(ERROR_ID_TENANT_SECRET_FILE_MISSING, ids)

    def test_validate_contract_tenant_rejects_secret_file_path_traversal_outside_scoped_app_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_app_resource_registry(root, baseline_app_resource_registry_payload())
            # Ensure referenced secret files exist so the test is stable against future
            # validation ordering (we want to lock in the scope error, not missing-file
            # preconditions).
            redis = resource_root(root, "prod0-main", "sub2api") / "redis.env"
            redis.parent.mkdir(parents=True, exist_ok=True)
            redis.write_text("REDIS_USER=sub2api_prod0\nREDIS_DB=1\nREDIS_KEY_PREFIX=sub2api:\n", encoding="utf-8")
            # Create the file that the traversal path would resolve to, so the check
            # cannot be a naive startswith(prefix) + exists(path) against the raw string.
            escaped_pg = resource_root(root, "prod0-main", "sampleapi") / "postgres.env"
            escaped_pg.parent.mkdir(parents=True, exist_ok=True)
            escaped_pg.write_text("PGDATABASE=sub2api_prod0\nPGUSER=sub2api_prod0\n", encoding="utf-8")
            write_contract(
                root,
                tenant_resources={
                    "postgres": {
                        "required": True,
                        "database": "sub2api_prod0",
                        "user": "sub2api_prod0",
                        # Looks in-scope by prefix, but escapes the app directory after normalization.
                        "secret_file": resource_relative("prod0-main", "sub2api", "postgres").replace(
                            "/postgres.env", "/../sampleapi/postgres.env"
                        ),
                    },
                    "redis": {
                        "required": True,
                        "user": "sub2api_prod0",
                        "db": 1,
                        "key_prefix": "sub2api:",
                        "secret_file": resource_relative("prod0-main", "sub2api", "redis"),
                    },
                },
            )

            result = run_app_delivery_cli("validate-contract", repo_root=root, app="sub2api")

            self.assertNotEqual(result.returncode, 0)
            combined = result.stdout + result.stderr
            # Keep the existing scope error id contract-side as well.
            self.assertIn(ERROR_ID_TENANT_SECRET_FILE_SCOPE, combined)
            self.assertIn(
                resource_relative("prod0-main", "sub2api", "postgres").replace(
                    "/postgres.env", "/../sampleapi/postgres.env"
                ),
                combined,
            )
            # When validate emits JSON, prefer schema-level assertions.
            try:
                payload = json.loads(result.stdout)
            except json.JSONDecodeError:
                payload = None
            if isinstance(payload, dict):
                items = payload.get("errors") or payload.get("violations") or payload.get("findings") or []
                if isinstance(items, list):
                    ids = {item.get("id") for item in items if isinstance(item, dict)}
                    self.assertIn(ERROR_ID_TENANT_SECRET_FILE_SCOPE, ids)

    def test_validate_contract_tenant_requires_minio_tenant_resource_when_contract_declares_minio_dependency(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_app_resource_registry(root, baseline_app_resource_registry_payload())
            # Ensure tenant secret files exist so the failure is stable and about missing
            # tenant_resources.minio (not secret-file preconditions).
            pg = resource_root(root, "prod0-main", "sub2api") / "postgres.env"
            pg.parent.mkdir(parents=True, exist_ok=True)
            pg.write_text("PGDATABASE=sub2api_prod0\nPGUSER=sub2api_prod0\n", encoding="utf-8")
            redis = resource_root(root, "prod0-main", "sub2api") / "redis.env"
            redis.parent.mkdir(parents=True, exist_ok=True)
            redis.write_text("REDIS_USER=sub2api_prod0\nREDIS_DB=1\nREDIS_KEY_PREFIX=sub2api:\n", encoding="utf-8")
            write_contract(
                root,
                dependencies=["postgres18-prod", "redis7-prod", "minio-prod"],
                tenant_resources={
                    "postgres": {
                        "required": True,
                        "database": "sub2api_prod0",
                        "user": "sub2api_prod0",
                        "secret_file": resource_relative("prod0-main", "sub2api", "postgres"),
                    },
                    "redis": {
                        "required": True,
                        "user": "sub2api_prod0",
                        "db": 1,
                        "key_prefix": "sub2api:",
                        "secret_file": resource_relative("prod0-main", "sub2api", "redis"),
                    },
                },
            )

            result = run_app_delivery_cli("validate-contract", repo_root=root, app="sub2api")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(ERROR_ID_TENANT_RESOURCES_REQUIRED, result.stdout + result.stderr)

    def test_validate_contract_tenant_rejects_cross_app_minio_secret_file_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_app_resource_registry(root, baseline_app_resource_registry_payload())
            # Ensure the referenced secret files exist so the test is stable against
            # future validation ordering (we want to lock in the scope error).
            pg = resource_root(root, "prod0-main", "sub2api") / "postgres.env"
            pg.parent.mkdir(parents=True, exist_ok=True)
            pg.write_text("PGDATABASE=sub2api_prod0\nPGUSER=sub2api_prod0\n", encoding="utf-8")
            redis = resource_root(root, "prod0-main", "sub2api") / "redis.env"
            redis.parent.mkdir(parents=True, exist_ok=True)
            redis.write_text("REDIS_USER=sub2api_prod0\nREDIS_DB=1\nREDIS_KEY_PREFIX=sub2api:\n", encoding="utf-8")
            bad_minio = root / "secrets" / "app-resources" / "prod0-main" / "sampleapi" / "minio.env"
            bad_minio.parent.mkdir(parents=True, exist_ok=True)
            bad_minio.write_text(
                "S3_BUCKET=prod0-sub2api\nS3_ACCESS_KEY=sub2api_prod0\nS3_SECRET_KEY=sub2api-s3-secret\n",
                encoding="utf-8",
            )
            write_contract(
                root,
                tenant_resources={
                    "postgres": {
                        "required": True,
                        "database": "sub2api_prod0",
                        "user": "sub2api_prod0",
                        "secret_file": resource_relative("prod0-main", "sub2api", "postgres"),
                    },
                    "redis": {
                        "required": True,
                        "user": "sub2api_prod0",
                        "db": 1,
                        "key_prefix": "sub2api:",
                        "secret_file": resource_relative("prod0-main", "sub2api", "redis"),
                    },
                    "minio": {
                        "required": True,
                        "bucket": "prod0-sub2api",
                        "access_key": "sub2api_prod0",
                        "secret_file": resource_relative("prod0-main", "sampleapi", "minio"),
                    },
                },
            )

            result = run_app_delivery_cli("validate-contract", repo_root=root, app="sub2api")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(ERROR_ID_TENANT_SECRET_FILE_SCOPE, result.stdout + result.stderr)

    def test_validate_contract_tenant_rejects_minio_names_mismatched_with_registry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_app_resource_registry(root, baseline_app_resource_registry_payload())
            # Ensure the referenced secret files exist so the test is stable against
            # future validation ordering (we want to lock in the registry mismatch error).
            pg = resource_root(root, "prod0-main", "sub2api") / "postgres.env"
            pg.parent.mkdir(parents=True, exist_ok=True)
            pg.write_text("PGDATABASE=sub2api_prod0\nPGUSER=sub2api_prod0\n", encoding="utf-8")
            redis = resource_root(root, "prod0-main", "sub2api") / "redis.env"
            redis.parent.mkdir(parents=True, exist_ok=True)
            redis.write_text("REDIS_USER=sub2api_prod0\nREDIS_DB=1\nREDIS_KEY_PREFIX=sub2api:\n", encoding="utf-8")
            minio = resource_root(root, "prod0-main", "sub2api") / "minio.env"
            minio.parent.mkdir(parents=True, exist_ok=True)
            minio.write_text(
                "S3_BUCKET=prod0-sub2api\nS3_ACCESS_KEY=sub2api_prod0\nS3_SECRET_KEY=sub2api-s3-secret\n",
                encoding="utf-8",
            )
            write_contract(
                root,
                tenant_resources={
                    "postgres": {
                        "required": True,
                        "database": "sub2api_prod0",
                        "user": "sub2api_prod0",
                        "secret_file": resource_relative("prod0-main", "sub2api", "postgres"),
                    },
                    "redis": {
                        "required": True,
                        "user": "sub2api_prod0",
                        "db": 1,
                        "key_prefix": "sub2api:",
                        "secret_file": resource_relative("prod0-main", "sub2api", "redis"),
                    },
                    "minio": {
                        "required": True,
                        "bucket": "prod0-sub2api-wrong",
                        "access_key": "sub2api_prod0",
                        "secret_file": resource_relative("prod0-main", "sub2api", "minio"),
                    },
                },
            )

            result = run_app_delivery_cli("validate-contract", repo_root=root, app="sub2api")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(ERROR_ID_TENANT_REGISTRY_MISMATCH, result.stdout + result.stderr)

    def test_validate_contract_tenant_rejects_names_mismatched_with_registry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_app_resource_registry(root, baseline_app_resource_registry_payload())
            # Ensure the referenced secret files exist so the test is stable against
            # future validation ordering (we want to lock in the registry mismatch error).
            pg = resource_root(root, "prod0-main", "sub2api") / "postgres.env"
            pg.parent.mkdir(parents=True, exist_ok=True)
            pg.write_text("PGDATABASE=sub2api_prod0\nPGUSER=sub2api_prod0\n", encoding="utf-8")
            redis = resource_root(root, "prod0-main", "sub2api") / "redis.env"
            redis.parent.mkdir(parents=True, exist_ok=True)
            redis.write_text("REDIS_USER=sub2api_prod0\nREDIS_DB=1\nREDIS_KEY_PREFIX=sub2api:\n", encoding="utf-8")
            write_contract(
                root,
                tenant_resources={
                    "postgres": {
                        "required": True,
                        "database": "sub2api_wrong_db",
                        "user": "sub2api_prod0",
                        "secret_file": resource_relative("prod0-main", "sub2api", "postgres"),
                    },
                    "redis": {
                        "required": True,
                        "user": "sub2api_wrong_user",
                        "db": 1,
                        "key_prefix": "sub2api:",
                        "secret_file": resource_relative("prod0-main", "sub2api", "redis"),
                    },
                },
            )

            result = run_app_delivery_cli("validate-contract", repo_root=root, app="sub2api")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(ERROR_ID_TENANT_REGISTRY_MISMATCH, result.stdout + result.stderr)

    def test_delivery_actions_fail_on_registry_truth_drift_before_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_tenant_secret_files(root)
            registry_payload = baseline_app_resource_registry_payload()
            registry_payload["sub2api"]["postgres"]["database"] = "sub2api_wrong"
            write_app_resource_registry(root, registry_payload)
            write_contract(root, tenant_resources=baseline_tenant_resources())

            inventory_file = root / "inventory" / "servers" / "prod0-main" / "inventory.json"
            inventory_before = inventory_file.read_text(encoding="utf-8")
            server_readme = root / "inventory" / "servers" / "prod0-main" / "README.md"
            app_summary = root / "docs" / "AGENTPLANE_DEPLOYMENT.md"
            ledger_root = root / "tmp" / "operation-ledger"
            actions = {
                "validate-contract": (),
                "render-runtime": (),
                "deploy": ("--image-ref", "sub2api-prod:test", "--dry-run"),
                "verify": ("--dry-run",),
                "rollback": ("--dry-run",),
                "inventory-refresh": ("--write",),
            }

            for action, extra_args in actions.items():
                with self.subTest(action=action):
                    result = run_app_delivery_cli(action, repo_root=root, app="sub2api", extra_args=extra_args)

                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(ERROR_ID_TENANT_REGISTRY_MISMATCH, result.stdout + result.stderr)
                    self.assertEqual(inventory_before, inventory_file.read_text(encoding="utf-8"))
                    self.assertFalse(server_readme.exists())
                    self.assertFalse(app_summary.exists())
                    self.assertFalse(ledger_root.exists())

    def test_deploy_rejects_secret_scope_before_planning_steps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_app_resource_registry(root, baseline_app_resource_registry_payload())
            bad_pg = resource_root(root, "prod0-main", "sampleapi") / "postgres.env"
            bad_pg.parent.mkdir(parents=True, exist_ok=True)
            bad_pg.write_text("PGDATABASE=sub2api_prod0\nPGUSER=sub2api_prod0\n", encoding="utf-8")
            bad_redis = resource_root(root, "prod0-main", "sampleapi") / "redis.env"
            bad_redis.write_text("REDIS_DB=1\nREDIS_KEY_PREFIX=sub2api:\n", encoding="utf-8")
            write_contract(
                root,
                tenant_resources={
                    "postgres": {
                        "required": True,
                        "database": "sub2api_prod0",
                        "user": "sub2api_prod0",
                        "secret_file": resource_relative("prod0-main", "sampleapi", "postgres"),
                    },
                    "redis": {
                        "required": True,
                        "db": 1,
                        "key_prefix": "sub2api:",
                        "secret_file": resource_relative("prod0-main", "sampleapi", "redis"),
                    },
                },
            )

            result = run_app_delivery_cli(
                "deploy",
                repo_root=root,
                app="sub2api",
                extra_args=("--image-ref", "sub2api-prod:test", "--dry-run"),
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(ERROR_ID_TENANT_SECRET_FILE_SCOPE, result.stdout + result.stderr)
            self.assertFalse((root / "tmp" / "operation-ledger").exists())


# ======================================================================
# From: test_app_delivery_doc_sync_cli.py
# ======================================================================


