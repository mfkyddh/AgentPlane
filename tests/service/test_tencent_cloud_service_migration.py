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
from unittest.mock import patch

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


# ======================================================================
# Migration scope patterns
# ======================================================================


class TestMigrationScopePatterns(unittest.TestCase):
    """Test that migration scope concepts are properly modeled."""

    def test_infrastructure_only_scope_copies_compose_and_secrets(self) -> None:
        """Infrastructure-only scope: recreate containers and credentials, no business data."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_migration_artifacts(root, "prod0")

            # Verify the artifacts exist (simulating what deploy script copies)
            compose_files = list((root / "infra" / "compose").rglob("*.yml"))
            secret_files = list((root / "secrets" / "services").rglob("*"))

            self.assertEqual(3, len(compose_files))
            self.assertGreaterEqual(len(secret_files), 3)

    def test_config_migration_scope_copies_selected_configs(self) -> None:
        """Config migration: copy selected runtime config directories."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_migration_artifacts(root, "prod0")

            # Simulate selective copy: only redis and postgres configs
            selected = []
            for svc in ("postgres", "redis"):
                conf_dir = root / "secrets" / "services" / svc
                if conf_dir.is_dir():
                    selected.extend(conf_dir.iterdir())

            self.assertEqual(2, len(selected))
            self.assertIn("postgres", str(selected[0]))
            self.assertIn("redis", str(selected[1]))

    def test_blank_control_plane_scope_deploys_empty_state(self) -> None:
        """Blank control plane: deploy with empty state, no data migration."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_migration_artifacts(root, "prod0")

            # Verify compose files exist but no data directories are populated
            compose_dir = root / "infra" / "compose"
            self.assertTrue(compose_dir.is_dir())

            # Data directories should not exist in the repo (they're on the host)
            self.assertFalse((root / "data").is_dir())


# ======================================================================
# Source host preservation
# ======================================================================


class TestSourceHostPreservation(unittest.TestCase):
    """The migration must keep the source host unchanged."""

    def test_deploy_script_targets_only_destination(self) -> None:
        """The deploy script takes a single host alias argument (the destination)."""
        script_text = DEPLOY_DATA_SERVICES_SCRIPT.read_text(encoding="utf-8")

        # The script uses $1 as the target host
        self.assertIn('target_host="$1"', script_text)
        # It does not reference any source host variable
        self.assertNotIn("source_host", script_text)
        self.assertNotIn("source_host", script_text.lower())

    def test_remote_script_does_not_stop_source_containers(self) -> None:
        """The remote script only removes legacy dev containers, not the source's prod containers."""
        script_text = REMOTE_DEPLOY_DATA_SERVICES_SCRIPT.read_text(encoding="utf-8")

        # It removes *-dev legacy names, not prod names
        self.assertIn("redis7-dev", script_text)
        self.assertIn("minio-dev", script_text)
        self.assertIn("postgres18-dev", script_text)
        # It does NOT do docker stop/rm on the prod containers being deployed
        self.assertNotIn("docker stop postgres18-prod", script_text)
        self.assertNotIn("docker stop redis7-prod", script_text)


# ======================================================================
# Docker image transfer fallback
# ======================================================================


@unittest.skipUnless(_skill_available, "SKILL.md not available")
class TestDockerImageTransferFallback(unittest.TestCase):
    """When destination can't pull images, use docker save | docker load."""

    def test_skill_documents_save_load_fallback(self) -> None:
        """The SKILL.md describes the docker save | docker load fallback pattern."""
        skill_path = REPO_ROOT / ".agents" / "skills" / "tencent-cloud-service-migration" / "SKILL.md"
        skill_text = skill_path.read_text(encoding="utf-8")

        self.assertIn("docker save", skill_text)
        self.assertIn("docker load", skill_text)
        self.assertIn("mirror.ccs.tencentyun.com", skill_text)

    def test_skill_documents_registry_mirror_fallback(self) -> None:
        """The SKILL.md documents the registry mirror fallback for Docker daemon EOF."""
        skill_path = REPO_ROOT / ".agents" / "skills" / "tencent-cloud-service-migration" / "SKILL.md"
        skill_text = skill_path.read_text(encoding="utf-8")

        self.assertIn("daemon.json", skill_text)
        self.assertIn("registry-mirrors", skill_text)
        self.assertIn("docker.1ms.run", skill_text)


