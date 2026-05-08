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


class TestAppDeliveryDocSyncCliTests(unittest.TestCase):
    def test_doc_sync_should_fail_on_registry_truth_drift_before_writing_server_readme(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_tenant_secret_files(root)
            registry_payload = baseline_app_resource_registry_payload()
            registry_payload["sub2api"]["postgres"]["database"] = "sub2api_wrong"
            write_app_resource_registry(root, registry_payload)
            write_contract(root, tenant_resources=baseline_tenant_resources())

            server_readme = root / "inventory" / "servers" / "prod0-main" / "README.md"
            app_summary = root / "docs" / "AGENTPLANE_DEPLOYMENT.md"

            result = run_app_delivery_cli("doc-sync", repo_root=root, app="sub2api", extra_args=("--write",))

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(ERROR_ID_TENANT_REGISTRY_MISMATCH, result.stdout + result.stderr)
            self.assertFalse(server_readme.exists())
            self.assertFalse(app_summary.exists())

    def test_doc_sync_prefers_explicit_app_repo_root_over_catalog_repo_root(self) -> None:
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
            write_tenant_secret_files(repo_root)
            write_target_contract(
                canonical_root,
                tenant_resources=baseline_tenant_resources(),
                docs_config={"app_summary_file": "docs/CANONICAL.md"},
            )
            write_target_contract(
                worktree_root,
                tenant_resources=baseline_tenant_resources(),
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

            result = run_app_delivery_cli(
                "doc-sync",
                repo_root=repo_root,
                app="sub2api",
                extra_args=("--write", "--app-repo-root", str(worktree_root)),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            worktree_summary = worktree_root / "docs" / "WORKTREE.md"
            canonical_summary = canonical_root / "docs" / "CANONICAL.md"
            self.assertTrue(worktree_summary.exists())
            self.assertFalse(canonical_summary.exists())
            self.assertIn(str(worktree_summary), payload["app_docs"])

    def test_doc_sync_writes_server_summary_and_app_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app_root = root / "sub2api"
            app_root.mkdir(parents=True, exist_ok=True)
            write_inventory(root)
            write_tenant_secret_files(root, include_minio=True)
            write_contract(app_root, tenant_resources=baseline_tenant_resources(include_minio=True))
            inventory_file = root / "inventory" / "servers" / "prod0-main" / "inventory.json"
            server_readme = root / "inventory" / "servers" / "prod0-main" / "README.md"
            server_readme.write_text(
                "\n".join(
                    [
                        "# prod0-main 摘要",
                        "",
                        "<!-- BEGIN AGENTPLANE_ONEPANEL_LEDGER -->",
                        "## 1Panel 对象台帐投影",
                        "",
                        "- 刷新命令：`uv run python -m agentplane.cli projection ledger refresh --target prod0-main --repo-root <repo-root> --write`",
                        "<!-- END AGENTPLANE_ONEPANEL_LEDGER -->",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            payload = json.loads(inventory_file.read_text(encoding="utf-8"))
            payload["services"]["sub2api"] = {
                "control_plane": "compose",
                "container_name": "sub2api-prod",
                "depends_on_containers": ["postgres18-prod", "redis7-prod"],
                "host_binding": "127.0.0.1:18080",
                "public_url": "https://token.example.net:8443",
                "rollback_entry": {"kind": "systemd", "service_name": "sub2api"},
                "app_resource_summary": {
                    "postgres": {
                        "database": "sub2api_prod0",
                        "user": "sub2api_prod0",
                        "secret_file": resource_relative("prod0-main", "sub2api", "postgres"),
                    },
                    "redis": {
                        "user": "sub2api_legacy_runtime",
                        "db": 1,
                        "key_prefix": "sub2api:",
                        "secret_file": resource_relative("prod0-main", "sub2api", "redis"),
                    },
                    "minio": {
                        "bucket": "prod0-sub2api",
                        "access_key": "sub2api_prod0",
                        "policy_name": "prod0-sub2api-rw",
                        "policy_scope": "bucket-only",
                        "isolation_level": "bucket-scoped-rw",
                        "secret_file": resource_relative("prod0-main", "sub2api", "minio"),
                    },
                },
            }
            inventory_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

            result = run_app_delivery_cli(
                "doc-sync",
                repo_root=root,
                app="sub2api",
                extra_args=("--write",),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            app_summary = app_root / "docs" / "AGENTPLANE_DEPLOYMENT.md"
            self.assertTrue(server_readme.exists())
            self.assertTrue(app_summary.exists())
            server_readme_text = server_readme.read_text(encoding="utf-8")
            app_summary_text = app_summary.read_text(encoding="utf-8")
            self.assertIn("sub2api-prod", server_readme_text)
            self.assertIn("postgres18-prod", app_summary_text)
            self.assertIn("app_resource_summary", server_readme_text)
            assert_live_db_partition_markers(self, server_readme_text)
            assert_live_db_partition_markers(self, app_summary_text)
            self.assertIn("PostgreSQL/MinIO", server_readme_text)
            self.assertIn("shared runtime credential", server_readme_text)
            self.assertIn("PostgreSQL/MinIO", app_summary_text)
            self.assertIn("shared runtime credential", app_summary_text)
            self.assertIn("bucket-scoped", server_readme_text)
            self.assertIn('"policy_name": "prod0-sub2api-rw"', server_readme_text)
            self.assertIn('"policy_scope": "bucket-only"', server_readme_text)
            self.assertIn('"isolation_level": "bucket-scoped-rw"', server_readme_text)
            self.assertIn('"policy_name": "prod0-sub2api-rw"', app_summary_text)
            self.assertIn('"policy_scope": "bucket-only"', app_summary_text)
            self.assertIn('"isolation_level": "bucket-scoped-rw"', app_summary_text)
            self.assertIn("合同文件：`contract.yaml`", app_summary_text)
            self.assertIn("<!-- BEGIN AGENTPLANE_ONEPANEL_LEDGER -->", server_readme_text)
            self.assertIn("--repo-root <repo-root> --write", server_readme_text)
            server_redis_line = next(
                line for line in server_readme_text.splitlines() if line.startswith("- app_resource_summary.redis")
            )
            redis_line = next(line for line in app_summary_text.splitlines() if line.startswith("- `redis`："))
            self.assertIn('"db": 1', server_redis_line)
            self.assertIn('"key_prefix": "sub2api:"', server_redis_line)
            self.assertNotIn('"user":', server_redis_line)
            self.assertIn('"db": 1', redis_line)
            self.assertIn('"key_prefix": "sub2api:"', redis_line)
            self.assertNotIn('"user":', redis_line)
            self.assertIn(resource_relative("prod0-main", "sub2api", "minio"), app_summary_text)

    def test_doc_sync_wsl_does_not_emit_prod0_live_db_partition_language(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app_root = root / "sampleapi"
            app_root.mkdir(parents=True, exist_ok=True)
            write_inventory(root)
            write_sampleapi_contract(app_root, target="wsl")
            write_sampleapi_tenant_files(root, target="wsl")
            inventory_file = root / "inventory" / "servers" / "wsl" / "inventory.json"
            payload = json.loads(inventory_file.read_text(encoding="utf-8"))
            payload["services"]["sampleapi"] = {
                "control_plane": "compose",
                "container_name": "sampleapi-dev",
                "depends_on_containers": ["postgres18-dev", "redis7-dev"],
                "host_binding": "0.0.0.0:3000",
                "public_url": "http://127.0.0.1:3000",
                "rollback_entry": {"kind": "none", "note": "dev only"},
                "app_resource_summary": {
                    "postgres": {
                        "database": "sampleapi_wsl",
                        "user": "sampleapi_wsl",
                        "secret_file": resource_relative("wsl", "sampleapi", "postgres"),
                    },
                    "redis": {
                        "user": "sampleapi_wsl_legacy",
                        "db": 2,
                        "key_prefix": "sampleapi:wsl:",
                        "secret_file": resource_relative("wsl", "sampleapi", "redis"),
                    },
                },
            }
            inventory_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

            result = run_app_delivery_cli(
                "doc-sync",
                repo_root=root,
                app="sampleapi",
                target="wsl",
                extra_args=("--write",),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            server_readme_text = (root / "inventory" / "servers" / "wsl" / "README.md").read_text(encoding="utf-8")
            app_summary_text = (app_root / "docs" / "AGENTPLANE_DEPLOYMENT.wsl.md").read_text(encoding="utf-8")
            self.assertNotIn("shared runtime credential", server_readme_text)
            self.assertNotIn("DB 级逻辑分区", server_readme_text)
            self.assertNotIn("强隔离", server_readme_text)
            self.assertNotIn("shared runtime credential", app_summary_text)
            self.assertNotIn("DB 级逻辑分区", app_summary_text)
            self.assertNotIn("强隔离", app_summary_text)
            self.assertNotIn('"user": "sampleapi_wsl_legacy"', server_readme_text)
            self.assertNotIn('"user": "sampleapi_wsl_legacy"', app_summary_text)

    def test_doc_sync_renders_1panel_compose_transition_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app_root = root / "sampleapi"
            app_root.mkdir(parents=True, exist_ok=True)
            write_inventory(root)
            write_sampleapi_tenant_files(root)
            write_sampleapi_contract(
                app_root,
                rollback_entry={
                    "kind": "1panel-compose",
                    "project_name": "samplepay-prod",
                    "container_name": "samplepay-prod",
                    "project_path": "/data/1panel/docker/compose/samplepay-prod",
                    "compose_file": "/data/1panel/docker/compose/samplepay-prod/docker-compose.yml",
                },
            )
            inventory_file = root / "inventory" / "servers" / "prod0-main" / "inventory.json"
            payload = json.loads(inventory_file.read_text(encoding="utf-8"))
            payload["services"]["sampleapi"] = {
                "control_plane": "compose",
                "container_name": "sampleapi-prod",
                "depends_on_containers": ["postgres18-prod", "redis7-prod"],
                "host_binding": "127.0.0.1:3000",
                "public_url": "https://sampleapi.example.net:8443",
                "rollback_entry": {
                    "kind": "1panel-compose",
                    "project_name": "samplepay-prod",
                    "container_name": "samplepay-prod",
                    "project_path": "/data/1panel/docker/compose/samplepay-prod",
                    "compose_file": "/data/1panel/docker/compose/samplepay-prod/docker-compose.yml",
                },
            }
            inventory_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

            result = run_app_delivery_cli(
                "doc-sync",
                repo_root=root,
                app="sampleapi",
                extra_args=("--write",),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            app_summary_text = (app_root / "docs" / "AGENTPLANE_DEPLOYMENT.md").read_text(encoding="utf-8")
            self.assertIn("1panel-compose", app_summary_text)
            self.assertIn("path=/data/1panel/docker/compose/samplepay-prod", app_summary_text)
            self.assertIn("compose=/data/1panel/docker/compose/samplepay-prod/docker-compose.yml", app_summary_text)

    def test_doc_sync_writes_target_specific_app_summary_files_when_configured(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app_root = root / "sub2api"
            app_root.mkdir(parents=True, exist_ok=True)
            write_inventory(root)
            write_tenant_secret_files(root, include_minio=True)
            write_tenant_secret_files(root, target="wsl")
            contract_file = write_contract(
                app_root,
                tenant_resources=baseline_tenant_resources(include_minio=True),
                docs_config={
                    "app_summary_files": {
                        "prod0-main": "docs/AGENTPLANE_DEPLOYMENT.prod0-main.md",
                        "wsl": "docs/AGENTPLANE_DEPLOYMENT.wsl.md",
                    }
                },
            )
            wsl_contract_file = app_root / "contract.wsl.yaml"
            wsl_contract_payload = yaml.safe_load(contract_file.read_text(encoding="utf-8"))
            wsl_contract_payload["infra"]["tenant_resources"] = baseline_tenant_resources(target="wsl")
            wsl_contract_payload["runtime"]["container_name"] = "sub2api-dev"
            wsl_contract_payload["runtime"]["host_binding"] = "0.0.0.0:18080"
            wsl_contract_file.write_text(
                yaml.safe_dump(wsl_contract_payload, sort_keys=False, allow_unicode=False),
                encoding="utf-8",
            )
            write_app_catalog_entry(
                root,
                app="sub2api",
                repo_name=app_root.name,
                app_root=app_root,
                service_key="sub2api",
                contracts={
                    "prod0-main": contract_file.relative_to(app_root).as_posix(),
                    "wsl": wsl_contract_file.relative_to(app_root).as_posix(),
                },
            )

            prod_inventory_file = root / "inventory" / "servers" / "prod0-main" / "inventory.json"
            prod_payload = json.loads(prod_inventory_file.read_text(encoding="utf-8"))
            prod_payload["services"]["sub2api"] = {
                "control_plane": "compose",
                "container_name": "sub2api-prod",
                "depends_on_containers": ["postgres18-prod", "redis7-prod"],
                "host_binding": "127.0.0.1:18080",
                "public_url": "https://token.example.net:8443",
                "rollback_entry": {"kind": "systemd", "service_name": "sub2api"},
                "app_resource_summary": {
                    "postgres": {
                        "database": "sub2api_prod0",
                        "user": "sub2api_prod0",
                        "secret_file": resource_relative("prod0-main", "sub2api", "postgres"),
                    },
                    "redis": {
                        "db": 1,
                        "key_prefix": "sub2api:",
                        "secret_file": resource_relative("prod0-main", "sub2api", "redis"),
                    },
                    "minio": {
                        "bucket": "prod0-sub2api",
                        "access_key": "sub2api_prod0",
                        "policy_name": "prod0-sub2api-rw",
                        "policy_scope": "bucket-only",
                        "isolation_level": "bucket-scoped-rw",
                        "secret_file": resource_relative("prod0-main", "sub2api", "minio"),
                    },
                },
            }
            prod_inventory_file.write_text(json.dumps(prod_payload, ensure_ascii=False, indent=2), encoding="utf-8")

            wsl_inventory_file = root / "inventory" / "servers" / "wsl" / "inventory.json"
            wsl_payload = json.loads(wsl_inventory_file.read_text(encoding="utf-8"))
            wsl_payload["services"]["sub2api"] = {
                "control_plane": "compose",
                "container_name": "sub2api-dev",
                "depends_on_containers": ["postgres18-dev", "redis7-dev"],
                "host_binding": "0.0.0.0:18080",
                "public_url": "http://127.0.0.1:18080",
                "rollback_entry": {"kind": "systemd", "service_name": "sub2api"},
                "app_resource_summary": {
                    "postgres": {
                        "database": "sub2api_wsl",
                        "user": "sub2api_wsl",
                        "secret_file": resource_relative("wsl", "sub2api", "postgres"),
                    },
                    "redis": {
                        "db": 1,
                        "key_prefix": "sub2api:wsl:",
                        "secret_file": resource_relative("wsl", "sub2api", "redis"),
                    },
                },
            }
            wsl_inventory_file.write_text(json.dumps(wsl_payload, ensure_ascii=False, indent=2), encoding="utf-8")

            prod_result = run_app_delivery_cli(
                "doc-sync",
                repo_root=root,
                app="sub2api",
                extra_args=("--write",),
            )
            self.assertEqual(prod_result.returncode, 0, msg=prod_result.stderr)

            wsl_result = run_app_delivery_cli(
                "doc-sync",
                repo_root=root,
                app="sub2api",
                target="wsl",
                extra_args=("--write",),
            )
            self.assertEqual(wsl_result.returncode, 0, msg=wsl_result.stderr)

            prod_summary = app_root / "docs" / "AGENTPLANE_DEPLOYMENT.prod0-main.md"
            wsl_summary = app_root / "docs" / "AGENTPLANE_DEPLOYMENT.wsl.md"
            self.assertTrue(prod_summary.exists())
            self.assertTrue(wsl_summary.exists())

            prod_text = prod_summary.read_text(encoding="utf-8")
            wsl_text = wsl_summary.read_text(encoding="utf-8")
            self.assertIn("目标环境：`prod0-main`", prod_text)
            self.assertIn("postgres18-prod", prod_text)
            self.assertIn("合同文件：`contract.yaml`", prod_text)
            self.assertIn("目标环境：`wsl`", wsl_text)
            self.assertIn("postgres18-dev", wsl_text)
            self.assertNotEqual(prod_text, wsl_text)

    def test_doc_sync_marks_missing_app_resource_summary_instead_of_falling_back_to_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app_root = root / "sub2api"
            app_root.mkdir(parents=True, exist_ok=True)
            write_inventory(root)
            write_tenant_secret_files(root, include_minio=True)
            write_contract(app_root, tenant_resources=baseline_tenant_resources(include_minio=True))
            inventory_file = root / "inventory" / "servers" / "prod0-main" / "inventory.json"
            payload = json.loads(inventory_file.read_text(encoding="utf-8"))
            payload["services"]["sub2api"] = {
                "control_plane": "compose",
                "container_name": "sub2api-prod",
                "depends_on_containers": ["postgres18-prod", "redis7-prod"],
                "host_binding": "127.0.0.1:18080",
                "public_url": "https://token.example.net:8443",
                "rollback_entry": {"kind": "systemd", "service_name": "sub2api"},
            }
            inventory_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

            result = run_app_delivery_cli(
                "doc-sync",
                repo_root=root,
                app="sub2api",
                extra_args=("--write",),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            app_summary = app_root / "docs" / "AGENTPLANE_DEPLOYMENT.md"
            content = app_summary.read_text(encoding="utf-8")
            self.assertIn("未登记 app_resource_summary", content)
            self.assertNotIn(resource_relative("prod0-main", "sub2api", "postgres"), content)

    def test_deploy_execute_runs_post_actions_in_projection_inventory_doc_sync_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root, include_managed_bridge_networks=True)
            write_tenant_secret_files(root)
            write_app_resource_registry(root, baseline_app_resource_registry_payload())
            write_compose_template(root)
            write_contract(root, tenant_resources=baseline_tenant_resources())
            tenant_root = app_resource_secret_dir(root, "prod0-main", "sub2api")
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
            (root / "secrets" / "services").mkdir(parents=True, exist_ok=True)
            (root / "secrets" / "services" / "sub2api.prod0.env").write_text("SERVER_PORT=8080\n", encoding="utf-8")
            (root / "secrets" / "ssh").mkdir(parents=True, exist_ok=True)
            (root / "secrets" / "ssh" / "config").write_text("Host prod0-main\n", encoding="utf-8")
            bin_dir = root / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            log_file = root / "post-actions-command.log"
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
            post_actions = payload["post_actions"]
            self.assertTrue(post_actions["ok"])
            self.assertEqual(
                [
                    "projection.runtime-env.apply",
                    "app.delivery.inventory-refresh",
                    "app.delivery.doc-sync",
                ],
                [item["action"] for item in post_actions["steps"]],
            )
            evidence = post_actions["evidence"]
            ledger_file = Path(evidence["ledger_file"])
            self.assertTrue(ledger_file.is_file())
            entries = [
                json.loads(line) for line in ledger_file.read_text(encoding="utf-8").splitlines() if line.strip()
            ]
            post_action_entries = [
                entry
                for entry in entries
                if entry.get("command") == "app"
                and entry.get("action") == "deploy"
                and entry.get("result") == "post-actions-synced"
            ]
            self.assertEqual(1, len(post_action_entries))
            self.assertEqual(evidence["operation"]["op_id"], post_action_entries[0]["op_id"])


# ======================================================================
# From: test_app_delivery_inventory_cli.py
# ======================================================================


