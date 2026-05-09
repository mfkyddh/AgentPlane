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


class TestAppDeliveryDeployRollbackCliTests(unittest.TestCase):
    def test_deploy_post_actions_prefers_explicit_app_repo_root_over_catalog_repo_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            repo_root = tmp_root / "oplinux"
            canonical_root = tmp_root / "sub2api"
            worktree_root = tmp_root / "sub2api.worktree"
            repo_root.mkdir(parents=True, exist_ok=True)
            canonical_root.mkdir(parents=True, exist_ok=True)
            worktree_root.mkdir(parents=True, exist_ok=True)

            write_inventory(repo_root)
            write_app_resource_registry(repo_root, baseline_app_resource_registry_payload())
            write_compose_template(repo_root)
            write_target_contract(
                canonical_root,
                tenant_resources=baseline_tenant_resources(include_minio=True),
                docs_config={"app_summary_file": "docs/CANONICAL.md"},
            )
            write_target_contract(
                worktree_root,
                tenant_resources=baseline_tenant_resources(include_minio=True),
                docs_config={"app_summary_file": "docs/WORKTREE.md"},
            )
            write_app_catalog_entry(
                repo_root,
                app="sub2api",
                repo_name="sub2api",
                app_root=canonical_root,
                service_key="sub2api",
                contracts={"prod0-main": "deploy/agentplane/contract.yaml"},
            )
            tenant_root = app_resource_secret_dir(repo_root, "prod0-main", "sub2api")
            tenant_root.mkdir(parents=True, exist_ok=True)
            (tenant_root / "postgres.env").write_text(
                "PGHOST=postgres18-prod\nPGPORT=5432\nPGDATABASE=sub2api_prod0\nPGUSER=sub2api_prod0\nPGPASSWORD=secret\n",
                encoding="utf-8",
            )
            (tenant_root / "redis.env").write_text(
                "REDIS_HOST=redis7-prod\nREDIS_PORT=6379\nREDIS_DB=1\nREDIS_KEY_PREFIX=sub2api:\nREDIS_PASSWORD=redis-secret\nREDIS_ENABLE_TLS=false\n",
                encoding="utf-8",
            )
            (tenant_root / "minio.env").write_text(
                "S3_BUCKET=prod0-sub2api\nS3_ACCESS_KEY=sub2api_prod0\nS3_SECRET_KEY=sub2api-s3-secret\n",
                encoding="utf-8",
            )

            result = run_app_delivery_cli(
                "deploy",
                repo_root=repo_root,
                app="sub2api",
                extra_args=("--image-ref", "sub2api-prod:test", "--dry-run", "--app-repo-root", str(worktree_root)),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)["payload"]
            post_actions = payload["post_actions"]["steps"]
            doc_sync_step = next(item for item in post_actions if item["action"] == "app.delivery.doc-sync")
            self.assertIn(str((worktree_root / "docs" / "WORKTREE.md").resolve()), doc_sync_step["payload"]["app_docs"])
            self.assertNotIn(
                str((canonical_root / "docs" / "CANONICAL.md").resolve()), doc_sync_step["payload"]["app_docs"]
            )

    def test_deploy_dry_run_includes_env_sync(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_tenant_secret_files(root)
            write_contract(root, tenant_resources=baseline_tenant_resources())
            write_compose_template(root)

            result = run_cli(
                "app",
                "delivery",
                "deploy",
                "--target",
                "prod0-main",
                "--app",
                "sub2api",
                "--repo-root",
                str(root),
                "--dry-run",
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("/data/sub2api/config/sub2api-prod.env", payload["payload"]["remote_env"])
            self.assertTrue(
                payload["payload"]["local_env"].replace("\\", "/").endswith("secrets/services/sub2api.prod0.env")
            )
            commands = "\n".join(payload["payload"]["commands"])
            self.assertIn("root@prod0-main", commands)
            self.assertNotIn("sudo ", commands)
            self.assertIn("install -Dm600 /tmp/sub2api.prod0.env /data/sub2api/config/sub2api-prod.env", commands)
            operation = payload["payload"]["operation"]
            ledger_file = Path(operation["ledger_file"])
            self.assertTrue(ledger_file.is_file())
            entry = json.loads(ledger_file.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(operation["op_id"], entry["op_id"])
            self.assertEqual("app", entry["command"])
            self.assertEqual("deploy", entry["action"])
            self.assertEqual("prod0-main", entry["target"])
            self.assertEqual("planned", entry["result"])

    def test_deploy_rejects_dry_run_with_execute(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_tenant_secret_files(root)
            write_contract(root, tenant_resources=baseline_tenant_resources())
            write_compose_template(root)

            result = run_app_delivery_cli(
                "deploy",
                repo_root=root,
                app="sub2api",
                extra_args=("--dry-run", "--execute"),
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("not allowed with argument", result.stderr)

    def test_deploy_execute_runs_remote_sync_and_cutover_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root, include_managed_bridge_networks=True)
            write_tenant_secret_files(root)
            write_app_resource_registry(root, baseline_app_resource_registry_payload())
            write_compose_template(root)
            write_contract(root, tenant_resources=baseline_tenant_resources())
            tenant_root = app_resource_secret_dir(root, "prod0-main", "sub2api")
            (tenant_root / "redis.env").write_text(
                "REDIS_HOST=redis7-prod\nREDIS_PORT=6379\nREDIS_DB=1\nREDIS_KEY_PREFIX=sub2api:\nREDIS_PASSWORD=redis-secret\nREDIS_ENABLE_TLS=false\n",
                encoding="utf-8",
            )
            (tenant_root / "minio.env").write_text(
                "S3_BUCKET=prod0-sub2api\nS3_ACCESS_KEY=sub2api_prod0\nS3_SECRET_KEY=sub2api-s3-secret\n",
                encoding="utf-8",
            )
            (root / "secrets" / "services").mkdir(parents=True, exist_ok=True)
            (root / "secrets" / "services" / "sub2api.prod0.env").write_text("SERVER_PORT=8080\n", encoding="utf-8")
            (root / "secrets" / "ssh").mkdir(parents=True, exist_ok=True)
            (root / "secrets" / "ssh" / "config").write_text("Host prod0-main\n", encoding="utf-8")
            bin_dir = root / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            log_file = root / "command.log"
            state_dir = root / "fake-network-state"
            state_dir.mkdir(parents=True, exist_ok=True)
            write_fake_command(
                bin_dir,
                "scp",
                '#!/usr/bin/env bash\nset -euo pipefail\nprintf \'scp %s\\n\' "$*" >> "$FAKE_CMD_LOG"\n',
            )
            write_fake_bridge_network_ssh(bin_dir)

            result = run_app_delivery_cli(
                "deploy",
                repo_root=root,
                app="sub2api",
                extra_args=("--image-ref", "sub2api-prod:test", "--execute"),
                env_overrides={
                    "PATH": f"{bin_dir}:{os.environ['PATH']}",
                    "FAKE_CMD_LOG": str(log_file),
                    "FAKE_NETWORK_STATE_DIR": str(state_dir),
                },
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)["payload"]
            self.assertTrue(payload["ok"])
            log_text = log_file.read_text(encoding="utf-8")
            self.assertIn("docker network inspect zqf_network", log_text)
            self.assertIn("ip addr add 172.19.0.1/16 dev br-66f7da1be943", log_text)
            self.assertIn("scp -F", log_text)
            self.assertIn("/opt/agentplane/infra/compose/sub2api/docker-compose.prod0.yml", log_text)
            self.assertIn("/data/sub2api/config/sub2api-prod.env", log_text)
            self.assertIn("systemctl disable --now sub2api || true", log_text)
            self.assertIn("docker compose -f docker-compose.prod0.yml up -d --pull never", log_text)

    def test_verify_execute_returns_origin_and_public_results(self) -> None:
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
            log_file = root / "verify.log"
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
            self.assertIn("origin", payload["checks"])
            self.assertIn("public", payload["checks"])
            self.assertEqual(2, len(payload["checks"]["origin"]))
            self.assertEqual(2, len(payload["checks"]["public"]))
            inspect_stdout = payload["checks"]["origin"][0]["stdout"]
            self.assertIn("DATABASE_PASSWORD=<redacted>", inspect_stdout)
            self.assertIn("REDIS_PASSWORD=<redacted>", inspect_stdout)
            self.assertNotIn("db-secret", inspect_stdout)
            self.assertNotIn("redis-secret", inspect_stdout)
            log_text = log_file.read_text(encoding="utf-8")
            self.assertIn("docker network inspect zqf_network", log_text)
            self.assertIn("docker inspect sub2api-prod", log_text)
            self.assertIn(f"{FAKE_PROXY_18080}/health", log_text)
            self.assertIn("https://token.example.net:8443/health", log_text)
            self.assertIn("https://token.example.net:8443/", log_text)

    def test_verify_execute_propagates_public_failure(self) -> None:
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
            log_file = root / "verify-failure.log"
            state_dir = root / "fake-network-state"
            state_dir.mkdir(parents=True, exist_ok=True)
            write_fake_bridge_network_ssh(bin_dir)
            write_fake_command(
                bin_dir,
                "curl",
                "#!/usr/bin/env bash\nset -euo pipefail\nif printf '%s' \"$*\" | grep -q '/health'; then exit 7; fi\nexit 0\n",
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

            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("invalid choice: 'delivery'", result.stderr)
            payload = json.loads(result.stdout)["payload"]
            self.assertFalse(payload["ok"])
            self.assertFalse(payload["checks"]["public"][0]["ok"])

