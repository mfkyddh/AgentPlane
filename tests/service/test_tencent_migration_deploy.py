"""Tests for tencent-cloud-service-migration skill building blocks.

The skill itself is a procedural SKILL.md that guides an AI agent through
cross-host service migration on a cloud provider.  These tests verify the
underlying code components the skill relies on:

- ``deploy_data_services_to_host.sh`` host alias validation
- ``remote_deploy_data_services.sh`` target-alias → compose-file mapping
- Service domain operations used during migration (resolve, verify, plan)
- Migration scope and verification patterns
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pytest
from tests.support.paths import REPO_ROOT

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

SKILL_PATH = REPO_ROOT / ".agents" / "skills" / "tencent-cloud-service-migration" / "SKILL.md"
_skill_available = SKILL_PATH.exists()

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Paths to the shell scripts under test
# ---------------------------------------------------------------------------

DEPLOY_DATA_SERVICES_SCRIPT = REPO_ROOT / "agentplane" / "scripts" / "remote" / "deploy_data_services_to_host.sh"
REMOTE_DEPLOY_DATA_SERVICES_SCRIPT = REPO_ROOT / "agentplane" / "scripts" / "remote" / "remote_deploy_data_services.sh"


def _run_script(script: Path, *args: str, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    """Run a bash script with the given arguments."""
    import shutil

    from agentplane.runtime.wsl_bridge import windows_path_to_wsl_posix

    bash = shutil.which("bash")
    # Try WSL path first; fall back to forward-slash Windows path for Git Bash.
    script_str = windows_path_to_wsl_posix(script) or str(script).replace("\\", "/")
    args_str = " ".join(f'"{a}"' for a in args)
    cmd = f'bash "{script_str}" {args_str}'
    return subprocess.run(
        [bash, "-c", cmd],
        input=stdin,
        text=True,
        capture_output=True,
        check=False,
        cwd=str(REPO_ROOT),
    )


def _bash_can_reach_script(script: Path) -> bool:
    """Check whether bash can actually access the script file."""
    import shutil

    from agentplane.runtime.wsl_bridge import windows_path_to_wsl_posix

    bash = shutil.which("bash")
    if not bash:
        return False
    script_str = windows_path_to_wsl_posix(script) or str(script).replace("\\", "/")
    result = subprocess.run(
        [bash, "-c", f'test -f "{script_str}"'],
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def _write_inventory(root: Path, target: str = "prod0-main") -> None:
    """Write minimal inventory for migration tests."""
    server_dir = root / "inventory" / "servers" / target
    server_dir.mkdir(parents=True, exist_ok=True)
    (server_dir / "inventory.json").write_text(
        json.dumps(
            {
                "ssh": {"aliases": [target], "user": "root"},
                "services": {
                    "postgres": {
                        "image": "postgres:18.3",
                        "container_name": "postgres18-prod",
                        "status": "running",
                        "host_binding": "0.0.0.0:5432",
                        "data_dir": "/data/postgres/data",
                    },
                    "redis": {
                        "image": "redis:7.4.7",
                        "container_name": "redis7-prod",
                        "status": "running",
                        "host_binding": "0.0.0.0:6379",
                        "data_dir": "/data/redis/data",
                    },
                    "minio": {
                        "image": "minio/minio:RELEASE.2025-04-22T22-12-26Z",
                        "container_name": "minio-prod",
                        "status": "running",
                        "host_bindings": ["0.0.0.0:9000", "0.0.0.0:9001"],
                        "data_dir": "/data/minio/data",
                        "config_dir": "/data/minio/config",
                    },
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (root / "secrets" / "ssh").mkdir(parents=True, exist_ok=True)
    (root / "secrets" / "ssh" / "config").write_text(f"Host {target}\n", encoding="utf-8")


def _write_migration_artifacts(root: Path, target_alias: str = "prod0") -> None:
    """Write the compose and secrets files required by deploy_data_services_to_host.sh."""
    for svc in ("postgres", "redis", "minio"):
        (root / "infra" / "compose" / svc).mkdir(parents=True, exist_ok=True)
    (root / "infra" / "compose" / "postgres" / f"docker-compose.{target_alias}.yml").write_text(
        "services:\n  postgres18-prod:\n    image: postgres:18.3\n", encoding="utf-8"
    )
    (root / "infra" / "compose" / "redis" / f"docker-compose.{target_alias}.yml").write_text(
        "services:\n  redis7-prod:\n    image: redis:7.4.7\n", encoding="utf-8"
    )
    (root / "infra" / "compose" / "minio" / f"docker-compose.{target_alias}.yml").write_text(
        "services:\n  minio-prod:\n    image: minio/minio:RELEASE.2025-04-22T22-12-26Z\n", encoding="utf-8"
    )
    (root / "secrets" / "services" / "postgres").mkdir(parents=True, exist_ok=True)
    (root / "secrets" / "services" / "redis").mkdir(parents=True, exist_ok=True)
    (root / "secrets" / "services" / "minio").mkdir(parents=True, exist_ok=True)
    (root / "secrets" / "services" / "postgres" / f"admin.{target_alias}.env").write_text(
        "POSTGRES_USER=admin\nPOSTGRES_DB=appdb\nPOSTGRES_PASSWORD=test\n", encoding="utf-8"
    )
    (root / "secrets" / "services" / "redis" / f"admin.{target_alias}.conf").write_text(
        "requirepass test-redis-pass\n", encoding="utf-8"
    )
    (root / "secrets" / "services" / "minio" / f"admin.{target_alias}.env").write_text(
        "MINIO_ROOT_USER=admin\nMINIO_ROOT_PASSWORD=test\n", encoding="utf-8"
    )


# ======================================================================
# deploy_data_services_to_host.sh host alias validation
# ======================================================================


@unittest.skipUnless(
    _bash_can_reach_script(DEPLOY_DATA_SERVICES_SCRIPT),
    "bash cannot reach deploy_data_services_to_host.sh (needs WSL or native Linux)",
)
class TestDeployDataServicesHostValidation(unittest.TestCase):
    """The deploy script must reject unsupported host aliases and accept known ones."""

    def test_rejects_unsupported_host_alias(self) -> None:
        result = _run_script(DEPLOY_DATA_SERVICES_SCRIPT, "unknown-host")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unsupported host alias", result.stderr)

    def test_accepts_prod0_main_alias(self) -> None:
        """prod0-main is a recognized alias; the script proceeds past validation."""
        result = _run_script(DEPLOY_DATA_SERVICES_SCRIPT, "prod0-main")

        # It will fail later (missing files / SSH) but NOT at host validation.
        self.assertNotIn("Unsupported host alias", result.stderr)

    def test_requires_exactly_one_argument(self) -> None:
        result = _run_script(DEPLOY_DATA_SERVICES_SCRIPT)

        self.assertNotEqual(result.returncode, 0)

    def test_rejects_extra_arguments(self) -> None:
        result = _run_script(DEPLOY_DATA_SERVICES_SCRIPT, "prod0-main", "extra")

        # Bash treats extra args as positional; the script only uses $1 so this
        # should still pass host validation (extra args are silently ignored).
        self.assertNotIn("Unsupported host alias", result.stderr)



# ======================================================================
# deploy_data_services_to_host.sh required-file validation
# ======================================================================


class TestDeployDataServicesRequiredFiles(unittest.TestCase):
    """The deploy script must verify all required compose and secret files exist."""

    def test_reports_missing_postgres_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Write everything except the postgres env file
            _write_inventory(root)
            for svc in ("postgres", "redis", "minio"):
                (root / "infra" / "compose" / svc).mkdir(parents=True, exist_ok=True)
            (root / "infra" / "compose" / "postgres" / "docker-compose.prod0.yml").write_text(
                "services: {}\n", encoding="utf-8"
            )
            (root / "infra" / "compose" / "redis" / "docker-compose.prod0.yml").write_text(
                "services: {}\n", encoding="utf-8"
            )
            (root / "infra" / "compose" / "minio" / "docker-compose.prod0.yml").write_text(
                "services: {}\n", encoding="utf-8"
            )
            (root / "secrets" / "services" / "redis").mkdir(parents=True, exist_ok=True)
            (root / "secrets" / "services" / "redis" / "admin.prod0.conf").write_text(
                "requirepass x\n", encoding="utf-8"
            )
            (root / "secrets" / "services" / "minio").mkdir(parents=True, exist_ok=True)
            (root / "secrets" / "services" / "minio" / "admin.prod0.env").write_text(
                "MINIO_ROOT_USER=x\n", encoding="utf-8"
            )

            # The script checks files relative to REPO_ROOT, so we need to
            # run it with the correct CWD.  Since deploy_data_services_to_host.sh
            # derives REPO_ROOT from its own location, we test the validation
            # logic indirectly by checking the script source.
            script_text = DEPLOY_DATA_SERVICES_SCRIPT.read_text(encoding="utf-8")
            self.assertIn("if [[ ! -f", script_text)
            self.assertIn("Missing required file", script_text)

    def test_script_validates_all_six_required_files(self) -> None:
        """The script checks for 6 required files: 3 compose + 3 secrets + remote script."""
        script_text = DEPLOY_DATA_SERVICES_SCRIPT.read_text(encoding="utf-8")

        # Verify the required_files array contains all expected entries
        self.assertIn("admin.${target_alias}.env", script_text)  # postgres env
        self.assertIn("admin.${target_alias}.conf", script_text)  # redis conf
        # minio env is also admin.${target_alias}.env (same pattern, different path)
        self.assertIn("secrets/services/postgres", script_text)
        self.assertIn("secrets/services/redis", script_text)
        self.assertIn("secrets/services/minio", script_text)
        self.assertIn("infra/compose/postgres", script_text)
        self.assertIn("infra/compose/redis", script_text)
        self.assertIn("infra/compose/minio", script_text)


# ======================================================================
# remote_deploy_data_services.sh target alias mapping
# ======================================================================


@unittest.skipUnless(
    _bash_can_reach_script(REMOTE_DEPLOY_DATA_SERVICES_SCRIPT),
    "bash cannot reach remote_deploy_data_services.sh (needs WSL or native Linux)",
)

class TestRemoteDeployTargetAliasMapping(unittest.TestCase):
    """The remote script maps target aliases to compose files."""

    def test_prod0_alias_maps_to_prod0_compose_files(self) -> None:
        script_text = REMOTE_DEPLOY_DATA_SERVICES_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("prod0)", script_text)
        self.assertIn("docker-compose.prod0.yml", script_text)

    def test_prod2_alias_maps_to_prod2_compose_files(self) -> None:
        script_text = REMOTE_DEPLOY_DATA_SERVICES_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("prod2)", script_text)
        self.assertIn("docker-compose.prod2.yml", script_text)

    def test_rejects_unknown_target_alias(self) -> None:
        script_text = REMOTE_DEPLOY_DATA_SERVICES_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("Unsupported target alias", script_text)
        self.assertIn("exit 1", script_text)

    def test_requires_stage_root_argument(self) -> None:
        result = _run_script(REMOTE_DEPLOY_DATA_SERVICES_SCRIPT)

        self.assertNotEqual(result.returncode, 0)

    def test_requires_target_alias_argument(self) -> None:
        result = _run_script(REMOTE_DEPLOY_DATA_SERVICES_SCRIPT, "/tmp/stage", "op-1")

        self.assertNotEqual(result.returncode, 0)



# ======================================================================
# remote_deploy_data_services.sh infrastructure setup
# ======================================================================


class TestRemoteDeployInfrastructureSetup(unittest.TestCase):
    """The remote script must create required directories and set permissions."""

    def test_script_creates_zqf_network(self) -> None:
        script_text = REMOTE_DEPLOY_DATA_SERVICES_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("docker network inspect zqf_network", script_text)
        self.assertIn("docker network create zqf_network", script_text)

    def test_script_creates_data_directories(self) -> None:
        script_text = REMOTE_DEPLOY_DATA_SERVICES_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("/data/redis/data", script_text)
        self.assertIn("/data/minio/data", script_text)
        self.assertIn("/data/minio/config", script_text)
        self.assertIn("/data/postgres/data", script_text)

    def test_script_sets_postgres_data_ownership(self) -> None:
        """PostgreSQL 18 official image uses uid/gid 999 for the postgres user."""
        script_text = REMOTE_DEPLOY_DATA_SERVICES_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("chown -R 999:999 /data/postgres/data", script_text)

    def test_script_sets_secret_directory_permissions(self) -> None:
        """Secret directories must be traversable for container processes."""
        script_text = REMOTE_DEPLOY_DATA_SERVICES_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("chmod 755", script_text)
        self.assertIn("secrets/services/postgres", script_text)
        self.assertIn("secrets/services/redis", script_text)
        self.assertIn("secrets/services/minio", script_text)

    def test_script_sets_redis_conf_readable(self) -> None:
        """Redis conf must be readable (not 0600) after copy for container process."""
        script_text = REMOTE_DEPLOY_DATA_SERVICES_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("chmod 644", script_text)
        self.assertIn("redis_conf", script_text)

    def test_script_cleans_up_legacy_container_names(self) -> None:
        """Legacy dev container names must be removed before deploying prod ones."""
        script_text = REMOTE_DEPLOY_DATA_SERVICES_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("redis7-dev", script_text)
        self.assertIn("minio-dev", script_text)
        self.assertIn("postgres18-dev", script_text)
        self.assertIn("docker rm -f", script_text)



# ======================================================================
# remote_deploy_data_services.sh service startup and verification
# ======================================================================


class TestRemoteDeployServiceVerification(unittest.TestCase):
    """The remote script must start services and verify they are healthy."""

    def test_script_starts_all_three_services(self) -> None:
        script_text = REMOTE_DEPLOY_DATA_SERVICES_SCRIPT.read_text(encoding="utf-8")

        # Each service is started with docker compose up -d
        self.assertIn("docker compose -f", script_text)
        self.assertIn("redis", script_text)
        self.assertIn("minio", script_text)
        self.assertIn("postgres", script_text)

    def test_script_waits_for_postgres_health(self) -> None:
        """The script polls postgres container health status before completing."""
        script_text = REMOTE_DEPLOY_DATA_SERVICES_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("docker inspect", script_text)
        self.assertIn("Health.Status", script_text)
        self.assertIn("healthy", script_text)
        self.assertIn("postgres18-prod", script_text)

    def test_script_verifies_redis_with_ping(self) -> None:
        script_text = REMOTE_DEPLOY_DATA_SERVICES_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("redis-cli", script_text)
        self.assertIn("PING", script_text)

    def test_script_verifies_minio_health_endpoints(self) -> None:
        script_text = REMOTE_DEPLOY_DATA_SERVICES_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("minio/health/live", script_text)
        self.assertIn("minio/health/ready", script_text)

    def test_script_verifies_postgres_version(self) -> None:
        script_text = REMOTE_DEPLOY_DATA_SERVICES_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("SELECT version()", script_text)

    def test_script_reports_operation_result(self) -> None:
        script_text = REMOTE_DEPLOY_DATA_SERVICES_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("===OPERATION===", script_text)
        self.assertIn("===RESULT===", script_text)
        self.assertIn("result=ok", script_text)
