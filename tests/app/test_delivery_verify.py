from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from agentplane.domain.app.resource_paths import app_resource_secret_dir
from agentplane.domain.app.runtime import _secrets_root
from agentplane.runtime.host_profile import HostProfile
from tests.support.app_delivery_cli import run_app_delivery_cli, run_cli
from tests.support.app_delivery_contracts import (
    ERROR_ID_TENANT_REGISTRY_MISMATCH,
    ERROR_ID_TENANT_RESOURCES_REQUIRED,
    ERROR_ID_TENANT_SECRET_FILE_MISSING,
    ERROR_ID_TENANT_SECRET_FILE_SCOPE,
    init_git_repo,
    sync_app_catalog_for_contract,
    write_app_catalog_entry,
    write_contract,
    write_sampleapi_contract,
    write_target_contract,
)
from tests.support.app_delivery_targets import (
    assert_live_db_partition_markers,
    baseline_app_resource_registry_payload,
    baseline_tenant_resources,
    write_app_resource_registry,
    write_compose_template,
    write_fake_bridge_network_ssh,
    write_fake_command,
    write_internal_worker_compose_template,
    write_inventory,
    write_sampleapi_compose_templates,
    write_sampleapi_tenant_files,
    write_tenant_secret_files,
)
from tests.support.app_resources import resource_relative, resource_root

pytestmark = pytest.mark.e2e


