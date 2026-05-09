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


class TestAppDeliveryDeployRollbackCliTests(unittest.TestCase):
    def test_deploy_dry_run_stops_1panel_app_control_plane_for_sampleapi(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_sampleapi_tenant_files(root)
            write_sampleapi_contract(root)
            write_sampleapi_compose_templates(root)

            result = run_app_delivery_cli(
                "deploy",
                repo_root=root,
                app="sampleapi",
                extra_args=("--image-ref", "sampleapi-prod:test", "--dry-run"),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            commands = "\n".join(payload["payload"]["commands"])
            self.assertIn(
                "uv run python -m agentplane.providers.onepanel_transition --target prod0-main app --operate stop --install-id 3",
                commands,
            )
            self.assertNotIn("systemctl stop", commands)

    def test_rollback_dry_run_starts_1panel_app_control_plane_for_sampleapi(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_sampleapi_tenant_files(root)
            write_sampleapi_contract(root)
            write_sampleapi_compose_templates(root)

            result = run_app_delivery_cli(
                "rollback",
                repo_root=root,
                app="sampleapi",
                extra_args=("--dry-run",),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            commands = "\n".join(payload["payload"]["commands"])
            self.assertIn(
                "uv run python -m agentplane.providers.onepanel_transition --target prod0-main app --operate start --install-id 3",
                commands,
            )
            self.assertNotIn("systemctl start", commands)

    def test_deploy_dry_run_stops_1panel_compose_control_plane(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_sampleapi_tenant_files(root)
            write_sampleapi_contract(
                root,
                rollback_entry={
                    "kind": "1panel-compose",
                    "project_name": "samplepay-prod",
                    "container_name": "samplepay-prod",
                    "project_path": "/data/1panel/docker/compose/samplepay-prod",
                    "compose_file": "/data/1panel/docker/compose/samplepay-prod/docker-compose.yml",
                },
            )
            write_sampleapi_compose_templates(root)

            result = run_app_delivery_cli(
                "deploy",
                repo_root=root,
                app="sampleapi",
                extra_args=("--image-ref", "sampleapi-prod:test", "--dry-run"),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            commands = "\n".join(json.loads(result.stdout)["payload"]["commands"])
            self.assertIn(
                "uv run python -m agentplane.providers.onepanel_transition --target prod0-main project --name samplepay-prod --operate stop",
                commands,
            )
            self.assertNotIn("systemctl stop", commands)

    def test_rollback_dry_run_starts_1panel_compose_control_plane(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_sampleapi_tenant_files(root)
            write_sampleapi_contract(
                root,
                rollback_entry={
                    "kind": "1panel-compose",
                    "project_name": "samplepay-prod",
                    "container_name": "samplepay-prod",
                    "project_path": "/data/1panel/docker/compose/samplepay-prod",
                    "compose_file": "/data/1panel/docker/compose/samplepay-prod/docker-compose.yml",
                },
            )
            write_sampleapi_compose_templates(root)

            result = run_app_delivery_cli(
                "rollback",
                repo_root=root,
                app="sampleapi",
                extra_args=("--dry-run",),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            commands = "\n".join(json.loads(result.stdout)["payload"]["commands"])
            self.assertIn(
                "uv run python -m agentplane.providers.onepanel_transition --target prod0-main project --name samplepay-prod --operate up",
                commands,
            )
            self.assertNotIn("systemctl start", commands)

    def test_deploy_execute_runs_onepanel_compose_stop_instead_of_systemd(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root, include_managed_bridge_networks=True)
            write_sampleapi_tenant_files(root)
            write_sampleapi_compose_templates(root)
            write_sampleapi_contract(
                root,
                rollback_entry={
                    "kind": "1panel-compose",
                    "project_name": "samplepay-prod",
                    "container_name": "samplepay-prod",
                    "project_path": "/data/1panel/docker/compose/samplepay-prod",
                    "compose_file": "/data/1panel/docker/compose/samplepay-prod/docker-compose.yml",
                },
            )
            (root / "secrets" / "services").mkdir(parents=True, exist_ok=True)
            (root / "secrets" / "services" / "sampleapi.prod0.env").write_text("PORT=3000\n", encoding="utf-8")
            (root / "secrets" / "ssh").mkdir(parents=True, exist_ok=True)
            (root / "secrets" / "ssh" / "config").write_text("Host prod0-main\n", encoding="utf-8")
            bin_dir = root / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            log_file = root / "onepanel-compose-deploy.log"
            state_dir = root / "fake-network-state"
            state_dir.mkdir(parents=True, exist_ok=True)
            write_fake_bridge_network_ssh(bin_dir)
            write_fake_command(
                bin_dir,
                "scp",
                '#!/usr/bin/env bash\nset -euo pipefail\nprintf \'scp %s\\n\' "$*" >> "$FAKE_CMD_LOG"\n',
            )
            write_fake_command(
                bin_dir,
                "uv",
                '#!/usr/bin/env bash\nset -euo pipefail\nprintf \'uv %s\\n\' "$*" >> "$FAKE_CMD_LOG"\n',
            )

            result = run_app_delivery_cli(
                "deploy",
                repo_root=root,
                app="sampleapi",
                extra_args=("--image-ref", "sampleapi-prod:test", "--execute"),
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
            self.assertIn(
                "uv run python -m agentplane.providers.onepanel_transition --target prod0-main project --name samplepay-prod --operate stop",
                log_text,
            )
            self.assertNotIn("systemctl stop", log_text)

    def test_rollback_execute_runs_onepanel_compose_up_instead_of_systemd(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_sampleapi_tenant_files(root)
            write_sampleapi_compose_templates(root)
            write_sampleapi_contract(
                root,
                rollback_entry={
                    "kind": "1panel-compose",
                    "project_name": "samplepay-prod",
                    "container_name": "samplepay-prod",
                    "project_path": "/data/1panel/docker/compose/samplepay-prod",
                    "compose_file": "/data/1panel/docker/compose/samplepay-prod/docker-compose.yml",
                },
            )
            (root / "secrets" / "ssh").mkdir(parents=True, exist_ok=True)
            (root / "secrets" / "ssh" / "config").write_text("Host prod0-main\n", encoding="utf-8")
            bin_dir = root / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            log_file = root / "onepanel-compose-rollback.log"
            write_fake_command(
                bin_dir,
                "ssh",
                '#!/usr/bin/env bash\nset -euo pipefail\nprintf \'ssh %s\\n\' "$*" >> "$FAKE_CMD_LOG"\n',
            )
            write_fake_command(
                bin_dir,
                "uv",
                '#!/usr/bin/env bash\nset -euo pipefail\nprintf \'uv %s\\n\' "$*" >> "$FAKE_CMD_LOG"\n',
            )

            result = run_app_delivery_cli(
                "rollback",
                repo_root=root,
                app="sampleapi",
                extra_args=("--execute",),
                env_overrides={
                    "PATH": f"{bin_dir}:{os.environ['PATH']}",
                    "FAKE_CMD_LOG": str(log_file),
                },
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)["payload"]
            self.assertTrue(payload["ok"])
            log_text = log_file.read_text(encoding="utf-8")
            self.assertIn(
                "uv run python -m agentplane.providers.onepanel_transition --target prod0-main project --name samplepay-prod --operate up",
                log_text,
            )
            self.assertNotIn("systemctl start", log_text)

    def test_rollback_execute_runs_compose_down_and_systemd_start(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_tenant_secret_files(root)
            write_app_resource_registry(root, baseline_app_resource_registry_payload())
            write_contract(root, tenant_resources=baseline_tenant_resources())
            (root / "secrets" / "ssh").mkdir(parents=True, exist_ok=True)
            (root / "secrets" / "ssh" / "config").write_text("Host prod0-main\n", encoding="utf-8")
            bin_dir = root / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            log_file = root / "rollback.log"
            write_fake_command(
                bin_dir,
                "ssh",
                '#!/usr/bin/env bash\nset -euo pipefail\nprintf \'ssh %s\\n\' "$*" >> "$FAKE_CMD_LOG"\n',
            )

            result = run_app_delivery_cli(
                "rollback",
                repo_root=root,
                app="sub2api",
                extra_args=("--execute",),
                env_overrides={
                    "PATH": f"{bin_dir}:{os.environ['PATH']}",
                    "FAKE_CMD_LOG": str(log_file),
                },
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)["payload"]
            self.assertTrue(payload["ok"])
            log_text = log_file.read_text(encoding="utf-8")
            self.assertIn("docker compose -f docker-compose.prod0.yml down || true", log_text)
            self.assertIn("systemctl enable --now sub2api || true", log_text)

    def test_deploy_dry_run_skips_transition_when_no_previous_control_plane(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_sampleapi_tenant_files(root)
            write_sampleapi_contract(
                root,
                rollback_entry={
                    "kind": "none",
                    "note": "no previous control plane retained; rollback requires manual image restore",
                },
            )
            write_sampleapi_compose_templates(root)

            result = run_app_delivery_cli(
                "deploy",
                repo_root=root,
                app="sampleapi",
                extra_args=("--image-ref", "sampleapi-prod:test", "--dry-run"),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            commands = "\n".join(payload["payload"]["commands"])
            self.assertNotIn("agentplane/scripts/onepanel/app_lifecycle.py", commands)
            self.assertNotIn("agentplane/scripts/onepanel/project_lifecycle.py", commands)
            self.assertNotIn("systemctl stop", commands)
            self.assertIn("docker compose -f docker-compose.prod0.yml up -d", commands)

    def test_rollback_dry_run_warns_when_no_previous_control_plane(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_sampleapi_tenant_files(root)
            write_sampleapi_contract(
                root,
                rollback_entry={
                    "kind": "none",
                    "note": "no previous control plane retained; rollback requires manual image restore",
                },
            )
            write_sampleapi_compose_templates(root)

            result = run_app_delivery_cli(
                "rollback",
                repo_root=root,
                app="sampleapi",
                extra_args=("--dry-run",),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual([], payload["payload"]["commands"])
            self.assertIn("manual image restore", payload["payload"]["warning"])


# ======================================================================
# From: test_app_delivery_render_verify_cli.py
# ======================================================================


