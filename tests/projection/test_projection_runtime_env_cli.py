import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.support.app_resources import resource_relative, resource_root


REPO_ROOT = Path(__file__).resolve().parents[2]


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


def write_inventory(root: Path) -> None:
    inventory_file = root / "inventory" / "servers" / "prod2-main" / "inventory.json"
    inventory_file.parent.mkdir(parents=True, exist_ok=True)
    inventory_file.write_text(
        json.dumps(
            {
                "services": {
                    "sub2api": {
                        "control_plane": "compose",
                        "container_name": "sub2api-prod",
                    }
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def write_registry(root: Path) -> None:
    registry_file = root / "inventory" / "servers" / "prod2-main" / "app-resources.json"
    registry_file.parent.mkdir(parents=True, exist_ok=True)
    registry_file.write_text(
        json.dumps(
            {
                "sub2api": {
                    "owner_app": "sub2api",
                    "postgres": {"database": "sub2api_prod2", "user": "sub2api_prod2"},
                    "redis": {"db": 1, "key_prefix": "sub2api:"},
                    "secret_files": [
                        resource_relative("prod2-main", "sub2api", "postgres"),
                        resource_relative("prod2-main", "sub2api", "redis"),
                    ],
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def write_resource_secrets(root: Path) -> None:
    resource_dir = resource_root(root, "prod2-main", "sub2api")
    resource_dir.mkdir(parents=True, exist_ok=True)
    (resource_dir / "postgres.env").write_text(
        "PGHOST=postgres18-prod\nPGPORT=5432\nPGDATABASE=sub2api_prod2\nPGUSER=sub2api_prod2\nPGPASSWORD=secret\nPGSSLMODE=disable\n",
        encoding="utf-8",
    )
    (resource_dir / "redis.env").write_text(
        "REDIS_HOST=redis7-prod\nREDIS_PORT=6379\nREDIS_PASSWORD=secret\nREDIS_DB=1\nREDIS_KEY_PREFIX=sub2api:\nREDIS_ENABLE_TLS=false\n",
        encoding="utf-8",
    )


class ProjectionRuntimeEnvCliTests(unittest.TestCase):
    def test_runtime_env_plan_reports_missing_app_as_app_resource_registry_gap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_registry(root)
            write_resource_secrets(root)

            result = run_cli(
                "projection",
                "runtime-env",
                "plan",
                "--target",
                "prod2-main",
                "--app",
                "newapi",
                "--repo-root",
                str(root),
            )

            self.assertNotEqual(result.returncode, 0)
            payload = json.loads(result.stdout)
            self.assertEqual("projection", payload["command"])
            self.assertEqual("runtime-env.plan", payload["action"])
            self.assertFalse(payload["ok"])
            self.assertEqual("app.resource.registry_missing_app", payload["error"]["id"])

    def test_runtime_env_plan_returns_target_env_file_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_registry(root)
            write_resource_secrets(root)

            result = run_cli(
                "projection",
                "runtime-env",
                "plan",
                "--target",
                "prod2-main",
                "--app",
                "sub2api",
                "--repo-root",
                str(root),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("projection", payload["command"])
            self.assertEqual("runtime-env.plan", payload["action"])
            self.assertEqual(str(root / "secrets" / "services" / "sub2api.prod2.env"), payload["env_file"])
            self.assertFalse(payload["written"])
            self.assertIn("DATABASE_USER", payload["managed_keys"])
            self.assertNotIn("rendered_env", payload)
            self.assertNotIn("current_env", payload)
            self.assertNotIn("PGPASSWORD=secret", result.stdout)
            self.assertNotIn("REDIS_PASSWORD=secret", result.stdout)
            self.assertFalse((root / "secrets" / "services" / "sub2api.prod2.env").exists())

            revealed = run_cli(
                "projection",
                "runtime-env",
                "plan",
                "--target",
                "prod2-main",
                "--app",
                "sub2api",
                "--repo-root",
                str(root),
                "--reveal-secrets",
            )

            self.assertEqual(revealed.returncode, 0, msg=revealed.stderr)
            revealed_payload = json.loads(revealed.stdout)
            self.assertIn("rendered_env", revealed_payload)
            self.assertIn("DATABASE_PASSWORD=secret", revealed_payload["rendered_env"])
            self.assertIn("REDIS_PASSWORD=secret", revealed_payload["rendered_env"])

    def test_runtime_env_verify_reports_missing_env_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_registry(root)
            write_resource_secrets(root)

            result = run_cli(
                "projection",
                "runtime-env",
                "verify",
                "--target",
                "prod2-main",
                "--app",
                "sub2api",
                "--repo-root",
                str(root),
            )

            self.assertNotEqual(result.returncode, 0)
            payload = json.loads(result.stdout)
            self.assertEqual("projection", payload["command"])
            self.assertEqual("runtime-env.verify", payload["action"])
            self.assertFalse(payload["ok"])
            self.assertEqual("projection.runtime_env_missing", payload["error"]["id"])

    def test_runtime_env_verify_reports_managed_key_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_registry(root)
            write_resource_secrets(root)
            env_file = root / "secrets" / "services" / "sub2api.prod2.env"
            env_file.parent.mkdir(parents=True, exist_ok=True)
            env_file.write_text(
                "DATABASE_USER=sub2api_prod2\nDATABASE_DBNAME=sub2api_prod2\nREDIS_PASSWORD=secret\nREDIS_DB=9\nJWT_SECRET=keep\n",
                encoding="utf-8",
            )

            result = run_cli(
                "projection",
                "runtime-env",
                "verify",
                "--target",
                "prod2-main",
                "--app",
                "sub2api",
                "--repo-root",
                str(root),
            )

            self.assertNotEqual(result.returncode, 0)
            payload = json.loads(result.stdout)
            self.assertEqual("projection", payload["command"])
            self.assertEqual("runtime-env.verify", payload["action"])
            self.assertFalse(payload["ok"])
            self.assertEqual("projection.runtime_env_drift", payload["error"]["id"])
            self.assertIn("REDIS_DB", payload["drift"]["managed_keys"])
            self.assertNotIn("expected", payload["drift"])
            self.assertNotIn("actual", payload["drift"])
            self.assertIn("expected_redacted", payload["drift"])
            self.assertIn("actual_redacted", payload["drift"])
            self.assertIn("REDIS_PASSWORD=<redacted>", payload["drift"]["actual_redacted"])
            self.assertIn("JWT_SECRET=<redacted>", payload["drift"]["actual_redacted"])
            self.assertNotIn("REDIS_PASSWORD=secret", result.stdout)
            self.assertNotIn("JWT_SECRET=keep", result.stdout)


if __name__ == "__main__":
    unittest.main()

