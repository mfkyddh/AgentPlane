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

from tests.support.constants import (FAKE_HOST_BINDING)

pytestmark = pytest.mark.e2e


class TestAppDeliveryDeployRollbackCliTests(unittest.TestCase):
    def test_deploy_dry_run_uses_main_repo_secrets_when_repo_root_is_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            main_root = tmp_root / "main"
            worktree_root = tmp_root / "worktree"
            git_worktree_dir = main_root / ".git" / "worktrees" / "demo"
            (main_root / "secrets" / "services").mkdir(parents=True, exist_ok=True)
            (main_root / "secrets" / "ssh").mkdir(parents=True, exist_ok=True)
            (main_root / "secrets" / "services" / "sub2api.prod0.env").write_text(
                "SERVER_PORT=8080\n", encoding="utf-8"
            )
            git_worktree_dir.mkdir(parents=True, exist_ok=True)
            worktree_root.mkdir(parents=True, exist_ok=True)
            (worktree_root / ".git").write_text(f"gitdir: {git_worktree_dir}\n", encoding="utf-8")
            compose_dir = worktree_root / "infra" / "compose" / "sub2api"
            compose_dir.mkdir(parents=True, exist_ok=True)
            (compose_dir / "docker-compose.prod0.yml").write_text(
                yaml.safe_dump(
                    {
                        "services": {
                            "sub2api": {
                                "image": "sub2api-prod:latest",
                                "container_name": "sub2api-prod",
                                "ports": ["127.0.0.1:18080:8080"],
                                "environment": {},
                            }
                        }
                    },
                    sort_keys=False,
                    allow_unicode=False,
                ),
                encoding="utf-8",
            )
            write_inventory(worktree_root)
            write_tenant_secret_files(main_root)
            write_contract(worktree_root, tenant_resources=baseline_tenant_resources())

            result = run_app_delivery_cli(
                "deploy",
                repo_root=worktree_root,
                app="sub2api",
                extra_args=("--image-ref", "sub2api-prod:test", "--dry-run"),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(
                str(main_root / "secrets" / "services" / "sub2api.prod0.env"),
                payload["payload"]["local_env"],
            )
            commands = "\n".join(payload["payload"]["commands"])
            self.assertIn(str(main_root / "secrets" / "ssh" / "config"), commands)
            self.assertIn("root@prod0-main", commands)

    def test_deploy_dry_run_keeps_sudo_when_inventory_user_is_not_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            inventory_file = root / "inventory" / "servers" / "prod0-main" / "inventory.json"
            payload = json.loads(inventory_file.read_text(encoding="utf-8"))
            payload["ssh"]["user"] = "ubuntu"
            inventory_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            write_tenant_secret_files(root)
            write_contract(root, tenant_resources=baseline_tenant_resources())
            write_compose_template(root)

            result = run_app_delivery_cli(
                "deploy",
                repo_root=root,
                app="sub2api",
                extra_args=("--image-ref", "sub2api-prod:test", "--dry-run"),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            commands = "\n".join(json.loads(result.stdout)["payload"]["commands"])
            self.assertIn("ubuntu@prod0-main", commands)
            self.assertIn("sudo bash -lc", commands)