class TestAppDeliveryRenderVerifyCliTests(unittest.TestCase):
    def test_render_runtime_outputs_sub2api_prod_compose(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_tenant_secret_files(root)
            write_contract(root, tenant_resources=baseline_tenant_resources())
            write_compose_template(root)

            result = run_app_delivery_cli(
                "render-runtime",
                repo_root=root,
                app="sub2api",
                extra_args=("--image-ref", "sub2api-prod:test"),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("render-runtime", payload["action"])
            self.assertEqual("sub2api-prod", payload["payload"]["container_name"])
            content = payload["payload"]["compose"]
            self.assertIn("image: sub2api-prod:test", content)
            self.assertIn("container_name: sub2api-prod", content)
            self.assertIn("127.0.0.1:18080:8080", content)
            self.assertIn("postgres18-prod", content)
            self.assertIn("redis7-prod", content)
            self.assertIn("zqf_network", content)
            self.assertIn("/data/sub2api/config/sub2api-prod.env", content)

    def test_render_runtime_outputs_sampleapi_wsl_compose_with_public_binding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_app_resource_registry(
                root,
                {
                    "sampleapi": {
                        "owner_app": "sampleapi",
                        "postgres": {"database": "sampleapi_wsl", "user": "sampleapi_wsl"},
                        "redis": {"db": 2, "key_prefix": "sampleapi:wsl:"},
                        "secret_files": [
                            resource_relative("wsl", "sampleapi", "postgres"),
                            resource_relative("wsl", "sampleapi", "redis"),
                        ],
                    }
                },
                target="wsl",
            )
            write_sampleapi_tenant_files(root, target="wsl")
            write_sampleapi_contract(root, target="wsl")
            write_sampleapi_compose_templates(root)

            result = run_app_delivery_cli(
                "render-runtime",
                repo_root=root,
                app="sampleapi",
                target="wsl",
                extra_args=("--image-ref", "sampleapi-dev:test"),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("sampleapi-dev", payload["payload"]["container_name"])
            compose = payload["payload"]["compose"]
            self.assertIn("image: sampleapi-dev:test", compose)
            self.assertIn("container_name: sampleapi-dev", compose)
            self.assertIn("0.0.0.0:3000:3000", compose)
            self.assertIn("DATABASE_HOST: postgres18-dev", compose)
            self.assertIn("REDIS_HOST: redis7-dev", compose)

    def test_render_runtime_keeps_internal_worker_without_default_db_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory_file = root / "inventory" / "servers" / "prod0-main" / "inventory.json"
            inventory_file.parent.mkdir(parents=True, exist_ok=True)
            inventory_file.write_text(
                json.dumps(
                    {
                        "ssh": {"aliases": ["prod0-main"], "user": "root"},
                        "services": {"sub2api": {"container_name": "sub2api-prod"}},
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            wsl_inventory_file = root / "inventory" / "servers" / "wsl" / "inventory.json"
            wsl_inventory_file.parent.mkdir(parents=True, exist_ok=True)
            wsl_inventory_file.write_text(inventory_file.read_text(encoding="utf-8"), encoding="utf-8")
            contract_file = write_contract(
                root,
                dependency="sub2api-prod",
                dependencies=["sub2api-prod"],
                tenant_resources={},
                ingress_mode="internal",
                public_sites=[],
            )
            payload = yaml.safe_load(contract_file.read_text(encoding="utf-8"))
            payload["app_id"] = "sample-register-v2"
            payload["artifact"]["image_name"] = "sample-register-v2-prod"
            payload["runtime"]["container_name"] = "sample-register-v2-prod"
            payload["runtime"]["container_port"] = 18081
            payload["runtime"]["host_binding"] = "127.0.0.1:18081"
            payload["runtime"]["healthcheck"] = {"path": "/healthz", "expected_status": 200}
            payload["data"]["mounts"] = [{"host_path": "/data/sample-register-v2/data", "container_path": "/data"}]
            payload["inventory"]["service_key"] = "sample-register-v2"
            contract_file.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8")
            sync_app_catalog_for_contract(
                root, contract_file=contract_file, app="sample-register-v2", service_key="sample-register-v2"
            )
            write_internal_worker_compose_template(root)

            result = run_app_delivery_cli(
                "render-runtime",
                repo_root=root,
                app="sample-register-v2",
                extra_args=("--image-ref", "sample-register-v2-prod:test"),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            compose = json.loads(result.stdout)["payload"]["compose"]
            self.assertIn("image: sample-register-v2-prod:test", compose)
            self.assertIn("127.0.0.1:18081:18081", compose)
            self.assertNotIn("DATABASE_HOST", compose)
            self.assertNotIn("REDIS_HOST", compose)

    def test_verify_app_uses_local_host_binding_for_wsl_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_app_resource_registry(
                root,
                {
                    "sampleapi": {
                        "owner_app": "sampleapi",
                        "postgres": {"database": "sampleapi_wsl", "user": "sampleapi_wsl"},
                        "redis": {"db": 2, "key_prefix": "sampleapi:wsl:"},
                        "secret_files": [
                            resource_relative("wsl", "sampleapi", "postgres"),
                            resource_relative("wsl", "sampleapi", "redis"),
                        ],
                    }
                },
                target="wsl",
            )
            write_sampleapi_tenant_files(root, target="wsl")
            write_sampleapi_contract(root, target="wsl")

            result = run_app_delivery_cli(
                "verify",
                repo_root=root,
                app="sampleapi",
                target="wsl",
                extra_args=("--dry-run",),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("sampleapi-dev", payload["payload"]["container_name"])
            commands = payload["payload"]["commands"]
            self.assertEqual(["curl -fsS http://127.0.0.1:3000/api/status"], commands)

    def test_verify_app_execute_waits_for_container_health_before_origin_healthcheck(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root, include_managed_bridge_networks=True)
            write_tenant_secret_files(root)
            write_app_resource_registry(root, baseline_app_resource_registry_payload())
            write_contract(root, tenant_resources=baseline_tenant_resources())
            (root / "secrets" / "ssh").mkdir(parents=True, exist_ok=True)
            (root / "secrets" / "ssh" / "config").write_text("Host prod0-main\n", encoding="utf-8")
            bin_dir = root / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            log_file = root / "verify-wait.log"
            state_dir = root / "fake-network-state"
            state_dir.mkdir(parents=True, exist_ok=True)
            write_fake_bridge_network_ssh(bin_dir)
            write_fake_command(
                bin_dir,
                "curl",
                '#!/usr/bin/env bash\nset -euo pipefail\nprintf \'curl %s\\n\' "$*" >> "$FAKE_CMD_LOG"\n',
            )

            result = run_app_delivery_cli(
                "verify",
                repo_root=root,
                app="sub2api",
                extra_args=("--execute",),
                env_overrides={
                    "PATH": f"{bin_dir}:{os.environ['PATH']}",
                    "FAKE_CMD_LOG": str(log_file),
                    "FAKE_NETWORK_STATE_DIR": str(state_dir),
                },
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)["payload"]
            self.assertTrue(payload["ok"])
            commands = payload["commands"]
            self.assertEqual(4, len(commands))
            self.assertIn("docker inspect sub2api-prod", commands[0])
            self.assertIn("for i in $(seq 1 12)", commands[1])
            self.assertIn("curl -fsS http://127.0.0.1:18080/health", commands[1])
            self.assertEqual(commands[1], payload["checks"]["origin"][1]["display"])
            self.assertIn("curl -fsS https://token.example.net:8443/health", commands[2])
            self.assertIn("curl -fsSI https://token.example.net:8443/", commands[3])
            ssh_log = log_file.read_text(encoding="utf-8")
            self.assertIn("docker inspect sub2api-prod", ssh_log)
            self.assertIn("for i in $(seq 1 12)", ssh_log)

    def test_deploy_app_execute_runs_local_compose_for_wsl_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_app_resource_registry(
                root,
                {
                    "sampleapi": {
                        "owner_app": "sampleapi",
                        "postgres": {"database": "sampleapi_wsl", "user": "sampleapi_wsl"},
                        "redis": {"user": "", "db": 2, "key_prefix": "sampleapi:wsl:"},
                        "secret_files": [
                            resource_relative("wsl", "sampleapi", "postgres"),
                            resource_relative("wsl", "sampleapi", "redis"),
                        ],
                    }
                },
                target="wsl",
            )
            write_sampleapi_tenant_files(root, target="wsl")
            write_sampleapi_compose_templates(root)
            service_env = root / "secrets" / "services" / "sampleapi.wsl.env"
            service_env.parent.mkdir(parents=True, exist_ok=True)
            service_env.write_text(
                "APP_DATABASE_URL=postgresql://sampleapi_wsl:secret@postgres18-dev:5432/sampleapi_wsl\n",
                encoding="utf-8",
            )
            write_sampleapi_contract(root, target="wsl")
            bin_dir = root / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            log_file = root / "wsl-deploy.log"
            write_fake_command(
                bin_dir,
                "docker",
                '#!/usr/bin/env bash\nset -euo pipefail\nprintf \'docker %s\\n\' "$*" >> "$FAKE_CMD_LOG"\n',
            )

            result = run_app_delivery_cli(
                "deploy",
                repo_root=root,
                app="sampleapi",
                target="wsl",
                extra_args=("--image-ref", "sampleapi-dev:test", "--execute"),
                env_overrides={
                    "PATH": f"{bin_dir}:{os.environ['PATH']}",
                    "FAKE_CMD_LOG": str(log_file),
                },
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)["payload"]
            self.assertEqual("sampleapi-dev", payload["container_name"])
            self.assertTrue(payload["ok"])
            self.assertIn("docker compose -f", payload["commands"][0])
            self.assertIn("docker compose -f", log_file.read_text(encoding="utf-8"))

    def test_deploy_app_execute_uses_backend_runner_for_wsl_target_on_windows_host(self) -> None:
        import agentplane.domain.app.runtime as app_runtime

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_app_resource_registry(
                root,
                {
                    "sampleapi": {
                        "owner_app": "sampleapi",
                        "postgres": {"database": "sampleapi_wsl", "user": "sampleapi_wsl"},
                        "redis": {"user": "", "db": 2, "key_prefix": "sampleapi:wsl:"},
                        "secret_files": [
                            resource_relative("wsl", "sampleapi", "postgres"),
                            resource_relative("wsl", "sampleapi", "redis"),
                        ],
                    }
                },
                target="wsl",
            )
            write_sampleapi_tenant_files(root, target="wsl")
            write_sampleapi_compose_templates(root)
            service_env = root / "secrets" / "services" / "sampleapi.wsl.env"
            service_env.parent.mkdir(parents=True, exist_ok=True)
            service_env.write_text(
                "APP_DATABASE_URL=postgresql://sampleapi_wsl:secret@postgres18-dev:5432/sampleapi_wsl\n",
                encoding="utf-8",
            )
            contract_file = write_sampleapi_contract(root, target="wsl")
            contract = app_runtime.validate_contract(contract_file, repo_root=root, target="wsl")

            class _FakeExecutionResult:
                def __init__(self, plan) -> None:
                    self.plan = plan
                    self.ok = True

                def to_payload(self) -> dict[str, object]:
                    return {
                        "backend_type": self.plan.backend_type,
                        "argv": list(self.plan.argv),
                        "display": "wsl.exe -e bash -lc docker compose",
                        "cwd": None,
                        "returncode": 0,
                        "stdout": "",
                        "stderr": "",
                        "ok": True,
                    }

            class _FakeRunner:
                def __init__(self) -> None:
                    self.plan = None

                def execute(self, plan, *, bindings=None):
                    self.plan = plan
                    return _FakeExecutionResult(plan)

            runner = _FakeRunner()
            with (
                patch(
                    "agentplane.domain.app.runtime.detect_host_profile",
                    return_value=HostProfile(os_name="windows", linux_backend="windows-wsl", supports_docker=True),
                ),
                patch("agentplane.domain.app.runtime.build_backend_runner", return_value=runner),
            ):
                payload = app_runtime.deploy_app(
                    contract,
                    repo_root=root,
                    target="wsl",
                    image_ref="sampleapi-dev:test",
                    dry_run=False,
                    execute=True,
                )

            self.assertEqual("windows-wsl", runner.plan.backend_type)
            self.assertEqual("windows-wsl", payload["backend_type"])
            self.assertEqual("windows-wsl", payload["results"][0]["backend_type"])
            self.assertEqual(["docker", "compose"], payload["results"][0]["argv"][:2])

    def test_deploy_app_execute_uses_canonical_service_env_for_wsl_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outer_root = Path(tmp) / "repo-root"
            worktree_root = outer_root / ".worktrees" / "codex" / "release"
            worktree_root.mkdir(parents=True, exist_ok=True)
            git_worktree_dir = outer_root / ".git" / "worktrees" / "release"
            git_worktree_dir.mkdir(parents=True, exist_ok=True)
            (worktree_root / ".git").write_text(f"gitdir: {git_worktree_dir}\n", encoding="utf-8")
            (worktree_root / "secrets").symlink_to(outer_root / "secrets")
            write_inventory(worktree_root)
            write_sampleapi_tenant_files(outer_root, target="wsl")
            write_app_resource_registry(
                worktree_root,
                {
                    "sampleapi": {
                        "owner_app": "sampleapi",
                        "postgres": {"database": "sampleapi_wsl", "user": "sampleapi_wsl"},
                        "redis": {"user": "", "db": 2, "key_prefix": "sampleapi:wsl:"},
                        "secret_files": [
                            resource_relative("wsl", "sampleapi", "postgres"),
                            resource_relative("wsl", "sampleapi", "redis"),
                        ],
                    }
                },
                target="wsl",
            )
            write_sampleapi_compose_templates(worktree_root)
            service_env = outer_root / "secrets" / "services" / "sampleapi.wsl.env"
            service_env.parent.mkdir(parents=True, exist_ok=True)
            service_env.write_text(
                "APP_DATABASE_URL=postgresql://sampleapi_wsl:secret@postgres18-dev:5432/sampleapi_wsl\n",
                encoding="utf-8",
            )
            write_sampleapi_contract(worktree_root, target="wsl")
            bin_dir = worktree_root / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            log_file = worktree_root / "wsl-deploy.log"
            write_fake_command(
                bin_dir,
                "docker",
                '#!/usr/bin/env bash\nset -euo pipefail\nprintf \'docker %s\\n\' "$*" >> "$FAKE_CMD_LOG"\n',
            )

            result = run_app_delivery_cli(
                "deploy",
                repo_root=worktree_root,
                app="sampleapi",
                target="wsl",
                extra_args=("--image-ref", "sampleapi-dev:test", "--execute"),
                env_overrides={
                    "PATH": f"{bin_dir}:{os.environ['PATH']}",
                    "FAKE_CMD_LOG": str(log_file),
                },
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)["payload"]
            rendered_compose = Path(payload["compose_file"])
            compose_text = rendered_compose.read_text(encoding="utf-8")
            self.assertIn(str(service_env), compose_text)
            self.assertIn("DATABASE_HOST: postgres18-dev", compose_text)
            self.assertIn("REDIS_HOST: redis7-dev", compose_text)

    def test_verify_app_execute_runs_local_healthcheck_for_wsl_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_app_resource_registry(
                root,
                {
                    "sampleapi": {
                        "owner_app": "sampleapi",
                        "postgres": {"database": "sampleapi_wsl", "user": "sampleapi_wsl"},
                        "redis": {"user": "", "db": 2, "key_prefix": "sampleapi:wsl:"},
                        "secret_files": [
                            resource_relative("wsl", "sampleapi", "postgres"),
                            resource_relative("wsl", "sampleapi", "redis"),
                        ],
                    }
                },
                target="wsl",
            )
            write_sampleapi_tenant_files(root, target="wsl")
            write_sampleapi_contract(root, target="wsl")
            bin_dir = root / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            log_file = root / "wsl-verify.log"
            write_fake_command(
                bin_dir,
                "curl",
                '#!/usr/bin/env bash\nset -euo pipefail\nprintf \'curl %s\\n\' "$*" >> "$FAKE_CMD_LOG"\necho \'{"status":"ok"}\'\n',
            )

            result = run_app_delivery_cli(
                "verify",
                repo_root=root,
                app="sampleapi",
                target="wsl",
                extra_args=("--execute",),
                env_overrides={
                    "PATH": f"{bin_dir}:{os.environ['PATH']}",
                    "FAKE_CMD_LOG": str(log_file),
                },
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)["payload"]
            self.assertEqual("sampleapi-dev", payload["container_name"])
            self.assertTrue(payload["ok"])
            self.assertEqual(["curl -fsS http://127.0.0.1:3000/api/status"], payload["commands"])
            self.assertIn("curl -fsS http://127.0.0.1:3000/api/status", log_file.read_text(encoding="utf-8"))


# ======================================================================
# From: test_app_delivery_validate_cli.py
# ======================================================================


