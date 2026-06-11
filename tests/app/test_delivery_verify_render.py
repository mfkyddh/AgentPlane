from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

import pytest
import yaml
from tests.support.app_delivery_cli import run_app_delivery_cli
from tests.support.app_delivery_contracts import (
    sync_app_catalog_for_contract,
    write_contract,
    write_sampleapi_contract,
)
from tests.support.app_delivery_targets import (
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
from tests.support.app_resources import resource_relative
from tests.support.constants import FAKE_BINDING_18081

pytestmark = pytest.mark.integration


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
            payload["runtime"]["host_binding"] = FAKE_BINDING_18081
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

