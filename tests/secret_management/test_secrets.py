from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import pytest
from agentplane.cli.secrets import materialize_legacy_host_layout
from agentplane.runtime.bootstrap import bootstrap_directory_specs, bootstrap_required_truth_specs

pytestmark = pytest.mark.e2e

REPO_ROOT = Path(__file__).resolve().parents[2]

def run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "agentplane.cli", *args],
        cwd=cwd or REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

def parse_env_text(content: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value
    return values

class SecretsCliTests(unittest.TestCase):
    def test_init_data_services_generates_target_scoped_random_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            result = run_cli("infra", "secrets", "init-data-services", "prod0-main", "--repo-root", str(root))
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual({"command", "action", "target", "payload"}, set(payload))
            self.assertEqual("infra", payload.get("command"))
            self.assertEqual("secrets.init-data-services", payload.get("action"))
            self.assertEqual("prod0-main", payload.get("target"))
            self.assertIn("files", payload["payload"])

            postgres_file = root / "secrets" / "services" / "postgres" / "admin.prod0.env"
            redis_file = root / "secrets" / "services" / "redis" / "admin.prod0.conf"
            minio_file = root / "secrets" / "services" / "minio" / "admin.prod0.env"

            self.assertTrue(postgres_file.is_file())
            self.assertTrue(redis_file.is_file())
            self.assertTrue(minio_file.is_file())
            self.assertFalse((root / "secrets" / "services" / "postgres.env").exists())
            self.assertFalse((root / "secrets" / "services" / "redis.conf").exists())
            self.assertFalse((root / "secrets" / "services" / "minio.env").exists())

            postgres_values = parse_env_text(postgres_file.read_text(encoding="utf-8"))
            self.assertEqual("postgres", postgres_values["POSTGRES_DB"])
            self.assertEqual("postgres", postgres_values["POSTGRES_USER"])
            self.assertRegex(postgres_values["POSTGRES_PASSWORD"], r"^[0-9a-f]{32}$")

            redis_text = redis_file.read_text(encoding="utf-8")
            self.assertIn("requirepass ", redis_text)
            self.assertRegex(redis_text, r"requirepass [0-9a-f]{32}")

            minio_values = parse_env_text(minio_file.read_text(encoding="utf-8"))
            self.assertRegex(minio_values["MINIO_ROOT_USER"], r"^minioadmin_[a-z0-9]+_[0-9a-f]{8}$")
            self.assertRegex(minio_values["MINIO_ROOT_PASSWORD"], r"^[0-9a-f]{32}$")

    def test_init_data_services_keeps_existing_files_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            postgres_file = root / "secrets" / "services" / "postgres" / "admin.wsl.env"
            postgres_file.parent.mkdir(parents=True, exist_ok=True)
            postgres_file.write_text(
                "POSTGRES_DB=postgres\nPOSTGRES_USER=existing_user\nPOSTGRES_PASSWORD=existing_password\n",
                encoding="utf-8",
            )

            result = run_cli("infra", "secrets", "init-data-services", "wsl", "--repo-root", str(root))
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual({"command", "action", "target", "payload"}, set(payload))
            self.assertEqual("infra", payload.get("command"))
            self.assertEqual("secrets.init-data-services", payload.get("action"))
            self.assertEqual("wsl", payload.get("target"))
            statuses = {item["path"]: item["status"] for item in payload["payload"]["files"]}
            self.assertEqual("kept", statuses[str(postgres_file)])

            postgres_values = parse_env_text(postgres_file.read_text(encoding="utf-8"))
            self.assertEqual("existing_user", postgres_values["POSTGRES_USER"])
            self.assertEqual("existing_password", postgres_values["POSTGRES_PASSWORD"])

    def test_sync_layout_projects_backup_env_to_legacy_path_with_host_first_source_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            host_root = root / "secrets" / "hosts" / "wsl" / "automations"
            host_root.mkdir(parents=True, exist_ok=True)
            (host_root / "secrets-backup.r2.env").write_text(
                "SECRETS_BACKUP_SOURCE_DIR=/tmp/legacy-override\n"
                "SECRETS_BACKUP_ENDPOINT=https://example.r2.cloudflarestorage.com\n",
                encoding="utf-8",
            )

            result = run_cli("infra", "secrets", "sync-layout", "wsl", "--write", "--repo-root", str(root))
            self.assertEqual(result.returncode, 0, msg=result.stderr)

            projected = root / "secrets" / "services" / "secrets-backup.r2.wsl.env"
            self.assertTrue(projected.is_file())
            self.assertIn(
                f"SECRETS_BACKUP_SOURCE_DIR={root}/secrets/hosts/wsl",
                projected.read_text(encoding="utf-8"),
            )

class SecretLayoutTests(unittest.TestCase):
    def test_compose_and_deploy_scripts_use_target_scoped_secret_paths(self) -> None:
        files_and_expected = {
            REPO_ROOT / "infra" / "compose" / "postgres" / "docker-compose.wsl.yml": "secrets/services/postgres/admin.wsl.env",
            REPO_ROOT / "infra" / "compose" / "redis" / "docker-compose.wsl.yml": "secrets/services/redis/admin.wsl.conf",
            REPO_ROOT / "infra" / "compose" / "minio" / "docker-compose.wsl.yml": "secrets/services/minio/admin.wsl.env",
            REPO_ROOT / "agentplane" / "scripts" / "remote" / "deploy_data_services_to_host.sh": "secrets/services/postgres/admin.${target_alias}.env",
            REPO_ROOT / "agentplane" / "scripts" / "remote" / "remote_deploy_data_services.sh": 'postgres_env="${control_root}/secrets/services/postgres/admin.${target_alias}.env"',
        }
        for path, expected in files_and_expected.items():
            with self.subTest(path=str(path)):
                self.assertIn(expected, path.read_text(encoding="utf-8"))

    def test_data_service_deploy_scripts_pin_canonical_compose_file_names(self) -> None:
        local_script = (REPO_ROOT / "agentplane" / "scripts" / "remote" / "deploy_data_services_to_host.sh").read_text(
            encoding="utf-8"
        )
        remote_script = (REPO_ROOT / "agentplane" / "scripts" / "remote" / "remote_deploy_data_services.sh").read_text(
            encoding="utf-8"
        )

        for compose_name in ("docker-compose.prod0.yml",):
            with self.subTest(compose_name=compose_name):
                self.assertIn(compose_name, local_script)
                self.assertIn(compose_name, remote_script)

    def test_remote_bash_wrapper_is_removed(self) -> None:
        wrapper = REPO_ROOT / "agentplane" / "scripts" / "remote" / "run_remote_bash.sh"
        self.assertFalse(wrapper.exists(), msg=f"removed compatibility wrapper still exists: {wrapper}")

    def test_data_service_deploy_scripts_use_unique_remote_staging_root(self) -> None:
        local_script = (REPO_ROOT / "agentplane" / "scripts" / "remote" / "deploy_data_services_to_host.sh").read_text(
            encoding="utf-8"
        )
        remote_script = (REPO_ROOT / "agentplane" / "scripts" / "remote" / "remote_deploy_data_services.sh").read_text(
            encoding="utf-8"
        )

        self.assertIn("/tmp/oplinux/", local_script)
        self.assertIn("op_id", local_script)
        self.assertNotIn("/tmp/env_ubuntu_deploy", local_script)
        self.assertIn('stage_root="${1:?stage_root is required}"', remote_script)
        self.assertNotIn("/tmp/env_ubuntu_deploy", remote_script)

    def test_service_templates_do_not_ship_real_default_credentials(self) -> None:
        postgres_template = (REPO_ROOT / "templates" / "services" / "postgres.env.example").read_text(encoding="utf-8")
        redis_template = (REPO_ROOT / "templates" / "services" / "redis.conf.example").read_text(encoding="utf-8")
        minio_template = (REPO_ROOT / "templates" / "services" / "minio.env.example").read_text(encoding="utf-8")

        self.assertIn("replace-with-postgres-user", postgres_template)
        self.assertIn("replace-with-postgres-password", postgres_template)
        self.assertNotIn("POSTGRES_PASSWORD=postgres", postgres_template)
        self.assertIn("replace-with-redis-password", redis_template)
        self.assertIn("replace-with-root-user", minio_template)
        self.assertIn("replace-with-strong-password", minio_template)

    def test_service_templates_expose_canonical_admin_examples_and_mark_flat_files_as_transitional(self) -> None:
        canonical_admin_templates = {
            "postgres": REPO_ROOT / "templates" / "services" / "postgres" / "admin.env.example",
            "redis": REPO_ROOT / "templates" / "services" / "redis" / "admin.env.example",
            "minio": REPO_ROOT / "templates" / "services" / "minio" / "admin.env.example",
        }
        for service, path in canonical_admin_templates.items():
            with self.subTest(service=service):
                self.assertTrue(path.is_file(), msg=f"missing canonical admin template: {path}")

        postgres_admin = canonical_admin_templates["postgres"].read_text(encoding="utf-8")
        redis_admin = canonical_admin_templates["redis"].read_text(encoding="utf-8")
        minio_admin = canonical_admin_templates["minio"].read_text(encoding="utf-8")

        self.assertIn("POSTGRES_DB=postgres", postgres_admin)
        self.assertIn("POSTGRES_USER=replace-with-postgres-user", postgres_admin)
        self.assertIn("POSTGRES_PASSWORD=replace-with-postgres-password", postgres_admin)
        self.assertIn("REDIS_PASSWORD=replace-with-redis-password", redis_admin)
        self.assertIn("MINIO_ROOT_USER=replace-with-root-user", minio_admin)
        self.assertIn("MINIO_ROOT_PASSWORD=replace-with-strong-password", minio_admin)

        flat_templates = {
            "postgres": REPO_ROOT / "templates" / "services" / "postgres.env.example",
            "redis": REPO_ROOT / "templates" / "services" / "redis.conf.example",
            "minio": REPO_ROOT / "templates" / "services" / "minio.env.example",
        }
        for service, path in flat_templates.items():
            with self.subTest(service=service):
                content = path.read_text(encoding="utf-8").lower()
                self.assertTrue(
                    any(marker in content for marker in ("legacy", "transitional", "projection-only", "projection only")),
                    msg=f"flat template must be explicitly marked transitional or projection-only: {path}",
                )

# ======================================================================
# From: test_secrets_backup_r2.py
# ======================================================================

class FakeR2Client:
    def __init__(self, existing: dict[str, bytes] | None = None, *, fail_put: bool = False) -> None:
        self.objects = dict(existing or {})
        self.fail_put = fail_put
        self.put_calls: list[str] = []
        self.delete_calls: list[str] = []

    def put_object(self, *, bucket: str, key: str, file_path: Path) -> dict[str, str]:
        self.put_calls.append(key)
        if self.fail_put:
            raise RuntimeError("put failed")
        self.objects[key] = file_path.read_bytes()
        return {"etag": "fake-etag", "bucket": bucket, "key": key}

    def list_objects(self, *, bucket: str, prefix: str) -> list[dict[str, object]]:
        return [
            {"key": key, "size": len(value)}
            for key, value in sorted(self.objects.items())
            if key.startswith(prefix)
        ]

    def delete_object(self, *, bucket: str, key: str) -> None:
        self.delete_calls.append(key)
        self.objects.pop(key, None)

def fake_encrypt_file(input_path: Path, output_path: Path, password: str) -> None:
    output_path.write_bytes(input_path.read_bytes() + f":{password}".encode("utf-8"))

class SecretsBackupR2Tests(unittest.TestCase):
    def _make_config(self, root: Path):
        from agentplane.scripts.automation.backup_secrets_r2 import BackupConfig

        return BackupConfig(
            source_dir=root / "secrets" / "hosts" / "wsl",
            state_file=root / "state" / "state.json",
            tmp_dir=root / "tmp",
            bucket="AgentPlane_Backups",
            endpoint="https://example.r2.cloudflarestorage.com",
            prefix="backups/agentplane/secrets-main",
            access_key_id="access",
            secret_access_key="secret",
            password="qf19940930",
            keep_count=5,
        )

    def test_backup_skips_upload_when_scan_fingerprint_matches_state(self) -> None:
        from agentplane.scripts.automation.backup_secrets_r2 import run_backup

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            secrets_dir = root / "secrets" / "hosts" / "wsl"
            secrets_dir.mkdir(parents=True)
            (secrets_dir / "alpha.txt").write_text("alpha\n", encoding="utf-8")

            config = self._make_config(root)
            client = FakeR2Client()

            first = run_backup(
                config,
                client=client,
                now=datetime(2026, 3, 27, 1, 0, tzinfo=timezone.utc),
                encrypt_file=fake_encrypt_file,
            )
            second = run_backup(
                config,
                client=client,
                now=datetime(2026, 3, 27, 2, 0, tzinfo=timezone.utc),
                encrypt_file=fake_encrypt_file,
            )

            self.assertEqual("ok_uploaded", first["status"])
            self.assertEqual("ok_no_changes", second["status"])
            self.assertEqual(1, len(client.put_calls))
            self.assertEqual(first["content_fingerprint"], second["content_fingerprint"])
            self.assertEqual(first["object_key"], second["last_uploaded_key"])

    def test_backup_updates_scan_state_without_upload_when_only_mtime_changes(self) -> None:
        from agentplane.scripts.automation.backup_secrets_r2 import run_backup

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            secrets_dir = root / "secrets" / "hosts" / "wsl"
            secrets_dir.mkdir(parents=True)
            target = secrets_dir / "alpha.txt"
            target.write_text("alpha\n", encoding="utf-8")

            config = self._make_config(root)
            client = FakeR2Client()

            first = run_backup(
                config,
                client=client,
                now=datetime(2026, 3, 27, 1, 0, tzinfo=timezone.utc),
                encrypt_file=fake_encrypt_file,
            )
            stat = target.stat()
            os.utime(target, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))

            second = run_backup(
                config,
                client=client,
                now=datetime(2026, 3, 27, 2, 0, tzinfo=timezone.utc),
                encrypt_file=fake_encrypt_file,
            )

            state = json.loads(config.state_file.read_text(encoding="utf-8"))
            self.assertEqual("ok_no_changes", second["status"])
            self.assertEqual(1, len(client.put_calls))
            self.assertNotEqual(first["scan_fingerprint"], second["scan_fingerprint"])
            self.assertEqual(first["content_fingerprint"], second["content_fingerprint"])
            self.assertEqual(second["scan_fingerprint"], state["scan_fingerprint"])
            self.assertEqual(second["content_fingerprint"], state["content_fingerprint"])

    def test_backup_uploads_new_archive_and_prunes_old_remote_objects(self) -> None:
        from agentplane.scripts.automation.backup_secrets_r2 import run_backup

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            secrets_dir = root / "secrets" / "hosts" / "wsl"
            secrets_dir.mkdir(parents=True)
            (secrets_dir / "alpha.txt").write_text("alpha\n", encoding="utf-8")

            existing = {
                "backups/agentplane/secrets-main/agentplane-secrets-20260320T000000Z-old000000001.tar.gz.enc": b"1",
                "backups/agentplane/secrets-main/agentplane-secrets-20260321T000000Z-old000000002.tar.gz.enc": b"2",
                "backups/agentplane/secrets-main/agentplane-secrets-20260322T000000Z-old000000003.tar.gz.enc": b"3",
                "backups/agentplane/secrets-main/agentplane-secrets-20260323T000000Z-old000000004.tar.gz.enc": b"4",
                "backups/agentplane/secrets-main/agentplane-secrets-20260324T000000Z-old000000005.tar.gz.enc": b"5",
            }
            config = self._make_config(root)
            client = FakeR2Client(existing=existing)

            payload = run_backup(
                config,
                client=client,
                now=datetime(2026, 3, 27, 3, 0, tzinfo=timezone.utc),
                encrypt_file=fake_encrypt_file,
            )

            self.assertEqual("ok_uploaded", payload["status"])
            self.assertEqual(1, len(client.put_calls))
            self.assertEqual(1, payload["deleted_old_backups"])
            self.assertEqual(
                [
                    "backups/agentplane/secrets-main/agentplane-secrets-20260320T000000Z-old000000001.tar.gz.enc"
                ],
                client.delete_calls,
            )
            self.assertEqual(5, len(client.objects))

    def test_backup_returns_failed_runtime_and_cleans_tmp_files_when_upload_fails(self) -> None:
        from agentplane.scripts.automation.backup_secrets_r2 import run_backup

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            secrets_dir = root / "secrets" / "hosts" / "wsl"
            secrets_dir.mkdir(parents=True)
            (secrets_dir / "alpha.txt").write_text("alpha\n", encoding="utf-8")

            config = self._make_config(root)
            client = FakeR2Client(fail_put=True)

            payload = run_backup(
                config,
                client=client,
                now=datetime(2026, 3, 27, 4, 0, tzinfo=timezone.utc),
                encrypt_file=fake_encrypt_file,
            )

            self.assertEqual("failed_runtime", payload["status"])
            self.assertEqual([], list(config.tmp_dir.glob("*")))
            self.assertFalse(config.state_file.exists())

