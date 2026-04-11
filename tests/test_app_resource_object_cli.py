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


class AppResourceObjectCliTests(unittest.TestCase):
    def test_resource_registry_lists_declared_app_resources(self) -> None:
        from agentplane.domain.app.resource_registry import available_app_resources

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_registry(root)

            items = available_app_resources(root, "prod2-main")

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

            payload = get_app_resource(root, "prod2-main", "sub2api")

            self.assertEqual("sub2api", payload["resource"]["app"])
            self.assertEqual("sub2api", payload["declared"]["owner_app"])
            self.assertTrue(payload["projection"]["found"])
            self.assertEqual(1, payload["projection"]["app_resource_summary"]["redis"]["db"])
            self.assertEqual(
                [True, True, True],
                [item["exists"] for item in payload["secret_files"]],
            )

    def test_resource_verify_reports_projection_drift(self) -> None:
        from agentplane.domain.app.resource_handlers import verify_app_resource

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root, projection_drift=True)
            write_registry(root)
            write_resource_secrets(root)

            payload = verify_app_resource(root, "prod2-main", "sub2api")

            self.assertFalse(payload["ok"])
            self.assertTrue(payload["checks"]["secret_files"]["ok"])
            self.assertFalse(payload["checks"]["inventory_projection"]["ok"])
            self.assertEqual(["inventory_projection"], payload["failures"])

    def test_resource_verify_separates_ledger_fields_and_observation(self) -> None:
        from agentplane.domain.app.resource_handlers import verify_app_resource

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_registry(root)
            write_resource_secrets(root)

            payload = verify_app_resource(root, "prod2-main", "sub2api")

            self.assertTrue(payload["ok"])
            self.assertEqual("targets/prod2-main/app-resources/sub2api", payload["canonical_ref"])
            self.assertEqual("targets/prod2-main/app-resources/sub2api", payload["ledger_fields"]["canonical_ref"])
            self.assertEqual("sub2api", payload["ledger_fields"]["app"])
            self.assertNotIn("declared", payload["ledger_fields"])
            self.assertIn("declared", payload["verification_fields"])
            self.assertIn("projection", payload["verification_fields"])
            self.assertIn("secret_files", payload["verification_fields"])

    def test_resource_verify_reports_secret_scope_and_missing_file_findings(self) -> None:
        from agentplane.domain.app.resource_handlers import verify_app_resource

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_registry(
                root,
                secret_file=resource_relative("prod2-main", "sub2api", "redis").replace(
                    "/redis.env", "/../otherapp/redis.env"
                ),
            )
            write_resource_secrets(root, include_redis=False)

            payload = verify_app_resource(root, "prod2-main", "sub2api")

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
                target="prod2-main",
                repo_root=str(root),
                write=True,
            )

            payload = handle_app_command(args)

            self.assertEqual("app", payload["command"])
            self.assertEqual("resource.refresh-ledger", payload["action"])
            self.assertEqual(1, payload["payload"]["counts"]["app_resources"])
            self.assertTrue((root / "inventory" / "servers" / "prod2-main" / "ledgers" / "app_resources.json").is_file())
            persisted_registry = json.loads(
                (root / "inventory" / "servers" / "prod2-main" / "app-resources.json").read_text(encoding="utf-8")
            )
            self.assertEqual("sub2api", persisted_registry["sub2api"]["owner_app"])
            persisted_inventory = json.loads(
                (root / "inventory" / "servers" / "prod2-main" / "inventory.json").read_text(encoding="utf-8")
            )
            self.assertEqual(1, persisted_inventory["object_ledgers"]["counts"]["app_resources"])

    def test_app_resource_help_lists_object_actions(self) -> None:
        result = run_cli("app", "resource", "--help")

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("search", result.stdout)
        self.assertIn("get", result.stdout)
        self.assertIn("verify", result.stdout)
        self.assertIn("refresh-ledger", result.stdout)


if __name__ == "__main__":
    unittest.main()
