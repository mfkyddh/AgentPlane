import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


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

    def test_init_data_services_supports_prod2_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_cli("infra", "secrets", "init-data-services", "prod2-main", "--repo-root", str(root))
            self.assertEqual(result.returncode, 0, msg=result.stderr)

            payload = json.loads(result.stdout)
            self.assertEqual({"command", "action", "target", "payload"}, set(payload))
            self.assertEqual("infra", payload.get("command"))
            self.assertEqual("secrets.init-data-services", payload.get("action"))
            self.assertEqual("prod2-main", payload.get("target"))
            self.assertIn("files", payload["payload"])
            postgres_file = root / "secrets" / "services" / "postgres" / "admin.prod2.env"
            self.assertTrue(postgres_file.is_file())
            self.assertTrue((root / "secrets" / "services" / "redis" / "admin.prod2.conf").is_file())
            self.assertTrue((root / "secrets" / "services" / "minio" / "admin.prod2.env").is_file())
            postgres_values = parse_env_text(postgres_file.read_text(encoding="utf-8"))
            self.assertEqual("postgres", postgres_values["POSTGRES_USER"])

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
            REPO_ROOT / "infra" / "compose" / "postgres" / "docker-compose.prod0.yml": "secrets/services/postgres/admin.prod0.env",
            REPO_ROOT / "infra" / "compose" / "postgres" / "docker-compose.prod2.yml": "secrets/services/postgres/admin.prod2.env",
            REPO_ROOT / "infra" / "compose" / "redis" / "docker-compose.wsl.yml": "secrets/services/redis/admin.wsl.conf",
            REPO_ROOT / "infra" / "compose" / "redis" / "docker-compose.prod0.yml": "secrets/services/redis/admin.prod0.conf",
            REPO_ROOT / "infra" / "compose" / "redis" / "docker-compose.prod2.yml": "secrets/services/redis/admin.prod2.conf",
            REPO_ROOT / "infra" / "compose" / "minio" / "docker-compose.wsl.yml": "secrets/services/minio/admin.wsl.env",
            REPO_ROOT / "infra" / "compose" / "minio" / "docker-compose.prod0.yml": "secrets/services/minio/admin.prod0.env",
            REPO_ROOT / "infra" / "compose" / "minio" / "docker-compose.prod2.yml": "secrets/services/minio/admin.prod2.env",
            REPO_ROOT / "agentplane" / "scripts" / "remote" / "deploy_data_services_to_host.sh": "secrets/services/postgres/admin.${target_alias}.env",
            REPO_ROOT / "agentplane" / "scripts" / "remote" / "remote_deploy_data_services.sh": 'postgres_env="${control_root}/secrets/services/postgres/admin.${target_alias}.env"',
        }
        for path, expected in files_and_expected.items():
            with self.subTest(path=path):
                self.assertIn(expected, path.read_text(encoding="utf-8"))

    def test_deploy_data_services_script_supports_prod2_target(self) -> None:
        script = (REPO_ROOT / "agentplane" / "scripts" / "remote" / "deploy_data_services_to_host.sh").read_text(encoding="utf-8")
        self.assertIn("prod2-main", script)
        self.assertIn("target_alias", script)
        self.assertIn("admin.${target_alias}.env", script)
        self.assertIn("admin.${target_alias}.conf", script)

    def test_data_service_deploy_scripts_pin_canonical_compose_file_names(self) -> None:
        local_script = (REPO_ROOT / "agentplane" / "scripts" / "remote" / "deploy_data_services_to_host.sh").read_text(
            encoding="utf-8"
        )
        remote_script = (REPO_ROOT / "agentplane" / "scripts" / "remote" / "remote_deploy_data_services.sh").read_text(
            encoding="utf-8"
        )

        for compose_name in ("docker-compose.prod0.yml", "docker-compose.prod2.yml"):
            with self.subTest(compose_name=compose_name):
                self.assertIn(compose_name, local_script)
                self.assertIn(compose_name, remote_script)

    def test_remote_bash_wrapper_delegates_to_cli_shim(self) -> None:
        wrapper = (REPO_ROOT / "agentplane" / "scripts" / "remote" / "run_remote_bash.sh").read_text(encoding="utf-8")
        self.assertIn("python3 -m agentplane.cli", wrapper)
        self.assertNotIn("agentplane/ssh.py", wrapper)

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

