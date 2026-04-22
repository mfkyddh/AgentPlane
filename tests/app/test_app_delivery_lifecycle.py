from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_contract(app_root: Path, *, app_id: str, container_name: str | None = None) -> Path:
    contract = {
        "schema_version": 1,
        "app_id": app_id,
        "artifact": {
            "build_command": "bash deploy/package-runtime-image.sh",
            "image_name": f"{app_id}-prod",
            "image_tag_rule": "<upstream>-zzz.<yyyymmdd>.v<n>.g<gitsha>",
        },
        "runtime": {
            "kind": "compose",
            "container_name": container_name or f"{app_id}-dev",
            "container_port": 8080,
            "host_binding": "127.0.0.1:18080",
            "healthcheck": {"path": "/health", "expected_status": 200},
            "env_template": "deploy/.env.example",
        },
        "infra": {"depends_on_containers": ["backend-prod"]},
        "ingress": {
            "mode": "public",
            "public_sites": [
                {
                    "alias": "app",
                    "domain": "demo.local",
                    "public_url": "http://127.0.0.1:18080",
                    "website_object": "demo",
                }
            ],
        },
        "data": {"mounts": [{"host_path": f"/data/{app_id}/data", "container_path": "/app/data"}]},
        "rollback": {"previous_control_plane": {"kind": "none", "note": "first onboarding"}},
        "docs": {"app_summary_file": "docs/AGENTPLANE_DEPLOYMENT.md"},
        "inventory": {"service_key": app_id},
    }
    contract_file = app_root / "contract.yaml"
    contract_file.write_text(yaml.safe_dump(contract, sort_keys=False, allow_unicode=False), encoding="utf-8")
    return contract_file


def _write_catalog(
    repo_root: Path,
    *,
    app: str,
    app_root: Path,
    contract_file: Path,
    target: str = "wsl",
) -> Path:
    catalog = {
        "apps": [
            {
                "app": app,
                "repo_name": app_root.name,
                "repo_root": str(app_root),
                "service_key": app,
                "contracts": {target: contract_file.name},
            }
        ]
    }
    path = repo_root / "inventory" / "apps" / "catalog.json"
    _write_json(path, catalog)
    return path


def _write_inventory(
    repo_root: Path,
    *,
    target: str,
    include_app_service: bool,
    app_service_key: str,
    ssh_user: str | None = None,
) -> Path:
    services: dict[str, object] = {
        "backend": {"container_name": "backend-prod"},
    }
    if include_app_service:
        services[app_service_key] = {"container_name": f"{app_service_key}-dev", "control_plane": "compose"}
    payload: dict[str, object] = {"services": services}
    if ssh_user is not None:
        payload["ssh"] = {"aliases": [target], "user": ssh_user}
    path = repo_root / "inventory" / "servers" / target / "inventory.json"
    _write_json(path, payload)
    return path


def _write_app_resources_registry(repo_root: Path, *, target: str, app_id: str) -> Path:
    path = repo_root / "inventory" / "servers" / target / "app-resources.json"
    _write_json(path, {app_id: {}})
    return path