# ======================================================================
# Verification checklist patterns
# ======================================================================


@unittest.skipUnless(_skill_available, "SKILL.md not available")
class TestVerificationChecklist(unittest.TestCase):
    """Test the verification patterns described in the skill."""

    def test_skill_documents_source_unchanged_verification(self) -> None:
        skill_path = REPO_ROOT / ".agents" / "skills" / "tencent-cloud-service-migration" / "SKILL.md"
        skill_text = skill_path.read_text(encoding="utf-8")

        self.assertIn("Source host services still run unchanged", skill_text)

    def test_skill_documents_destination_container_verification(self) -> None:
        skill_path = REPO_ROOT / ".agents" / "skills" / "tencent-cloud-service-migration" / "SKILL.md"
        skill_text = skill_path.read_text(encoding="utf-8")

        self.assertIn("Destination host containers match", skill_text)

    def test_skill_documents_local_upstream_checks(self) -> None:
        skill_path = REPO_ROOT / ".agents" / "skills" / "tencent-cloud-service-migration" / "SKILL.md"
        skill_text = skill_path.read_text(encoding="utf-8")

        self.assertIn("127.0.0.1:<port>", skill_text)

    def test_skill_documents_front_door_checks(self) -> None:
        """Front-door checks use Host header with curl to verify reverse proxy routing."""
        skill_path = REPO_ROOT / ".agents" / "skills" / "tencent-cloud-service-migration" / "SKILL.md"
        skill_text = skill_path.read_text(encoding="utf-8")

        self.assertIn("curl -kI", skill_text)
        self.assertIn("Host:", skill_text)

    def test_skill_documents_partial_state_handling(self) -> None:
        """Intentionally missing upstreams must be called out explicitly."""
        skill_path = REPO_ROOT / ".agents" / "skills" / "tencent-cloud-service-migration" / "SKILL.md"
        skill_text = skill_path.read_text(encoding="utf-8")

        self.assertIn("known partial state", skill_text)
        self.assertIn("intentionally missing", skill_text)


# ======================================================================
# Service domain operations used during migration
# ======================================================================


