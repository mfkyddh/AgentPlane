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