class AppDeliveryLifecycleTests(unittest.TestCase):
    def test_onboard_sequences_validation_then_projection_inventory_doc_sync(self) -> None:
        from agentplane.domain.app.delivery_handlers import onboard_for_app

        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            app_id = "demoapp"
            contract_file = _write_contract(repo_root, app_id=app_id)
            _write_catalog(repo_root, app=app_id, app_root=repo_root, contract_file=contract_file)
            _write_inventory(repo_root, target="wsl", include_app_service=False, app_service_key=app_id)
            _write_app_resources_registry(repo_root, target="wsl", app_id=app_id)

            result = onboard_for_app(repo_root, target="wsl", app=app_id, dry_run=True, write=False)
            payload = result["payload"]

            self.assertTrue(payload["ok"])
            actions = [step["action"] for step in payload["sequence"]]
            self.assertEqual("app.delivery.validate-contract", actions[0])
            self.assertIn("app.delivery.onboard.catalog", actions)
            self.assertIn("app.delivery.onboard.app-resource-truth", actions)
            self.assertIn("app.delivery.onboard.service-truth", actions)
            self.assertIn("app.delivery.onboard.website-truth", actions)
            self.assertIn("projection.runtime-env.plan", actions)
            self.assertIn("app.delivery.inventory-refresh", actions)
            self.assertIn("app.delivery.doc-sync", actions)
            self.assertFalse((repo_root / "inventory" / "servers" / "wsl" / "README.md").exists())

    def test_offboard_produces_dry_run_plan_and_write_mode_removes_tracked_truth(self) -> None:
        from agentplane.domain.app.delivery_handlers import offboard_for_app

        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            app_id = "demoapp"
            contract_file = _write_contract(repo_root, app_id=app_id)
            catalog_file = _write_catalog(repo_root, app=app_id, app_root=repo_root, contract_file=contract_file)
            inventory_file = _write_inventory(repo_root, target="wsl", include_app_service=True, app_service_key=app_id)
            _write_app_resources_registry(repo_root, target="wsl", app_id=app_id)

            env_file = repo_root / "secrets" / "services" / f"{app_id}.wsl.env"
            env_file.parent.mkdir(parents=True, exist_ok=True)
            env_file.write_text("FOO=bar\n", encoding="utf-8")

            dry_run = offboard_for_app(repo_root, target="wsl", app=app_id, dry_run=True, write=False)
            dry_payload = dry_run["payload"]
            self.assertTrue(dry_payload["ok"])
            dry_actions = [step["action"] for step in dry_payload["steps"]]
            self.assertIn("app.delivery.offboard.website-truth", dry_actions)
            self.assertIn("app.delivery.offboard.service-truth", dry_actions)
            self.assertIn("app.delivery.offboard.app-resource-truth", dry_actions)
            self.assertIn("app.delivery.offboard.secrets", dry_actions)
            self.assertIn("app.delivery.offboard.catalog", dry_actions)
            self.assertTrue(catalog_file.exists())
            self.assertTrue(inventory_file.exists())
            self.assertTrue(env_file.exists())

            applied = offboard_for_app(repo_root, target="wsl", app=app_id, dry_run=False, write=True)
            apply_payload = applied["payload"]
            self.assertTrue(apply_payload["ok"])

            catalog_text = catalog_file.read_text(encoding="utf-8")
            self.assertNotIn(f"\"app\": \"{app_id}\"", catalog_text)
            inventory_text = inventory_file.read_text(encoding="utf-8")
            self.assertNotIn(f"\"{app_id}\"", inventory_text)
            self.assertFalse(env_file.exists())
            registry_text = (repo_root / "inventory" / "servers" / "wsl" / "app-resources.json").read_text(encoding="utf-8")
            self.assertNotIn(f"\"{app_id}\"", registry_text)
            self.assertTrue((repo_root / "inventory" / "servers" / "wsl" / "README.md").is_file())

    def test_verify_dry_run_exposes_backend_execution_steps(self) -> None:
        from agentplane.domain.app.delivery_handlers import verify_delivery_for_app

        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            app_id = "demoapp"
            contract_file = _write_contract(repo_root, app_id=app_id, container_name=f"{app_id}-prod")
            _write_catalog(repo_root, app=app_id, app_root=repo_root, contract_file=contract_file, target="prod0-main")
            _write_inventory(
                repo_root,
                target="prod0-main",
                include_app_service=True,
                app_service_key=app_id,
                ssh_user="root",
            )
            _write_app_resources_registry(repo_root, target="prod0-main", app_id=app_id)

            payload = verify_delivery_for_app(
                repo_root,
                target="prod0-main",
                app=app_id,
                dry_run=True,
                execute=False,
            )["payload"]

            self.assertEqual("ssh-linux", payload["backend_type"])
            self.assertEqual("ssh-linux", payload["execution_steps"][0]["plan"]["backend_type"])
            self.assertEqual("ssh-linux", payload["execution_steps"][0]["backend"]["backend_type"])
            self.assertIn("docker inspect demoapp-prod", payload["commands"][0])


if __name__ == "__main__":
    unittest.main()

