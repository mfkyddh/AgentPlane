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

from tests.support.constants import FAKE_PROXY_18080, FAKE_PROXY_3000

pytestmark = pytest.mark.e2e


class TestAppDeliveryRenderVerifyCliTests(unittest.TestCase):
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