# ======================================================================
# From: test_secrets_host_layout.py
# ======================================================================

class SecretsHostLayoutTests(unittest.TestCase):
    def test_bootstrap_required_truth_specs_keep_takeover_truth_separate_from_projections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            specs = bootstrap_required_truth_specs(root)
            refs = {item["secret_ref"]: item["destination"] for item in specs}

            self.assertEqual(
                str(root / "secrets" / "ssh" / "config").replace("\\", "/"),
                str(refs["local/control-plane/ssh-config"]).replace("\\", "/"),
            )
            self.assertNotIn("local/control-plane/prod-jump", refs)

    def test_bootstrap_directory_specs_follow_inventory_targets_instead_of_hardcoded_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "inventory" / "servers" / "wsl").mkdir(parents=True, exist_ok=True)
            (root / "inventory" / "servers" / "prod9-main").mkdir(parents=True, exist_ok=True)
            (root / "inventory" / "servers" / "wsl" / "inventory.json").write_text("{}", encoding="utf-8")
            (root / "inventory" / "servers" / "prod9-main" / "inventory.json").write_text("{}", encoding="utf-8")

            specs = bootstrap_directory_specs(root)
            targets = {item["scope"] for item in specs if item["scope"].startswith("targets/")}

            self.assertEqual({"targets/wsl", "targets/prod9-main"}, targets)

    def test_materialize_legacy_host_layout_projects_host_truth_into_legacy_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            host_root = root / "secrets" / "hosts" / "prod0-main"
            (host_root / "onepanel").mkdir(parents=True, exist_ok=True)
            (host_root / "infra" / "postgres").mkdir(parents=True, exist_ok=True)
            (host_root / "apps" / "sampleapi" / "tenants").mkdir(parents=True, exist_ok=True)
            (host_root / "apps" / "sampleapi").mkdir(parents=True, exist_ok=True)

            (host_root / "onepanel" / "api.env").write_text("ONEPANEL_API_KEY=demo\n", encoding="utf-8")
            (host_root / "infra" / "postgres" / "admin.env").write_text("POSTGRES_USER=postgres\n", encoding="utf-8")
            (host_root / "apps" / "sampleapi" / "runtime.env").write_text("DATABASE_URL=postgres://demo\n", encoding="utf-8")
            (host_root / "apps" / "sampleapi" / "tenants" / "postgres.env").write_text("PGDATABASE=sampleapi_prod0\n", encoding="utf-8")

            payload = materialize_legacy_host_layout(root, "prod0-main", write=True)

            self.assertEqual("prod0-main", payload["target"])
            self.assertTrue((root / "secrets" / "services" / "onepanel-api.env").is_file())
            self.assertTrue((root / "secrets" / "services" / "postgres" / "admin.prod0.env").is_file())
            self.assertTrue((root / "secrets" / "services" / "sampleapi.prod0.env").is_file())
            self.assertTrue((root / "secrets" / "tenants" / "prod0-main" / "sampleapi" / "postgres.env").is_file())
            self.assertEqual(
                "ONEPANEL_API_KEY=demo\n",
                (root / "secrets" / "services" / "onepanel-api.env").read_text(encoding="utf-8"),
            )

    def test_materialize_legacy_host_layout_projects_backup_env_with_host_first_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            host_root = root / "secrets" / "hosts" / "wsl"
            automation_root = host_root / "automations"
            automation_root.mkdir(parents=True, exist_ok=True)

            (automation_root / "secrets-backup.r2.env").write_text(
                "SECRETS_BACKUP_SOURCE_DIR=<repo-root>/secrets/hosts/wsl\n"
                "SECRETS_BACKUP_STATE_FILE=/data/agentplane/secrets-backup/state.json\n",
                encoding="utf-8",
            )

            payload = materialize_legacy_host_layout(root, "wsl", write=True)
            self.assertEqual("wsl", payload["target"])

            projected = root / "secrets" / "services" / "secrets-backup.r2.wsl.env"
            self.assertTrue(projected.is_file())
            projected_text = projected.read_text(encoding="utf-8")
            self.assertIn(
                f"SECRETS_BACKUP_SOURCE_DIR={root}/secrets/hosts/wsl".replace("\\", "/"),
                projected_text.replace("\\", "/"),
            )