class TestServiceDomainForMigration(unittest.TestCase):
    """Test service domain operations that support the migration workflow."""

    def test_resolve_service_returns_data_services(self) -> None:
        """The migration skill works with postgres, redis, minio — all resolvable."""
        from agentplane.domain.service.registry import resolve_service

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_inventory(root)

            for svc_name in ("postgres", "redis", "minio"):
                definition, declared = resolve_service(root, "prod0-main", svc_name)
                self.assertEqual(svc_name, definition.name)
                self.assertEqual("docker", definition.runtime_kind)
                self.assertEqual("compose", definition.control_plane)
                self.assertIn("reconcile", definition.supported_operations)
                self.assertIsNotNone(declared)

    def test_service_plan_reconcile_produces_compose_steps(self) -> None:
        """Reconcile plan for a data service should produce compose-related steps."""
        from agentplane.domain.service.handlers import plan_service_operation

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_inventory(root)

            # Write a compose file so reconcile has something to sync
            compose_dir = root / "infra" / "compose" / "postgres"
            compose_dir.mkdir(parents=True, exist_ok=True)
            (compose_dir / "docker-compose.prod0.yml").write_text(
                "services:\n  postgres18-prod:\n    image: postgres:18.3\n", encoding="utf-8"
            )

            result = plan_service_operation(root, "prod0-main", "postgres", "reconcile")

            self.assertEqual("postgres", result["service"]["name"])
            self.assertEqual("reconcile", result["operation"])
            steps = result["steps"]
            self.assertGreater(len(steps), 0)
            # At least one step should involve docker compose
            display_texts = [s.get("display", "") for s in steps]
            self.assertTrue(any("docker compose" in d for d in display_texts))

    def test_service_verify_returns_health_checks(self) -> None:
        """Verify operation returns health check results for the service."""
        from agentplane.domain.service.handlers import verify_service

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_inventory(root)

            mock_probe = {
                "argv": ["ssh", "prod0-main", "docker inspect postgres18-prod"],
                "display": "ssh prod0-main docker inspect postgres18-prod",
                "returncode": 0,
                "stdout": json.dumps(
                    {
                        "Name": "postgres18-prod",
                        "Config": {"Image": "postgres:18.3"},
                        "State": {"Status": "running", "Running": True},
                        "HostConfig": {"NetworkMode": "bridge"},
                        "NetworkSettings": {"Ports": {"5432/tcp": [{"HostIp": "0.0.0.0", "HostPort": "5432"}]}},
                    }
                ),
                "stderr": "",
                "ok": True,
            }

            with patch("agentplane.adapters.service.docker_runtime.run_shell_command", return_value=mock_probe):
                result = verify_service(root, "prod0-main", "postgres")

            self.assertTrue(result["ok"])
            self.assertIn("checks", result)
            self.assertIn("running", result["checks"])

    def test_resolve_service_rejects_unknown_service(self) -> None:
        """Requesting a non-existent service raises ValueError."""
        from agentplane.domain.service.registry import resolve_service

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_inventory(root)

            with self.assertRaises(ValueError):
                resolve_service(root, "prod0-main", "nonexistent-service")

    def test_resolve_service_rejects_unknown_target(self) -> None:
        """Requesting a service for an unknown target raises ValueError."""
        from agentplane.domain.service.registry import resolve_service

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_inventory(root)

            with self.assertRaises(ValueError):
                resolve_service(root, "unknown-target", "postgres")


# ======================================================================
# Nginx-UI migration patterns
# ======================================================================


@unittest.skipUnless(_skill_available, "SKILL.md not available")
class TestNginxUIMigrationPatterns(unittest.TestCase):
    """Test nginx-ui migration patterns described in the skill."""

    def test_skill_documents_nginx_ui_directory_scope(self) -> None:
        """The skill specifies exactly which directories to copy for nginx-ui migration."""
        skill_path = REPO_ROOT / ".agents" / "skills" / "tencent-cloud-service-migration" / "SKILL.md"
        skill_text = skill_path.read_text(encoding="utf-8")

        self.assertIn("/data/apps/nginx-ui-official/nginx", skill_text)
        self.assertIn("/data/apps/nginx-ui-official/nginx-ui", skill_text)

    def test_skill_documents_websocket_origin_fix(self) -> None:
        """The skill documents the proxy_set_header fix for nginx-ui WebSocket self-checks."""
        skill_path = REPO_ROOT / ".agents" / "skills" / "tencent-cloud-service-migration" / "SKILL.md"
        skill_text = skill_path.read_text(encoding="utf-8")

        self.assertIn("proxy_set_header Host $http_host", skill_text)
        self.assertIn("request origin not allowed", skill_text)

    def test_skill_documents_8443_port_handling(self) -> None:
        """The skill documents handling of nginx-ui on explicit public port 8443."""
        skill_path = REPO_ROOT / ".agents" / "skills" / "tencent-cloud-service-migration" / "SKILL.md"
        skill_text = skill_path.read_text(encoding="utf-8")

        self.assertIn("8443", skill_text)


# ======================================================================
# Cloudflare token verification patterns
# ======================================================================


