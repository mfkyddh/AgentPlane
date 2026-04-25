from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import yaml
from tests.support.app_delivery_cli import run_app_delivery_cli
from tests.support.app_delivery_contracts import (
    sync_app_catalog_for_contract,
    write_contract,
    write_prod2_contract,
    write_sampleapi_contract,
)
from tests.support.app_delivery_targets import (
    baseline_tenant_resources,
    write_app_resource_registry,
    write_internal_worker_compose_template,
    write_inventory,
    write_prod2_inventory,
    write_prod2_tenant_registry,
    write_prod2_tenant_secret_files,
    write_sampleapi_compose_templates,
    write_sampleapi_tenant_files,
    write_tenant_secret_files,
)
from tests.support.app_resources import resource_relative
from tests.support.paths import REPO_ROOT


class TestAppDeliveryInventoryCliTests(unittest.TestCase):
    def test_inventory_refresh_writes_app_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_tenant_secret_files(root, include_minio=True)
            write_contract(root, tenant_resources=baseline_tenant_resources(include_minio=True))
            inventory_file = root / "inventory" / "servers" / "prod0-main" / "inventory.json"

            result = run_app_delivery_cli(
                "inventory-refresh",
                repo_root=root,
                app="sub2api",
                extra_args=("--write",),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            app_entry = payload["payload"]["services"]["sub2api"]
            self.assertEqual("compose", app_entry["control_plane"])
            self.assertEqual("sub2api-prod", app_entry["container_name"])
            self.assertEqual(["postgres18-prod", "redis7-prod"], app_entry["depends_on_containers"])
            self.assertEqual("https://token.zzzai.cloud:8443", app_entry["public_url"])
            self.assertEqual(["/data/sub2api/config/sub2api-prod.env"], app_entry["config_files"])
            self.assertEqual("sub2api_prod0", app_entry["app_resource_summary"]["postgres"]["database"])
            self.assertEqual("sub2api:", app_entry["app_resource_summary"]["redis"]["key_prefix"])
            self.assertNotIn("user", app_entry["app_resource_summary"]["redis"])
            self.assertEqual("prod0-sub2api", app_entry["app_resource_summary"]["minio"]["bucket"])
            self.assertEqual(
                resource_relative("prod0-main", "sub2api", "minio"),
                app_entry["app_resource_summary"]["minio"]["secret_file"],
            )
            written_payload = json.loads(inventory_file.read_text(encoding="utf-8"))
            self.assertEqual(
                ["/data/sub2api/config/sub2api-prod.env"],
                written_payload["services"]["sub2api"]["config_files"],
            )
            self.assertNotIn("user", written_payload["services"]["sub2api"]["app_resource_summary"]["redis"])

    def test_inventory_refresh_writes_wsl_target_specific_sampleapi_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_sampleapi_tenant_files(root, target="wsl")
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
            write_sampleapi_contract(root, target="wsl")
            write_sampleapi_compose_templates(root)

            result = run_app_delivery_cli(
                "inventory-refresh",
                repo_root=root,
                app="sampleapi",
                target="wsl",
                extra_args=("--write",),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            app_entry = payload["payload"]["services"]["sampleapi"]
            self.assertEqual("sampleapi-dev", app_entry["container_name"])
            self.assertEqual(["postgres18-dev", "redis7-dev"], app_entry["depends_on_containers"])
            self.assertEqual([str(root / "secrets" / "services" / "sampleapi.wsl.env")], app_entry["config_files"])
            self.assertEqual("0.0.0.0:3000", app_entry["host_binding"])
            self.assertEqual("http://127.0.0.1:3000", app_entry["public_url"])
            self.assertEqual(["zqf_network"], app_entry["docker_networks"])
            self.assertEqual("sampleapi_wsl", app_entry["app_resource_summary"]["postgres"]["database"])
            self.assertEqual("sampleapi:wsl:", app_entry["app_resource_summary"]["redis"]["key_prefix"])
            self.assertNotIn("user", app_entry["app_resource_summary"]["redis"])
            written_payload = json.loads((root / "inventory" / "servers" / "wsl" / "inventory.json").read_text(encoding="utf-8"))
            self.assertEqual(["zqf_network"], written_payload["services"]["sampleapi"]["docker_networks"])
            self.assertNotIn("user", written_payload["services"]["sampleapi"]["app_resource_summary"]["redis"])

    def test_inventory_refresh_wsl_uses_canonical_secrets_path_outside_worktree_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outer_root = Path(tmp) / "repo-root"
            worktree_root = outer_root / ".worktrees" / "codex" / "release"
            worktree_root.mkdir(parents=True, exist_ok=True)
            git_worktree_dir = outer_root / ".git" / "worktrees" / "release"
            git_worktree_dir.mkdir(parents=True, exist_ok=True)
            (worktree_root / ".git").write_text(f"gitdir: {git_worktree_dir}\n", encoding="utf-8")
            canonical_secrets = outer_root / "secrets" / "services"
            canonical_secrets.mkdir(parents=True, exist_ok=True)
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
            write_sampleapi_contract(worktree_root, target="wsl")
            write_sampleapi_compose_templates(worktree_root)

            result = run_app_delivery_cli(
                "inventory-refresh",
                repo_root=worktree_root,
                app="sampleapi",
                target="wsl",
                extra_args=("--write",),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            expected = str(outer_root / "secrets" / "services" / "sampleapi.wsl.env")
            self.assertEqual([expected], payload["payload"]["services"]["sampleapi"]["config_files"])
            written_payload = json.loads((worktree_root / "inventory" / "servers" / "wsl" / "inventory.json").read_text(encoding="utf-8"))
            self.assertEqual([expected], written_payload["services"]["sampleapi"]["config_files"])

    def test_inventory_refresh_keeps_1panel_compose_project_fields(self) -> None:
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

            result = run_app_delivery_cli(
                "inventory-refresh",
                repo_root=root,
                app="sampleapi",
                extra_args=("--write",),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            rollback_entry = json.loads(result.stdout)["payload"]["services"]["sampleapi"]["rollback_entry"]
            self.assertEqual("1panel-compose", rollback_entry["kind"])
            self.assertEqual("/data/1panel/docker/compose/samplepay-prod", rollback_entry["project_path"])
            self.assertEqual(
                "/data/1panel/docker/compose/samplepay-prod/docker-compose.yml",
                rollback_entry["compose_file"],
            )

    def test_inventory_refresh_writes_prod2_target_specific_sampleapi_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_prod2_inventory(root)
            write_app_resource_registry(
                root,
                {
                    "sampleapi": {
                        "owner_app": "sampleapi",
                        "postgres": {"database": "sampleapi_prod2", "user": "sampleapi_prod2"},
                        "redis": {"db": 2, "key_prefix": "sampleapi:"},
                        "minio": {
                            "bucket": "prod2-sampleapi",
                            "access_key": "sampleapi_prod2",
                            "policy_name": "prod2-sampleapi-rw",
                            "policy_scope": "bucket-only",
                            "isolation_level": "bucket-scoped-rw",
                        },
                        "secret_files": [
                            resource_relative("prod2-main", "sampleapi", "postgres"),
                            resource_relative("prod2-main", "sampleapi", "redis"),
                            resource_relative("prod2-main", "sampleapi", "minio"),
                        ],
                    }
                },
                target="prod2-main",
            )
            write_sampleapi_tenant_files(root, target="prod2-main", include_minio=True)
            write_sampleapi_contract(root, target="prod2-main", include_minio=True)
            write_sampleapi_compose_templates(root, include_prod2=True)
            inventory_file = root / "inventory" / "servers" / "prod2-main" / "inventory.json"

            result = run_app_delivery_cli(
                "inventory-refresh",
                repo_root=root,
                app="sampleapi",
                target="prod2-main",
                extra_args=("--write",),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            app_entry = payload["payload"]["services"]["sampleapi"]
            self.assertEqual("sampleapi-prod", app_entry["container_name"])
            self.assertEqual("https://sampleapi.zzzai.fun", app_entry["public_url"])
            self.assertEqual(["postgres18-prod", "redis7-prod", "minio-prod"], app_entry["depends_on_containers"])
            self.assertEqual(["/opt/agentplane/secrets/services/sampleapi.prod2.env"], app_entry["config_files"])
            self.assertEqual("sampleapi_prod2", app_entry["app_resource_summary"]["postgres"]["database"])
            self.assertEqual("prod2-sampleapi", app_entry["app_resource_summary"]["minio"]["bucket"])
            self.assertEqual(
                resource_relative("prod2-main", "sampleapi", "minio"),
                app_entry["app_resource_summary"]["minio"]["secret_file"],
            )
            written_payload = json.loads(inventory_file.read_text(encoding="utf-8"))
            self.assertEqual("https://sampleapi.zzzai.fun", written_payload["services"]["sampleapi"]["public_url"])
            self.assertEqual(
                ["/opt/agentplane/secrets/services/sampleapi.prod2.env"],
                written_payload["services"]["sampleapi"]["config_files"],
            )

    def test_inventory_refresh_internal_worker_uses_internal_probe_url(self) -> None:
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
            payload["runtime"]["config_files"] = ["/opt/agentplane/secrets/services/sample-register-v2.prod0.env"]
            payload["runtime"]["healthcheck"] = {"path": "/healthz", "expected_status": 200}
            payload["data"]["mounts"] = [{"host_path": "/data/sample-register-v2/data", "container_path": "/data"}]
            payload["inventory"]["service_key"] = "sample-register-v2"
            payload["inventory"]["remove_service_keys"] = ["chatgpt-register-wsl"]
            contract_file.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8")
            sync_app_catalog_for_contract(root, contract_file=contract_file, app="sample-register-v2", service_key="sample-register-v2")
            write_internal_worker_compose_template(root)
            inventory_payload = json.loads(inventory_file.read_text(encoding="utf-8"))
            inventory_payload["services"]["chatgpt-register-wsl"] = {
                "control_plane": "compose",
                "container_name": "sample-register-v2-wsl",
                "public_url": "http://127.0.0.1:18081",
            }
            inventory_file.write_text(json.dumps(inventory_payload, ensure_ascii=False, indent=2), encoding="utf-8")

            result = run_app_delivery_cli(
                "inventory-refresh",
                repo_root=root,
                app="sample-register-v2",
                extra_args=("--write",),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            app_entry = json.loads(result.stdout)["payload"]["services"]["sample-register-v2"]
            self.assertEqual("internal://127.0.0.1:18081", app_entry["public_url"])
            self.assertEqual(["sub2api-prod"], app_entry["depends_on_containers"])
            self.assertEqual(["/opt/agentplane/secrets/services/sample-register-v2.prod0.env"], app_entry["config_files"])
            refreshed_services = json.loads(result.stdout)["payload"]["services"]
            self.assertNotIn("chatgpt-register-wsl", refreshed_services)

    def test_repo_internal_worker_assets_no_legacy_wsl_compose_path(self) -> None:
        self.assertFalse((REPO_ROOT / "infra" / "compose" / "chatgpt-register-wsl").exists())
        self.assertFalse((REPO_ROOT / "templates" / "services" / "chatgpt-register-wsl.env.example").exists())
        wsl_inventory = json.loads((REPO_ROOT / "inventory" / "servers" / "wsl" / "inventory.json").read_text(encoding="utf-8"))
        compose_services = wsl_inventory.get("compose_services") or []
        self.assertIn("sub2api", compose_services)
        self.assertNotIn("sample-register-v2", compose_services)
        self.assertNotIn("chatgpt-register-wsl", compose_services)

    def test_repo_prod0_internal_worker_inventory_and_readme_are_offboarded(self) -> None:
        prod0_inventory = json.loads((REPO_ROOT / "inventory" / "servers" / "prod0-main" / "inventory.json").read_text(encoding="utf-8"))
        self.assertNotIn("sample-register-v2", prod0_inventory["services"])
        readme_text = (REPO_ROOT / "inventory" / "servers" / "prod0-main" / "README.md").read_text(encoding="utf-8")
        self.assertNotIn("sample-register-v2", readme_text)

    def test_inventory_refresh_writes_prod2_target_specific_sub2api_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_prod2_inventory(root)
            write_prod2_tenant_secret_files(root, include_minio=True)
            write_prod2_tenant_registry(root, include_minio=True)
            write_prod2_contract(root, include_minio=True)
            inventory_file = root / "inventory" / "servers" / "prod2-main" / "inventory.json"

            result = run_app_delivery_cli(
                "inventory-refresh",
                repo_root=root,
                app="sub2api",
                target="prod2-main",
                extra_args=("--write",),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            app_entry = payload["payload"]["services"]["sub2api"]
            self.assertEqual("sub2api-prod", app_entry["container_name"])
            self.assertEqual("https://token.zzzai.fun", app_entry["public_url"])
            self.assertEqual(["postgres18-prod", "redis7-prod"], app_entry["depends_on_containers"])
            self.assertEqual("sub2api_prod2", app_entry["app_resource_summary"]["postgres"]["database"])
            self.assertEqual("prod2-sub2api", app_entry["app_resource_summary"]["minio"]["bucket"])
            self.assertEqual(
                resource_relative("prod2-main", "sub2api", "minio"),
                app_entry["app_resource_summary"]["minio"]["secret_file"],
            )
            written_payload = json.loads(inventory_file.read_text(encoding="utf-8"))
            self.assertEqual("https://token.zzzai.fun", written_payload["services"]["sub2api"]["public_url"])


if __name__ == "__main__":
    unittest.main()

