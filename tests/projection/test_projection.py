from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from tests.support.app_resources import resource_relative, resource_root
from tests.support.cli import run_agentplane_cli as run_cli
from tests.support.paths import REPO_ROOT

pytestmark = pytest.mark.integration


def write_inventory(root: Path) -> None:
    inventory_file = root / "inventory" / "servers" / "prod0-main" / "inventory.json"
    inventory_file.parent.mkdir(parents=True, exist_ok=True)
    inventory_file.write_text(
        json.dumps(
            {
                "services": {
                    "sub2api": {
                        "control_plane": "compose",
                        "container_name": "sub2api-prod",
                    }
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def write_registry(root: Path) -> None:
    registry_file = root / "inventory" / "servers" / "prod0-main" / "app-resources.json"
    registry_file.parent.mkdir(parents=True, exist_ok=True)
    registry_file.write_text(
        json.dumps(
            {
                "sub2api": {
                    "owner_app": "sub2api",
                    "postgres": {"database": "sub2api_prod2", "user": "sub2api_prod2"},
                    "redis": {"db": 1, "key_prefix": "sub2api:"},
                    "secret_files": [
                        resource_relative("prod0-main", "sub2api", "postgres"),
                        resource_relative("prod0-main", "sub2api", "redis"),
                    ],
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def write_resource_secrets(root: Path) -> None:
    resource_dir = resource_root(root, "prod0-main", "sub2api")
    resource_dir.mkdir(parents=True, exist_ok=True)
    (resource_dir / "postgres.env").write_text(
        "PGHOST=postgres18-prod\nPGPORT=5432\nPGDATABASE=sub2api_prod2\nPGUSER=sub2api_prod2\nPGPASSWORD=secret\nPGSSLMODE=disable\n",
        encoding="utf-8",
    )
    (resource_dir / "redis.env").write_text(
        "REDIS_HOST=redis7-prod\nREDIS_PORT=6379\nREDIS_PASSWORD=secret\nREDIS_DB=1\nREDIS_KEY_PREFIX=sub2api:\nREDIS_ENABLE_TLS=false\n",
        encoding="utf-8",
    )


class ProjectionRuntimeEnvCliTests(unittest.TestCase):
    def test_runtime_env_plan_reports_missing_app_as_app_resource_registry_gap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_registry(root)
            write_resource_secrets(root)

            result = run_cli(
                "project", "projection", "runtime-env", "plan",
                "--target", "prod0-main", "--app", "sampleapi", "--repo-root", str(root),
            )

            self.assertNotEqual(result.returncode, 0)
            payload = json.loads(result.stdout)
            self.assertEqual("project", payload["command"])
            self.assertEqual("runtime-env.plan", payload["action"])
            self.assertFalse(payload["ok"])
            self.assertEqual("app.resource.registry_missing_app", payload["error"]["id"])

    @pytest.mark.integration_wsl
    def test_runtime_env_plan_returns_target_env_file_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_registry(root)
            write_resource_secrets(root)

            result = run_cli(
                "project", "projection", "runtime-env", "plan",
                "--target", "prod0-main", "--app", "sub2api", "--repo-root", str(root),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("project", payload["command"])
            self.assertEqual("runtime-env.plan", payload["action"])
            self.assertEqual(str(root / "secrets" / "services" / "sub2api.prod0.env"), payload["env_file"])
            self.assertFalse(payload["written"])
            self.assertIn("DATABASE_USER", payload["managed_keys"])
            self.assertNotIn("rendered_env", payload)
            self.assertNotIn("current_env", payload)
            self.assertNotIn("PGPASSWORD=secret", result.stdout)
            self.assertNotIn("REDIS_PASSWORD=secret", result.stdout)
            self.assertFalse((root / "secrets" / "services" / "sub2api.prod0.env").exists())

            revealed = run_cli(
                "project", "projection", "runtime-env", "plan",
                "--target", "prod0-main", "--app", "sub2api", "--repo-root", str(root),
                "--reveal-secrets",
            )

            self.assertEqual(revealed.returncode, 0, msg=revealed.stderr)
            revealed_payload = json.loads(revealed.stdout)
            self.assertIn("rendered_env", revealed_payload)
            self.assertIn("DATABASE_PASSWORD=secret", revealed_payload["rendered_env"])
            self.assertIn("REDIS_PASSWORD=secret", revealed_payload["rendered_env"])

    def test_runtime_env_verify_reports_missing_env_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_registry(root)
            write_resource_secrets(root)

            result = run_cli(
                "project", "projection", "runtime-env", "verify",
                "--target", "prod0-main", "--app", "sub2api", "--repo-root", str(root),
            )

            self.assertNotEqual(result.returncode, 0)
            payload = json.loads(result.stdout)
            self.assertEqual("project", payload["command"])
            self.assertEqual("runtime-env.verify", payload["action"])
            self.assertFalse(payload["ok"])
            self.assertEqual("projection.runtime_env_missing", payload["error"]["id"])

    def test_runtime_env_verify_reports_managed_key_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_registry(root)
            write_resource_secrets(root)
            env_file = root / "secrets" / "services" / "sub2api.prod0.env"
            env_file.parent.mkdir(parents=True, exist_ok=True)
            env_file.write_text(
                "DATABASE_USER=sub2api_prod2\nDATABASE_DBNAME=sub2api_prod2\nREDIS_PASSWORD=secret\nREDIS_DB=9\nJWT_SECRET=keep\n",
                encoding="utf-8",
            )

            result = run_cli(
                "project", "projection", "runtime-env", "verify",
                "--target", "prod0-main", "--app", "sub2api", "--repo-root", str(root),
            )

            self.assertNotEqual(result.returncode, 0)
            payload = json.loads(result.stdout)
            self.assertEqual("project", payload["command"])
            self.assertEqual("runtime-env.verify", payload["action"])
            self.assertFalse(payload["ok"])
            self.assertEqual("projection.runtime_env_drift", payload["error"]["id"])
            self.assertIn("REDIS_DB", payload["drift"]["managed_keys"])
            self.assertNotIn("expected", payload["drift"])
            self.assertNotIn("actual", payload["drift"])
            self.assertIn("expected_redacted", payload["drift"])
            self.assertIn("actual_redacted", payload["drift"])
            self.assertIn("REDIS_PASSWORD=<redacted>", payload["drift"]["actual_redacted"])
            self.assertIn("JWT_SECRET=<redacted>", payload["drift"]["actual_redacted"])
            self.assertNotIn("REDIS_PASSWORD=secret", result.stdout)
            self.assertNotIn("JWT_SECRET=keep", result.stdout)


class ProjectionValidationCliTests(unittest.TestCase):
    def test_projection_verification_run_wraps_suite_payload(self) -> None:
        from agentplane.cli.project import _handle_projection

        args = SimpleNamespace(
            project_action="projection",
            project_projection_surface="verification",
            project_projection_verification_action="run",
            target="wsl",
            profile="wsl-fixture",
            repo_root=str(REPO_ROOT),
            write_report=False,
            website_alias="",
            container_name="",
            project_name="",
            cronjob_id=None,
            cronjob_name="",
            app_name="",
            firewall_tab="port",
        )

        with (
            patch("agentplane.cli.project_projection.onepanel_target_executor", return_value=object()),
            patch(
                "agentplane.cli.project_projection.run_onepanel_verification_suite",
                return_value={"ok": True, "checks": []},
            ) as run_suite,
        ):
            payload = _handle_projection(args)

        self.assertEqual("project", payload["command"])
        self.assertEqual("verification.run", payload["action"])
        self.assertTrue(payload["ok"])
        self.assertEqual("wsl-fixture", run_suite.call_args.kwargs["profile"])
        self.assertEqual("wsl", run_suite.call_args.kwargs["env"])

    def test_projection_verification_run_redacts_sensitive_payload(self) -> None:
        from agentplane.cli.project import _handle_projection

        args = SimpleNamespace(
            project_action="projection",
            project_projection_surface="verification",
            project_projection_verification_action="run",
            target="wsl",
            profile="wsl-fixture",
            repo_root=str(REPO_ROOT),
            write_report=False,
            website_alias="",
            container_name="",
            project_name="",
            cronjob_id=None,
            cronjob_name="",
            app_name="",
            firewall_tab="port",
        )

        with (
            patch("agentplane.cli.project_projection.onepanel_target_executor", return_value=object()),
            patch(
                "agentplane.cli.project_projection.run_onepanel_verification_suite",
                return_value={"ok": True, "checks": [{"scope": "panel", "ok": True, "payload": {"apiKey": "secret"}}]},
            ),
        ):
            payload = _handle_projection(args)

        self.assertEqual("<redacted>", payload["checks"][0]["payload"]["apiKey"])

    def test_projection_fixture_apply_requires_execute(self) -> None:
        from agentplane.cli.project import _handle_projection

        args = SimpleNamespace(
            project_action="projection",
            project_projection_surface="fixture",
            project_projection_fixture_action="apply",
            target="wsl",
            profile="wsl-fixture",
            repo_root=str(REPO_ROOT),
            website_alias="",
            container_name="",
            project_name="",
            cronjob_name="",
            firewall_tab="",
            execute=False,
        )

        with self.assertRaisesRegex(ValueError, "--execute"):
            _handle_projection(args)

    def test_projection_fixture_cleanup_wraps_underlying_payload(self) -> None:
        from agentplane.cli.project import _handle_projection

        args = SimpleNamespace(
            project_action="projection",
            project_projection_surface="fixture",
            project_projection_fixture_action="cleanup",
            target="wsl",
            profile="wsl-fixture",
            repo_root=str(REPO_ROOT),
            website_alias="",
            container_name="",
            project_name="",
            cronjob_name="",
            firewall_tab="",
            execute=True,
        )

        with (
            patch("agentplane.cli.project_projection.resolve_fixture_spec", return_value=object()) as resolve_spec,
            patch("agentplane.cli.project_projection.onepanel_target_executor", return_value=object()),
            patch(
                "agentplane.cli.project_projection.cleanup_fixture",
                return_value={"ok": True, "items": [{"object": "project", "action": "down-project"}]},
            ) as cleanup_fixture,
        ):
            payload = _handle_projection(args)

        resolve_spec.assert_called_once_with(
            "wsl-fixture",
            env="wsl",
            website_alias="",
            container_name="",
            project_name="",
            cronjob_name="",
            firewall_tab="",
        )
        cleanup_fixture.assert_called_once()
        self.assertEqual("project", payload["command"])
        self.assertEqual("fixture.cleanup", payload["action"])
        self.assertTrue(payload["ok"])

    def test_projection_ledger_refresh_wraps_formal_envelope(self) -> None:
        from agentplane.cli.project import _handle_projection

        args = SimpleNamespace(
            project_action="projection",
            project_projection_surface="ledger",
            project_projection_ledger_action="refresh",
            target="prod0-main",
            repo_root=str(REPO_ROOT),
            write=True,
        )

        with patch(
            "agentplane.cli.project_projection.refresh_onepanel_ledgers",
            return_value={"counts": {"websites": 1}, "written": True},
        ) as refresh_ledgers:
            payload = _handle_projection(args)

        refresh_ledgers.assert_called_once_with(REPO_ROOT.resolve(), "prod0-main", write=True)
        self.assertEqual("project", payload["command"])
        self.assertEqual("ledger.refresh", payload["action"])
        self.assertEqual({"websites": 1}, payload["counts"])

    def test_repo_self_check_keeps_projection_scenario_workflows_out_of_daily_gate(self) -> None:
        self_check = (REPO_ROOT / "agentplane" / "scripts" / "internal" / "repo" / "self_check.sh").read_text(
            encoding="utf-8"
        )

        self.assertIn("projection verification / fixture / ledger remain scenario-specific workflows", self_check)
        self.assertIn("do not move them into the daily thin gate", self_check)
        self.assertNotIn("tests/test_projection_validation_cli.py", self_check)
        self.assertNotIn("tests/test_projection_runtime_env_cli.py", self_check)
        self.assertNotIn("tests/test_onepanel_fixture_manager.py", self_check)
        self.assertNotIn("tests/test_onepanel_verification_suite.py", self_check)
        self.assertNotIn("projection verification run", self_check)
        self.assertNotIn("projection fixture", self_check)
        self.assertNotIn("projection ledger refresh", self_check)


class ProjectionGoldenTests(unittest.TestCase):
    """Golden tests for the three-layer projection model.

    These tests verify that the output format of each projection layer
    is stable and reproducible.  If these tests break, the projection
    contract has changed and downstream consumers may be affected.
    """

    def test_layer1_inventory_snapshot_has_required_keys(self) -> None:
        from agentplane.domain.infra.inventory import generate_inventory_snapshot

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory_file = root / "inventory" / "servers" / "prod0-main" / "inventory.json"
            inventory_file.parent.mkdir(parents=True, exist_ok=True)
            inventory_file.write_text(
                json.dumps({"services": {"sub2api": {"control_plane": "compose"}}}, indent=2),
                encoding="utf-8",
            )
            result = generate_inventory_snapshot(root, "prod0-main")

        assert "command" in result
        assert "target" in result
        assert "inventory_file" in result
        assert "payload" in result
        assert result["command"] == "inventory"
        assert result["target"] == "prod0-main"

    def test_layer1_inventory_snapshot_payload_has_services(self) -> None:
        from agentplane.domain.infra.inventory import generate_inventory_snapshot

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory_file = root / "inventory" / "servers" / "prod0-main" / "inventory.json"
            inventory_file.parent.mkdir(parents=True, exist_ok=True)
            inventory_file.write_text(
                json.dumps({"services": {"sub2api": {"control_plane": "compose"}}}, indent=2),
                encoding="utf-8",
            )
            result = generate_inventory_snapshot(root, "prod0-main")

        assert "services" in result["payload"]
        assert "sub2api" in result["payload"]["services"]

    def test_layer2_app_ledger_has_required_keys(self) -> None:
        from agentplane.domain.app.object_handlers import refresh_app_ledger

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            result = refresh_app_ledger(root, "prod0-main", write=False)

        assert "target" in result
        assert "count" in result
        assert "json_file" in result
        assert "markdown_file" in result
        assert "inventory_pointer" in result
        assert result["target"] == "prod0-main"

    def test_layer2_app_ledger_json_structure(self) -> None:
        from agentplane.domain.app.object_handlers import refresh_app_ledger

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            result = refresh_app_ledger(root, "prod0-main", write=True)

            json_file = Path(result["json_file"])
            assert json_file.exists()
            ledger = json.loads(json_file.read_text(encoding="utf-8"))

        assert "target" in ledger
        assert "count" in ledger
        assert "items" in ledger
        assert ledger["target"] == "prod0-main"

    def test_layer2_app_ledger_markdown_structure(self) -> None:
        from agentplane.domain.app.object_handlers import refresh_app_ledger

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            result = refresh_app_ledger(root, "prod0-main", write=True)

            md_file = Path(result["markdown_file"])
            assert md_file.exists()
            content = md_file.read_text(encoding="utf-8")

        assert content.startswith("# prod0-main apps ledger")
        assert "- " in content

    def test_layer2_inventory_pointer_written(self) -> None:
        from agentplane.domain.app.object_handlers import refresh_app_ledger

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            refresh_app_ledger(root, "prod0-main", write=True)

            inventory_file = root / "inventory" / "servers" / "prod0-main" / "inventory.json"
            inventory = json.loads(inventory_file.read_text(encoding="utf-8"))

        assert "object_ledgers" in inventory
        assert "ledgers" in inventory["object_ledgers"]
        assert "apps" in inventory["object_ledgers"]["ledgers"]

    def test_layer3_app_summary_rendering(self) -> None:
        from agentplane.domain.app.doc_sync import _render_app_summary

        contract = {
            "app_id": "sub2api",
            "runtime": {"container_name": "sub2api-prod", "container_port": 8080},
        }
        inventory_entry = {
            "control_plane": "compose",
            "container_name": "sub2api-prod",
            "public_url": "https://sub2api.example.com",
        }
        summary = _render_app_summary(contract, "prod0-main", inventory_entry)

        assert "sub2api" in summary
        assert "prod0-main" in summary
        assert "sub2api-prod" in summary

    def test_layer2_ledger_idempotent_when_write_false(self) -> None:
        from agentplane.domain.app.object_handlers import refresh_app_ledger

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            r1 = refresh_app_ledger(root, "prod0-main", write=False)
            r2 = refresh_app_ledger(root, "prod0-main", write=False)

        assert r1 == r2