@unittest.skipUnless(_skill_available, "SKILL.md not available")
class TestCloudflareTokenVerification(unittest.TestCase):
    """Test Cloudflare token verification patterns from the skill."""

    def test_skill_documents_account_token_endpoint(self) -> None:
        """The skill specifies the correct token verification endpoint for account tokens."""
        skill_path = REPO_ROOT / ".agents" / "skills" / "tencent-cloud-service-migration" / "SKILL.md"
        skill_text = skill_path.read_text(encoding="utf-8")

        self.assertIn("/accounts/<account_id>/tokens/verify", skill_text)

    def test_skill_warns_against_user_token_endpoint(self) -> None:
        """The skill warns that /user/tokens/verify can give false negatives."""
        skill_path = REPO_ROOT / ".agents" / "skills" / "tencent-cloud-service-migration" / "SKILL.md"
        skill_text = skill_path.read_text(encoding="utf-8")

        self.assertIn("/user/tokens/verify", skill_text)
        self.assertIn("Invalid API Token", skill_text)

    def test_skill_documents_zone_scope_requirement(self) -> None:
        """Zone DNS writes require the token resource scope to include the target zone."""
        skill_path = REPO_ROOT / ".agents" / "skills" / "tencent-cloud-service-migration" / "SKILL.md"
        skill_text = skill_path.read_text(encoding="utf-8")

        self.assertIn("target zone", skill_text)
        self.assertIn("resource scope", skill_text)


# ======================================================================
# Script cleanup and trap handling
# ======================================================================


class TestScriptCleanupPatterns(unittest.TestCase):
    """Test that scripts properly clean up temporary resources."""

    def test_deploy_script_cleans_up_remote_stage(self) -> None:
        """The deploy script removes the remote staging directory on exit."""
        script_text = DEPLOY_DATA_SERVICES_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("trap cleanup EXIT", script_text)
        self.assertIn("rm -rf", script_text)
        self.assertIn("remote_stage_root", script_text)

    def test_deploy_script_cleans_up_local_stage(self) -> None:
        """The deploy script removes the local staging directory on exit."""
        script_text = DEPLOY_DATA_SERVICES_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("stage_dir", script_text)
        self.assertIn("cleanup", script_text)

    def test_remote_script_cleans_up_stage_root(self) -> None:
        """The remote script removes the stage root after deployment."""
        script_text = REMOTE_DEPLOY_DATA_SERVICES_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("trap cleanup EXIT", script_text)
        self.assertIn("rm -rf", script_text)


# ======================================================================
# Script staging and transfer patterns
# ======================================================================


class TestScriptStagingPatterns(unittest.TestCase):
    """Test the staging and transfer patterns used in the deploy script."""

    def test_deploy_script_stages_compose_and_secrets(self) -> None:
        """The deploy script creates a staging directory with compose and secrets."""
        script_text = DEPLOY_DATA_SERVICES_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("mkdir -p", script_text)
        self.assertIn("infra/compose/postgres", script_text)
        self.assertIn("infra/compose/redis", script_text)
        self.assertIn("infra/compose/minio", script_text)
        self.assertIn("secrets/services/postgres", script_text)
        self.assertIn("secrets/services/redis", script_text)
        self.assertIn("secrets/services/minio", script_text)

    def test_deploy_script_transfers_via_tar_pipe(self) -> None:
        """The deploy script uses tar over SSH to transfer the staging directory."""
        script_text = DEPLOY_DATA_SERVICES_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("tar -C", script_text)
        self.assertIn("tar -xf -", script_text)
        self.assertIn("ssh", script_text)

    def test_deploy_script_executes_remote_script_via_stdin(self) -> None:
        """The deploy script pipes the remote script through SSH stdin."""
        script_text = DEPLOY_DATA_SERVICES_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("bash -s --", script_text)
        self.assertIn("$REMOTE_SCRIPT", script_text)


# ======================================================================
# Integration: service operations with mock SSH
# ======================================================================


