import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from tests.app_resource_path_fixtures import resource_relative, resource_root


REPO_ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = None
    if cwd is None:
        repo_root: Path | None = None
        for idx, token in enumerate(args):
            if token == "--repo-root" and idx + 1 < len(args):
                repo_root = Path(args[idx + 1])
                break
            if token.startswith("--repo-root="):
                repo_root = Path(token.split("=", 1)[1])
                break
        if repo_root is not None:
            cwd = repo_root
            env = os.environ.copy()
            repo_path = str(REPO_ROOT)
            existing = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = repo_path if not existing else f"{repo_path}:{existing}"
    return subprocess.run(
        [sys.executable, "-m", "agentplane.cli", *args],
        cwd=cwd or REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def write_inventory(root: Path, *, projection_drift: bool = False) -> None:
    server_root = root / "inventory" / "servers" / "prod2-main"
    server_root.mkdir(parents=True, exist_ok=True)
    (server_root / "README.md").write_text("# prod2-main 摘要\n", encoding="utf-8")
    app_resource_summary = {
        "postgres": {
            "database": "sub2api_prod2",
            "user": "sub2api_prod2",
            "secret_file": resource_relative("prod2-main", "sub2api", "postgres"),
        },
        "redis": {
            "db": 1 if not projection_drift else 9,
            "key_prefix": "sub2api:",
            "secret_file": resource_relative("prod2-main", "sub2api", "redis"),
        },
        "minio": {
            "bucket": "prod2-sub2api",
            "access_key": "sub2api_prod2",
            "policy_name": "prod2-sub2api-rw",
            "policy_scope": "bucket-only",
            "isolation_level": "bucket-scoped-rw",
            "secret_file": resource_relative("prod2-main", "sub2api", "minio"),
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
    registry_file = root / "inventory" / "servers" / "prod2-main" / "app-resources.json"
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
                "database": "sub2api_prod2",
                "user": "sub2api_prod2",
            },
            "redis": {
                "db": 1,
                "key_prefix": "sub2api:",
            },
            "minio": {
                "bucket": "prod2-sub2api",
                "access_key": "sub2api_prod2",
                "policy_name": "prod2-sub2api-rw",
                "policy_scope": "bucket-only",
                "isolation_level": "bucket-scoped-rw",
            },
            "secret_files": [
                resource_relative("prod2-main", "sub2api", "postgres"),
                secret_file or resource_relative("prod2-main", "sub2api", "redis"),
                resource_relative("prod2-main", "sub2api", "minio"),
            ],
        }
    }
    registry_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_resource_secrets(root: Path, *, include_redis: bool = True) -> None:
    resource_dir = resource_root(root, "prod2-main", "sub2api")
    resource_dir.mkdir(parents=True, exist_ok=True)
    (resource_dir / "postgres.env").write_text(
        "PGHOST=postgres18-prod\nPGPORT=5432\nPGDATABASE=sub2api_prod2\nPGUSER=sub2api_prod2\nPGPASSWORD=secret\n",
        encoding="utf-8",
    )
    if include_redis:
        (resource_dir / "redis.env").write_text(
            "REDIS_HOST=redis7-prod\nREDIS_PORT=6379\nREDIS_PASSWORD=secret\nREDIS_DB=1\nREDIS_KEY_PREFIX=sub2api:\nREDIS_ENABLE_TLS=false\n",
            encoding="utf-8",
        )
    (resource_dir / "minio.env").write_text(
        "MINIO_BUCKET=prod2-sub2api\nMINIO_ACCESS_KEY=sub2api_prod2\nMINIO_SECRET_KEY=secret\n",
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
                        "contracts": {"prod2-main": "deploy/agentplane/contract.yaml"},
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

            result = run_cli("app", "resource", "search", "--target", "prod2-main", "--repo-root", str(root))

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

            result = run_cli("app", "resource", "get", "--target", "prod2-main", "--app", "sub2api", "--repo-root", str(root))

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("resource.get", payload["action"])
            self.assertEqual("sub2api", payload["payload"]["resource"]["app"])
            self.assertTrue(payload["payload"]["projection"]["found"])

    def test_app_resource_verify_reports_projection_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root, projection_drift=True)
            write_registry(root)
            write_resource_secrets(root)

            result = run_cli("app", "resource", "verify", "--target", "prod2-main", "--app", "sub2api", "--repo-root", str(root))

            self.assertEqual(result.returncode, 1, msg=result.stdout)
            payload = json.loads(result.stdout)
            self.assertEqual("resource.verify", payload["action"])
            self.assertFalse(payload["payload"]["ok"])
            self.assertEqual(["inventory_projection"], payload["payload"]["failures"])

    def test_app_resource_verify_ignores_legacy_tenant_truth_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_registry(root)
            registry_file = root / "inventory" / "servers" / "prod2-main" / "app-resources.json"
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

            verify = run_cli("app", "resource", "verify", "--target", "prod2-main", "--app", "sub2api", "--repo-root", str(root))
            search = run_cli("app", "resource", "search", "--target", "prod2-main", "--repo-root", str(root))

            self.assertEqual(verify.returncode, 0, msg=verify.stderr)
            verify_payload = json.loads(verify.stdout)
            self.assertTrue(verify_payload["payload"]["ok"])
            self.assertEqual("sub2api", verify_payload["payload"]["resource"]["owner_app"])
            expected_projection = verify_payload["payload"]["checks"]["inventory_projection"]["expected"]
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
                target="prod2-main",
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
            app_id = "chatgpt-register-v2"
            service_key = "chatgpt-register"
            write_catalog(root, app=app_id, service_key=service_key)
            write_inventory(root)
            write_resource_secrets(root)
            write_registry(root)
            registry_file = root / "inventory" / "servers" / "prod2-main" / "app-resources.json"
            registry_payload = json.loads(registry_file.read_text(encoding="utf-8"))
            registry_payload["legacy-chatgpt-register"] = registry_payload.pop("sub2api")
            registry_payload["legacy-chatgpt-register"]["owner_app"] = app_id
            registry_file.write_text(json.dumps(registry_payload, ensure_ascii=False, indent=2), encoding="utf-8")
            inventory_file = root / "inventory" / "servers" / "prod2-main" / "inventory.json"
            inventory_payload = json.loads(inventory_file.read_text(encoding="utf-8"))
            inventory_payload["services"] = {
                service_key: inventory_payload["services"].pop("sub2api"),
            }
            inventory_payload["services"][service_key]["app_resource_summary"]["redis"]["key_prefix"] = "sub2api:"
            inventory_file.write_text(json.dumps(inventory_payload, ensure_ascii=False, indent=2), encoding="utf-8")

            get = run_cli("app", "resource", "get", "--target", "prod2-main", "--app", app_id, "--repo-root", str(root))

            self.assertEqual(0, get.returncode, msg=get.stderr + get.stdout)
            payload = json.loads(get.stdout)
            self.assertEqual(app_id, payload["payload"]["resource"]["app"])
            self.assertEqual(app_id, payload["payload"]["resource"]["owner_app"])
            projection = payload["payload"]["projection"]
            self.assertEqual(service_key, projection["service_key"])


if __name__ == "__main__":
    unittest.main()
