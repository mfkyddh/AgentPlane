import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agentplane.domain.app.runtime import _render_server_readme
from agentplane.cli.inventory import generate_inventory_snapshot
from agentplane.scripts.onepanel.ledger import _markdown_for, _render_readme_projection, _tenant_rows

REPO_ROOT = Path(__file__).resolve().parents[2]


def run_cli(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "agentplane.cli", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


class InventoryGenerationTests(unittest.TestCase):
    def test_focused_acceptance_commands_are_documented_as_readonly_or_dry_run(self) -> None:
        versioning_doc = (REPO_ROOT / "docs" / "reference" / "app-delivery-versioning.md").read_text(encoding="utf-8")
        self.assertIn("Focused Acceptance", versioning_doc)
        self.assertIn("focused acceptance", versioning_doc)
        self.assertIn("host automation search wsl", versioning_doc)
        self.assertIn("projection ledger refresh --target wsl", versioning_doc)
        self.assertIn("app delivery build-artifact", versioning_doc)
        self.assertIn("--dry-run", versioning_doc)
        self.assertIn("仅允许只读或 dry-run", versioning_doc)

    def test_phase4_lane12_host_automation_search_acceptance_is_readonly(self) -> None:
        result = run_cli("infra", "automation", "search", "wsl", "--repo-root", str(REPO_ROOT), cwd=REPO_ROOT)
        self.assertEqual(result.returncode, 0, msg=result.stderr)

        payload = json.loads(result.stdout)
        self.assertEqual("infra", payload.get("command"))
        self.assertEqual("automation.search", payload.get("action"))
        self.assertEqual("wsl", payload.get("target"))
        self.assertIn("items", payload["payload"])
        self.assertGreaterEqual(len(payload["payload"]["items"]), 1)

    def test_phase4_lane12_projection_ledger_refresh_acceptance_defaults_to_readonly(self) -> None:
        result = run_cli("projection", "ledger", "refresh", "--target", "wsl", "--repo-root", str(REPO_ROOT), cwd=REPO_ROOT)
        self.assertEqual(result.returncode, 0, msg=result.stderr)

        payload = json.loads(result.stdout)
        self.assertEqual("projection", payload.get("command"))
        self.assertEqual("ledger.refresh", payload.get("action"))
        self.assertEqual("wsl", payload.get("target"))
        self.assertIn("ledger_root", payload)

    def test_projection_only_templates_and_pointer_files_reference_canonical_sources(self) -> None:
        projection_only_templates = {
            REPO_ROOT / "templates" / "services" / "minio.env.example": "templates/services/minio/admin.env.example",
            REPO_ROOT / "templates" / "services" / "postgres.env.example": "templates/services/postgres/admin.env.example",
            REPO_ROOT / "templates" / "services" / "redis.conf.example": "templates/services/redis/admin.env.example",
        }
        for path, canonical in projection_only_templates.items():
            with self.subTest(path=path):
                content = path.read_text(encoding="utf-8").lower()
                self.assertIn(canonical.lower(), content)
                self.assertRegex(content, r"(legacy|transitional|projection-only|projection only)")

        pointer_files = {
            REPO_ROOT / "infra" / "compose" / "cliproxyapi" / "config.yaml": "templates/services/cliproxyapi.config.yaml.example",
            REPO_ROOT / "infra" / "compose" / "redis" / "redis.conf": "templates/services/redis.conf.example",
        }
        for path, canonical in pointer_files.items():
            with self.subTest(path=path):
                content = path.read_text(encoding="utf-8").lower()
                self.assertIn(canonical.lower(), content)
                self.assertRegex(content, r"(pointer|placeholder|projection)")

    def test_server_readme_renderer_marks_json_as_machine_source(self) -> None:
        inventory_payload = json.loads(
            (REPO_ROOT / "inventory" / "servers" / "prod2-main" / "inventory.json").read_text(encoding="utf-8")
        )

        rendered = _render_server_readme("prod2-main", inventory_payload)
        self.assertIn("机器真源：`inventory/servers/prod2-main/inventory.json`", rendered)
        self.assertIn("README 只保留非敏感摘要", rendered)

        for path in (
            REPO_ROOT / "inventory" / "servers" / "wsl" / "README.md",
            REPO_ROOT / "inventory" / "servers" / "prod0-main" / "README.md",
            REPO_ROOT / "inventory" / "servers" / "prod2-main" / "README.md",
        ):
            with self.subTest(path=path):
                content = path.read_text(encoding="utf-8")
                self.assertIn("机器真源：", content)
                self.assertIn("README 只保留非敏感摘要", content)

    def test_onepanel_readme_projection_uses_repo_root_placeholder(self) -> None:
        rendered = _render_readme_projection("prod0-main", {"websites": 1}, {})

        self.assertIn("--repo-root <repo-root> --write", rendered)
        self.assertNotIn("/root/work/AgentPlane", rendered)
        self.assertIn("--repo-root <repo-root> --write", (REPO_ROOT / "inventory" / "servers" / "prod0-main" / "README.md").read_text(encoding="utf-8"))

    def test_tenant_rows_skip_registry_scaffolding_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            server_root = Path(tmp)
            registry_file = server_root / "app-resources.json"
            registry_file.write_text(
                json.dumps(
                    {
                        "_meta": {"infra": "prod2-main"},
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

    def test_ledger_markdown_is_projection_only_summary(self) -> None:
        rendered = _markdown_for("app_resources", [{"app_id": "sampleapi"}])
        self.assertIn("Markdown 摘要投影", rendered)
        self.assertIn("对应 JSON 真源", rendered)

        for path in sorted((REPO_ROOT / "inventory" / "servers").glob("*/ledgers/app_resources.md")):
            with self.subTest(path=path):
                content = path.read_text(encoding="utf-8")
                self.assertIn("Markdown 摘要投影", content)
                self.assertIn("对应 JSON 真源", content)

        prod2_tenants = (
            REPO_ROOT / "inventory" / "servers" / "prod2-main" / "ledgers" / "app_resources.md"
        ).read_text(
            encoding="utf-8"
        )
        self.assertNotIn("`_meta`", prod2_tenants)
        self.assertNotIn("`infrastructure`", prod2_tenants)
        self.assertNotIn("`app_resources`", prod2_tenants)

    def test_app_resource_markdown_is_summary_projection(self) -> None:
        for path in (
            REPO_ROOT / "inventory" / "servers" / "prod0-main" / "ledgers" / "app_resources.md",
            REPO_ROOT / "inventory" / "servers" / "prod2-main" / "ledgers" / "app_resources.md",
        ):
            with self.subTest(path=path):
                content = path.read_text(encoding="utf-8")
                self.assertIn("Markdown 摘要投影", content)
                self.assertIn("机器真源：", content)

    def test_real_app_ledgers_are_empty_after_local_app_delivery_offboarding(self) -> None:
        for target in ("wsl", "prod0-main", "prod2-main"):
            with self.subTest(target=target):
                ledger_json = json.loads(
                    (REPO_ROOT / "inventory" / "servers" / target / "ledgers" / "apps.json").read_text(encoding="utf-8")
                )
                self.assertEqual([], ledger_json["items"])
                self.assertEqual(0, ledger_json["count"])

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

            with patch("agentplane.cli.inventory._wsl_backend_type", return_value="linux-native"), patch(
                "agentplane.cli.inventory._docker_container_rows",
                return_value=rows,
            ):
                payload = generate_inventory_snapshot(root, "wsl")["payload"]

            self.assertEqual(["redis"], payload["compose_services"])
            self.assertEqual(["redis7-dev"], [item["name"] for item in payload["docker_containers"]])
            self.assertEqual(["foreign-service"], [item["name"] for item in payload["unmanaged_docker_containers"]])

    def test_inventory_command_outputs_wsl_snapshot(self) -> None:
        result = run_cli("infra", "inventory", "wsl", "--repo-root", str(REPO_ROOT), cwd=REPO_ROOT)
        self.assertEqual(result.returncode, 0, msg=result.stderr)

        payload = json.loads(result.stdout)
        self.assertEqual({"command", "action", "target", "payload"}, set(payload))
        self.assertEqual("infra", payload.get("command"))
        self.assertEqual("inventory", payload.get("action"))
        self.assertEqual("wsl", payload.get("target"))
        self.assertIsInstance(payload["payload"], dict)

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

    def test_inventory_snapshot_preserves_host_truth_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory_file = root / "inventory" / "servers" / "wsl" / "inventory.json"
            inventory_file.parent.mkdir(parents=True, exist_ok=True)
            inventory_file.write_text(
                json.dumps(
                    {
                        "host_truth": {
                            "control_plane_inventory": "uv run python -m agentplane.cli host inventory wsl --repo-root <repo-root>",
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
                "uv run python -m agentplane.cli host inventory wsl --repo-root <repo-root>",
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


if __name__ == "__main__":
    unittest.main()

