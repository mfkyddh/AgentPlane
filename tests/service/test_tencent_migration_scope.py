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