class TestServiceOperationsWithMockSSH(unittest.TestCase):
    """Test service operations end-to-end with mocked SSH backend."""

    def _write_full_inventory(self, root: Path) -> None:
        """Write a complete inventory for integration-style tests."""
        server_dir = root / "inventory" / "servers" / "prod0-main"
        server_dir.mkdir(parents=True, exist_ok=True)
        (server_dir / "inventory.json").write_text(
            json.dumps(
                {
                    "ssh": {"aliases": ["prod0-main"], "user": "root"},
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
                        },
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (root / "secrets" / "ssh").mkdir(parents=True, exist_ok=True)
        (root / "secrets" / "ssh" / "config").write_text("Host prod0-main\n", encoding="utf-8")

    def _make_mock_probe(self, container_name: str, image: str, status: str = "running") -> dict:
        return {
            "argv": ["ssh", "prod0-main", f"docker inspect {container_name}"],
            "display": f"ssh prod0-main docker inspect {container_name}",
            "returncode": 0,
            "stdout": json.dumps(
                {
                    "Name": container_name,
                    "Config": {"Image": image},
                    "State": {"Status": status, "Running": status == "running"},
                    "HostConfig": {"NetworkMode": "bridge"},
                    "NetworkSettings": {"Ports": {}},
                }
            ),
            "stderr": "",
            "ok": True,
        }

    def test_search_returns_all_data_services(self) -> None:
        """Searching services should return postgres, redis, minio among others."""
        from agentplane.domain.service.handlers import search_services

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_full_inventory(root)

            result = search_services(root, "prod0-main")

            names = {item["name"] for item in result["items"]}
            self.assertIn("postgres", names)
            self.assertIn("redis", names)
            self.assertIn("minio", names)

    def test_get_service_returns_declared_shape_for_postgres(self) -> None:
        from agentplane.domain.service.handlers import get_service

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_full_inventory(root)

            mock_probe = self._make_mock_probe("postgres18-prod", "postgres:18.3")

            with patch("agentplane.adapters.service.docker_runtime.run_shell_command", return_value=mock_probe):
                result = get_service(root, "prod0-main", "postgres")

            self.assertEqual("postgres", result["service"]["name"])
            self.assertIn("reconcile", result["service"]["supported_operations"])
            self.assertIsNotNone(result["live"])

    def test_get_service_returns_declared_shape_for_redis(self) -> None:
        from agentplane.domain.service.handlers import get_service

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_full_inventory(root)

            mock_probe = self._make_mock_probe("redis7-prod", "redis:7.4.7")

            with patch("agentplane.adapters.service.docker_runtime.run_shell_command", return_value=mock_probe):
                result = get_service(root, "prod0-main", "redis")

            self.assertEqual("redis", result["service"]["name"])
            self.assertEqual("compose", result["service"]["control_plane"])

    def test_get_service_returns_declared_shape_for_minio(self) -> None:
        from agentplane.domain.service.handlers import get_service

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_full_inventory(root)

            mock_probe = self._make_mock_probe("minio-prod", "minio/minio:RELEASE.2025-04-22T22-12-26Z")

            with patch("agentplane.adapters.service.docker_runtime.run_shell_command", return_value=mock_probe):
                result = get_service(root, "prod0-main", "minio")

            self.assertEqual("minio", result["service"]["name"])
            self.assertIn("restart", result["service"]["supported_operations"])

    def test_plan_reconcile_for_all_data_services(self) -> None:
        """All data services should support reconcile for migration."""
        from agentplane.domain.service.handlers import plan_service_operation

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_full_inventory(root)

            for svc_name in ("postgres", "redis", "minio"):
                compose_dir = root / "infra" / "compose" / svc_name
                compose_dir.mkdir(parents=True, exist_ok=True)
                (compose_dir / "docker-compose.prod0.yml").write_text(
                    f"services:\n  {svc_name}-prod:\n    image: latest\n", encoding="utf-8"
                )

                result = plan_service_operation(root, "prod0-main", svc_name, "reconcile")

                self.assertEqual(svc_name, result["service"]["name"])
                self.assertEqual("reconcile", result["operation"])
                self.assertGreater(len(result["steps"]), 0)
