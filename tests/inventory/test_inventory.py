from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pytest
from agentplane.cli.inventory import generate_inventory_snapshot
from agentplane.scripts.onepanel.ledger import _tenant_rows
from tests.support.cli import run_agentplane_cli as run_cli
from tests.support.paths import REPO_ROOT

pytestmark = pytest.mark.integration


class InventoryGenerationTests(unittest.TestCase):
    def test_focused_acceptance_commands_are_documented_as_readonly_or_dry_run(self) -> None:
        versioning_doc = (REPO_ROOT / "docs" / "archive" / "reference" / "app-delivery-versioning.md").read_text(encoding="utf-8")
        self.assertIn("Focused Acceptance", versioning_doc)
        self.assertIn("focused acceptance", versioning_doc)
        self.assertIn("infra automation search wsl", versioning_doc)
        self.assertIn("projection ledger refresh --target wsl", versioning_doc)
        self.assertIn("app delivery build-artifact", versioning_doc)
        self.assertIn("--dry-run", versioning_doc)
        self.assertIn("仅允许只读或 dry-run", versioning_doc)

    @pytest.mark.integration_wsl
    def test_phase4_lane12_host_automation_search_acceptance_is_readonly(self) -> None:
        result = run_cli("infra", "automation", "search", "wsl", "--repo-root", str(REPO_ROOT), cwd=REPO_ROOT)
        self.assertEqual(result.returncode, 0, msg=result.stderr)

        payload = json.loads(result.stdout)
        self.assertEqual("infra", payload.get("command"))
        self.assertEqual("automation.search", payload.get("action"))
        self.assertEqual("wsl", payload.get("target"))
        self.assertIn("items", payload["payload"])
        self.assertGreaterEqual(len(payload["payload"]["items"]), 1)

    @pytest.mark.integration_wsl
    def test_phase4_lane12_projection_ledger_refresh_acceptance_defaults_to_readonly(self) -> None:
        result = run_cli(
            "project", "projection", "ledger", "refresh", "--target", "wsl", "--repo-root", str(REPO_ROOT), cwd=REPO_ROOT
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)

        payload = json.loads(result.stdout)
        self.assertEqual("project", payload.get("command"))
        self.assertEqual("ledger.refresh", payload.get("action"))
        self.assertEqual("wsl", payload.get("target"))
        self.assertIn("ledger_root", payload)

    def test_projection_only_templates_and_pointer_files_reference_canonical_sources(self) -> None:
        projection_only_templates = {
            REPO_ROOT / "templates" / "services" / "minio.env.example": "templates/services/minio/admin.env.example",
            REPO_ROOT
            / "templates"
            / "services"
            / "postgres.env.example": "templates/services/postgres/admin.env.example",
            REPO_ROOT / "templates" / "services" / "redis.conf.example": "templates/services/redis/admin.env.example",
        }
        for path, canonical in projection_only_templates.items():
            with self.subTest(path=str(path)):
                content = path.read_text(encoding="utf-8").lower()
                self.assertIn(canonical.lower(), content)
                self.assertRegex(content, r"(legacy|transitional|projection-only|projection only)")

        pointer_files = {
            REPO_ROOT
            / "infra"
            / "compose"
            / "cliproxyapi"
            / "config.yaml": "templates/services/cliproxyapi.config.yaml.example",
            REPO_ROOT / "infra" / "compose" / "redis" / "redis.conf": "templates/services/redis.conf.example",
        }
        for path, canonical in pointer_files.items():
            with self.subTest(path=str(path)):
                content = path.read_text(encoding="utf-8").lower()
                self.assertIn(canonical.lower(), content)
                self.assertRegex(content, r"(pointer|placeholder|projection)")

    def test_tenant_rows_skip_registry_scaffolding_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            server_root = Path(tmp)
            registry_file = server_root / "app-resources.json"
            registry_file.write_text(
                json.dumps(
                    {
                        "_meta": {"infra": "prod0-main"},
                        "infrastructure": {"postgres": {"status": "running"}},
                        "app_resources": {"sampleapi": {"owner_app": "sampleapi"}},
                        "sampleapi": {"owner_app": "sampleapi"},
                        "sub2api": {"owner_app": "sub2api"},
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            rows = _tenant_rows(server_root)

        self.assertEqual(["sampleapi", "sub2api"], [row["app_id"] for row in rows])

    @pytest.mark.docker_required
    def test_inventory_separates_managed_and_unmanaged_containers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service_dir = root / "infra" / "compose" / "redis"
            service_dir.mkdir(parents=True, exist_ok=True)
            (service_dir / "docker-compose.wsl.yml").write_text("services: {}\n", encoding="utf-8")
            managed_config = str(service_dir / "docker-compose.wsl.yml")

            rows = [
                {
                    "name": "redis7-dev",
                    "image": "redis:7.4.7",
                    "ports": "0.0.0.0:6379->6379/tcp",
                    "status": "Up 1 minute",
                    "labels": {"com.docker.compose.project.config_files": managed_config},
                },
                {
                    "name": "foreign-service",
                    "image": "busybox:latest",
                    "ports": "",
                    "status": "Up 1 minute",
                    "labels": {"com.docker.compose.project.config_files": "/tmp/foreign/docker-compose.yml"},
                },
            ]

            with (
                patch("agentplane.domain.infra.inventory._wsl_backend_type", return_value="linux-native"),
                patch(
                    "agentplane.domain.infra.inventory._docker_container_rows",
                    return_value=rows,
                ),
            ):
                payload = generate_inventory_snapshot(root, "wsl")["payload"]

            self.assertEqual(["redis"], payload["compose_services"])
            self.assertEqual(["redis7-dev"], [item["name"] for item in payload["docker_containers"]])
            self.assertEqual(["foreign-service"], [item["name"] for item in payload["unmanaged_docker_containers"]])

    @pytest.mark.integration_wsl
    def test_inventory_command_outputs_wsl_snapshot(self) -> None:
        result = run_cli("infra", "inventory", "wsl", "--repo-root", str(REPO_ROOT), cwd=REPO_ROOT)
        self.assertEqual(result.returncode, 0, msg=result.stderr)

        payload = json.loads(result.stdout)
        self.assertEqual({"command", "action", "target", "payload"}, set(payload))
        self.assertEqual("infra", payload.get("command"))
        self.assertEqual("inventory", payload.get("action"))
        self.assertEqual("wsl", payload.get("target"))
        self.assertIsInstance(payload["payload"], dict)

    @pytest.mark.ssh_required
    def test_inventory_snapshot_preserves_automation_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory_file = root / "inventory" / "servers" / "wsl" / "inventory.json"
            inventory_file.parent.mkdir(parents=True, exist_ok=True)
            inventory_file.write_text(
                json.dumps(
                    {
                        "automations": [
                            {
                                "name": "wsl-zzz-skills-sync",
                                "controller": "1panel-cronjob",
                            }
                        ]
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            payload = generate_inventory_snapshot(root, "wsl")["payload"]

            self.assertIn("automations", payload)
            self.assertEqual("wsl-zzz-skills-sync", payload["automations"][0]["name"])

    @pytest.mark.ssh_required
    def test_inventory_snapshot_preserves_host_truth_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory_file = root / "inventory" / "servers" / "wsl" / "inventory.json"
            inventory_file.parent.mkdir(parents=True, exist_ok=True)
            inventory_file.write_text(
                json.dumps(
                    {
                        "host_truth": {
                            "control_plane_inventory": "uv run python -m agentplane.cli infra inventory wsl --repo-root <repo-root>",
                            "last_ledger_refresh": "2026-04-02T12:04:12.394460+00:00",
                        }
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            payload = generate_inventory_snapshot(root, "wsl")["payload"]

            self.assertIn("host_truth", payload)
            self.assertEqual(
                "uv run python -m agentplane.cli infra inventory wsl --repo-root <repo-root>",
                payload["host_truth"]["control_plane_inventory"],
            )

    def test_inventory_command_handles_missing_prod0_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "inventory" / "servers").mkdir(parents=True, exist_ok=True)
            result = run_cli("infra", "inventory", "prod0-main", "--repo-root", str(root), cwd=REPO_ROOT)
            self.assertEqual(result.returncode, 0, msg=result.stderr)

            payload = json.loads(result.stdout)
            self.assertEqual({"command", "action", "target", "payload"}, set(payload))
            self.assertEqual("infra", payload.get("command"))
            self.assertEqual("inventory", payload.get("action"))
            self.assertEqual("prod0-main", payload.get("target"))
            self.assertIsInstance(payload["payload"], dict)


# ======================================================================
# From: test_observation_contracts.py
# ======================================================================


def write_app_object_fixture(root: Path) -> Path:
    target = "prod0-main"
    server_root = root / "inventory" / "servers" / target
    server_root.mkdir(parents=True, exist_ok=True)
    (server_root / "inventory.json").write_text(
        json.dumps(
            {
                "services": {
                    "sub2api": {
                        "control_plane": "compose",
                        "public_url": "https://token.example.net:8443",
                    }
                },
                "object_ledgers": {"ledgers": {"apps": f"inventory/servers/{target}/ledgers/apps.json"}},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    ledger_root = server_root / "ledgers"
    ledger_root.mkdir(parents=True, exist_ok=True)
    (ledger_root / "apps.json").write_text(json.dumps({"count": 1}, ensure_ascii=False, indent=2), encoding="utf-8")
    (ledger_root / "apps.md").write_text("# apps\n", encoding="utf-8")

    catalog_root = root / "inventory" / "apps"
    catalog_root.mkdir(parents=True, exist_ok=True)
    app_root = root / "sub2api"
    (catalog_root / "catalog.json").write_text(
        json.dumps(
            {
                "apps": [
                    {
                        "app": "sub2api",
                        "repo_name": "sub2api",
                        "repo_root": str(app_root),
                        "service_key": "sub2api",
                        "contracts": {"prod0-main": "deploy/agentplane/contract.yaml"},
                    }
                ]
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    contract_file = app_root / "deploy" / "agentplane" / "contract.yaml"
    contract_file.parent.mkdir(parents=True, exist_ok=True)
    contract_file.write_text(
        json.dumps({"docs": {"app_summary_file": "docs/AGENTPLANE_DEPLOYMENT.md"}}),
        encoding="utf-8",
    )
    summary_file = app_root / "docs" / "AGENTPLANE_DEPLOYMENT.md"
    summary_file.parent.mkdir(parents=True, exist_ok=True)
    summary_file.write_text("# summary\n", encoding="utf-8")
    return contract_file.resolve()


class ObservationContractTests(unittest.TestCase):
    def test_verification_payload_keeps_resolved_path_out_of_ledger_fields(self) -> None:
        from agentplane.runtime.observation import build_verification_payload

        payload = build_verification_payload(
            canonical_ref="apps/sub2api/contracts/prod0-main",
            ledger_fields={"app": "sub2api"},
            verification_fields={"check": "ok"},
            resolved_path="D:/Projects/AgentPlane/.cache/runtime/contract.yaml",
        )

        self.assertEqual("apps/sub2api/contracts/prod0-main", payload["ledger_fields"]["canonical_ref"])
        self.assertEqual("sub2api", payload["ledger_fields"]["app"])
        self.assertNotIn("resolved_path", payload["ledger_fields"])
        self.assertEqual(
            "D:/Projects/AgentPlane/.cache/runtime/contract.yaml",
            payload["verification_fields"]["resolved_path"],
        )

    def test_extract_ledger_fields_drops_observation_only_keys(self) -> None:
        from agentplane.runtime.observation import extract_ledger_fields

        payload = extract_ledger_fields(
            {
                "canonical_ref": "targets/prod0-main/services/postgres",
                "name": "postgres",
                "verification_fields": {"live": {"ok": True}},
                "observation": {"resolved_path": "D:/tmp/runtime.json"},
                "resolved_path": "D:/tmp/runtime.json",
            }
        )

        self.assertEqual("targets/prod0-main/services/postgres", payload["canonical_ref"])
        self.assertEqual("postgres", payload["name"])
        self.assertNotIn("verification_fields", payload)
        self.assertNotIn("observation", payload)
        self.assertNotIn("resolved_path", payload)

    def test_app_object_verify_separates_ledger_fields_and_observation(self) -> None:
        from agentplane.domain.app.object_handlers import verify_app_object

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            contract_file = write_app_object_fixture(root)

            payload = verify_app_object(root, "prod0-main", "sub2api")

        self.assertTrue(payload["ok"])
        self.assertEqual("apps/sub2api/contracts/prod0-main", payload["canonical_ref"])
        self.assertEqual("apps/sub2api/contracts/prod0-main", payload["ledger_fields"]["canonical_ref"])
        self.assertEqual("sub2api", payload["ledger_fields"]["app"])
        self.assertNotIn("resolved_path", payload["ledger_fields"])
        self.assertEqual(str(contract_file), payload["verification_fields"]["resolved_path"])
        self.assertEqual(str(contract_file), payload["observation"]["resolved_path"])
        self.assertIn("summary_files", payload["verification_fields"])
