from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from agentplane.domain.infra.onepanel import (
    handle_cronjob_action,
    handle_firewall_action,
    handle_panel_action,
    handle_task_action,
    onepanel_skeleton,
)
from agentplane.scripts.onepanel.object_api import (
    FakeLikeExecutorProtocol,
    build_app_install_params,
    get_panel_summary,
    load_firewall_base,
    plan_app_install,
    plan_firewall_operation,
    plan_installed_app_operation,
    search_cronjobs,
    search_firewall_rules,
)
from tests.support.cli import run_agentplane_cli as run_cli
from tests.support.paths import REPO_ROOT

pytestmark = pytest.mark.e2e


class FakeExecutor(FakeLikeExecutorProtocol):
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, object] | None]] = []

    def api_request(self, method: str, path: str, body: dict[str, object] | None = None) -> object:
        self.calls.append((method, path, body))
        if path == "/api/v2/core/settings/search":
            return {"systemVersion": "v2.1.7", "bindDomain": "1panel.example.com", "apiKey": "panel-secret-key"}
        if path == "/api/v2/core/settings/update":
            return {"ok": True}
        if path == "/api/v2/cronjobs/search":
            return {"items": [{"id": 2, "name": "backup-secrets", "status": "Enable"}]}
        if path == "/api/v2/hosts/firewall/base":
            return {
                "name": "ufw",
                "isExist": True,
                "isActive": True,
                "isInit": False,
                "isBind": False,
                "version": "0.36.2",
                "pingStatus": "1",
            }
        if path == "/api/v2/hosts/firewall/search":
            return {
                "items": [{"port": "22", "protocol": "tcp", "strategy": "accept", "description": "ssh"}],
                "total": 1,
            }
        if path == "/api/v2/hosts/firewall/operate":
            return {"ok": True}
        if path == "/api/v2/logs/tasks/executing/count":
            return {"executing": 0}
        if path == "/api/v2/logs/tasks/search":
            return {"items": [{"id": 1, "status": "success", "type": "cronjob"}], "total": 1}
        raise AssertionError(f"Unexpected request: {method} {path} {body}")


class OnePanelObjectApiTests(unittest.TestCase):
    def test_get_panel_summary_uses_v2_settings_endpoint(self) -> None:
        executor = FakeExecutor()

        result = get_panel_summary(executor)

        self.assertEqual("v2.1.7", result["systemVersion"])
        self.assertEqual(("POST", "/api/v2/core/settings/search", {}), executor.calls[0])

    def test_search_cronjobs_uses_expected_payload(self) -> None:
        executor = FakeExecutor()

        result = search_cronjobs(executor, info="backup")

        self.assertEqual("backup-secrets", result["items"][0]["name"])
        self.assertEqual(
            (
                "POST",
                "/api/v2/cronjobs/search",
                {
                    "page": 1,
                    "pageSize": 20,
                    "info": "backup",
                    "groupIDs": [],
                    "orderBy": "createdAt",
                    "order": "descending",
                },
            ),
            executor.calls[0],
        )

    def test_firewall_base_and_search_use_expected_payloads(self) -> None:
        executor = FakeExecutor()

        base = load_firewall_base(executor, name="port")
        search = search_firewall_rules(executor, rule_type="port", info="22")

        self.assertTrue(base["isActive"])
        self.assertEqual("22", search["items"][0]["port"])
        self.assertEqual(("POST", "/api/v2/hosts/firewall/base", {"name": "port"}), executor.calls[0])
        self.assertEqual(
            (
                "POST",
                "/api/v2/hosts/firewall/search",
                {
                    "page": 1,
                    "pageSize": 20,
                    "info": "22",
                    "status": "",
                    "strategy": "",
                    "type": "port",
                },
            ),
            executor.calls[1],
        )

    def test_plan_firewall_operation_uses_official_operate_endpoint(self) -> None:
        plan = plan_firewall_operation(operation="stop", with_docker_restart=False)

        self.assertEqual("/api/v2/hosts/firewall/operate", plan.path)
        self.assertEqual({"operation": "stop", "withDockerRestart": False}, plan.body)


class OnePanelObjectCliHandlerTests(unittest.TestCase):
    def test_panel_verify_redacts_sensitive_settings(self) -> None:
        args = type(
            "Args",
            (),
            {
                "env": "wsl",
                "onepanel_panel_action": "verify",
                "key": "",
            },
        )()

        with patch("agentplane.domain.infra.onepanel._executor_for", return_value=FakeExecutor()):
            payload = handle_panel_action(args)

        self.assertEqual("panel", payload["scope"])
        self.assertEqual("<redacted>", payload["payload"]["summary"]["apiKey"])
        self.assertNotIn("panel-secret-key", json.dumps(payload))

    def test_panel_apply_executes_setting_update(self) -> None:
        executor = FakeExecutor()
        args = type(
            "Args",
            (),
            {
                "env": "wsl",
                "onepanel_panel_action": "apply",
                "key": "bindDomain",
                "value": "panel.example.net",
                "execute": True,
            },
        )()

        with patch("agentplane.domain.infra.onepanel._executor_for", return_value=executor):
            payload = handle_panel_action(args)

        self.assertEqual("panel", payload["scope"])
        self.assertEqual("apply", payload["action"])
        self.assertTrue(payload["payload"]["verified"]["ok"])
        self.assertIn(
            ("POST", "/api/v2/core/settings/update", {"key": "bindDomain", "value": "panel.example.net"}),
            executor.calls,
        )

    def test_firewall_verify_reports_expected_active(self) -> None:
        args = type(
            "Args",
            (),
            {
                "env": "wsl",
                "onepanel_firewall_action": "verify",
                "tab": "port",
                "expected_active": "true",
                "expected_name": "ufw",
            },
        )()

        with patch("agentplane.domain.infra.onepanel._executor_for", return_value=FakeExecutor()):
            payload = handle_firewall_action(args)

        self.assertEqual("firewall", payload["scope"])
        self.assertTrue(payload["payload"]["ok"])

    def test_cronjob_plan_wraps_status_operation(self) -> None:
        args = type(
            "Args",
            (),
            {
                "env": "wsl",
                "onepanel_cronjob_action": "plan",
                "mode": "status",
                "body_json": '{"id": 2, "status": "Disable"}',
                "execute": False,
            },
        )()

        with patch("agentplane.domain.infra.onepanel._executor_for", return_value=FakeExecutor()):
            payload = handle_cronjob_action(args)

        self.assertEqual("cronjob", payload["scope"])
        self.assertEqual("/api/v2/cronjobs/status", payload["payload"]["plan"]["path"])
        self.assertEqual({"id": 2, "status": "Disable"}, payload["payload"]["plan"]["body"])

    def test_task_verify_checks_executing_count(self) -> None:
        args = type(
            "Args",
            (),
            {
                "env": "wsl",
                "onepanel_task_action": "verify",
                "expected_count": 0,
            },
        )()

        with patch("agentplane.domain.infra.onepanel._executor_for", return_value=FakeExecutor()):
            payload = handle_task_action(args)

        self.assertEqual("task", payload["scope"])
        self.assertTrue(payload["payload"]["ok"])

    def test_skeleton_hint_points_only_to_remaining_object_faces(self) -> None:
        payload = onepanel_skeleton("wsl")

        self.assertEqual("onepanel", payload["command"])
        self.assertIn("<panel|firewall|cronjob|task>", payload["hint"])
        self.assertNotIn("ingress", payload["hint"])
        self.assertNotIn("container", payload["hint"])
        self.assertNotIn("app", payload["hint"])
        self.assertNotIn("project", payload["hint"])

    def test_removed_onepanel_subcommands_are_rejected_by_argparse(self) -> None:
        for scope in ("ingress", "container", "app", "project", "ledger", "suite", "fixture", "ingress"):
            with self.subTest(scope=scope):
                result = run_cli("onepanel", "--env", "wsl", scope, "--help")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("invalid choice", result.stderr)


# ======================================================================
# From: test_onepanel_plugin_and_skills.py
# ======================================================================

CATALOG_FILE = REPO_ROOT / ".agents" / "skills" / "catalog.yaml"
REQUIRED_DOMAINS = {"infra", "service", "ingress", "app", "project"}


class OnePanelPluginAndSkillsTests(unittest.TestCase):
    def _tracked_skill_paths(self) -> list[Path]:
        result = subprocess.run(
            ["git", "ls-files", ".agents/skills/*/SKILL.md"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        return sorted(REPO_ROOT / line for line in result.stdout.splitlines() if line)

    def _load_frontmatter(self, path: Path) -> dict:
        text = path.read_text(encoding="utf-8")
        parts = text.split("---", 2)
        self.assertGreaterEqual(len(parts), 3, msg=f"missing frontmatter in {path}")
        payload = yaml.safe_load(parts[1])
        self.assertIsInstance(payload, dict)
        return payload

    def _load_catalog(self) -> dict:
        self.assertTrue(CATALOG_FILE.is_file(), msg=f"missing {CATALOG_FILE}")
        payload = yaml.safe_load(CATALOG_FILE.read_text(encoding="utf-8"))
        self.assertIsInstance(payload, dict)
        self.assertEqual(2, payload.get("version"))
        self.assertIsInstance(payload.get("skills"), list)
        return payload

    def test_catalog_covers_repo_skills_and_required_domains(self) -> None:
        payload = self._load_catalog()
        entries = payload["skills"]
        names = [entry["name"] for entry in entries]
        self.assertEqual(len(names), len(set(names)), msg="catalog skill names must be unique")

        repo_skill_names = sorted(path.parent.name for path in self._tracked_skill_paths())
        self.assertEqual(sorted(names), repo_skill_names)

        covered_domains = {domain for entry in entries for domain in entry["domains"]}
        self.assertEqual(REQUIRED_DOMAINS, covered_domains)

    def test_catalog_tracks_skill_frontmatter_names(self) -> None:
        payload = self._load_catalog()
        entries = {entry["name"]: entry for entry in payload["skills"]}
        for path in self._tracked_skill_paths():
            name = path.parent.name
            with self.subTest(name=name):
                frontmatter = self._load_frontmatter(path)
                self.assertEqual(frontmatter["name"], entries[name]["frontmatter_name"])
                self.assertEqual(path.relative_to(REPO_ROOT).as_posix(), entries[name]["source_path"])

    def test_catalog_has_no_compatibility_skills(self) -> None:
        payload = self._load_catalog()
        compat_entries = [entry["name"] for entry in payload["skills"] if entry["kind"] == "compat"]

        self.assertEqual([], compat_entries)
        self.assertFalse((REPO_ROOT / ".agents" / "skills" / "onepanel-app-lifecycle").exists())
        self.assertFalse((REPO_ROOT / ".agents" / "skills" / "openclaw-1panel").exists())

    def test_active_skills_do_not_route_back_to_openclaw_direct_wrappers(self) -> None:
        cases = (
            REPO_ROOT / ".agents" / "skills" / "site-migration-ops" / "SKILL.md",
            REPO_ROOT / ".agents" / "skills" / "openclaw-ops" / "SKILL.md",
        )
        for path in cases:
            with self.subTest(path=str(path)):
                text = path.read_text(encoding="utf-8")
                self.assertNotIn("API wrappers", text)
                self.assertNotIn("raw signed request", text)
                self.assertNotIn("POST /api/v2/", text)

    def test_ingress_skill_routes_to_formal_ingress_cli(self) -> None:
        repo_skill_text = (REPO_ROOT / ".agents" / "skills" / "agentplane-ingress-ops" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        catalog_text = CATALOG_FILE.read_text(encoding="utf-8")

        self.assertIn("agentplane ingress search --target <target>", repo_skill_text)
        self.assertIn("agentplane ingress get --target <target> --alias <alias>", repo_skill_text)
        self.assertIn(
            "agentplane ingress publish plan --target <target>",
            repo_skill_text,
        )
        self.assertIn("entrypoint: uv run python -m agentplane.cli ingress", catalog_text)

    def test_service_skill_routes_to_formal_service_cli(self) -> None:
        repo_skill_text = (REPO_ROOT / ".agents" / "skills" / "agentplane-service-ops" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        catalog_text = CATALOG_FILE.read_text(encoding="utf-8")

        self.assertIn("agentplane service search --target <target>", repo_skill_text)
        self.assertIn("agentplane service get --target <target> --name <service>", repo_skill_text)
        self.assertIn("agentplane service verify --target <target> --name <service>", repo_skill_text)
        self.assertIn(
            "agentplane service plan --target <target> --name <service> --operation restart",
            repo_skill_text,
        )
        self.assertIn("entrypoint: uv run python -m agentplane.cli service", catalog_text)

    def test_template_surface_skills_use_repo_root_placeholders(self) -> None:
        cases = {
            "agentplane-infra-ops": (
                "--repo-root <repo-root>",
                "infra automation get <target> --name <automation-name>",
            ),
            "app-delivery-ops": (
                "--repo-root <repo-root>",
                "app delivery deploy --target <target> --app <app> --repo-root <repo-root> --dry-run",
            ),
            "agentplane-app-ops": (
                "--repo-root <repo-root>",
                "app resource refresh-ledger --target <target> --repo-root <repo-root> --write",
            ),
            "agentplane-projection-ops": (
                "--repo-root <repo-root>",
                "project projection verification run --target <target> --profile <profile> --repo-root <repo-root>",
            ),
            "agentplane-project-ops": (
                "--repo-root <repo-root>",
                "project docs-sanity --repo-root <repo-root>",
            ),
            "agentplane-service-ops": (
                "--repo-root <repo-root>",
                "service apply --target <target> --name <service> --operation restart --repo-root <repo-root> --execute",
            ),
            "agentplane-ingress-ops": (
                "--repo-root <repo-root>",
                "ingress refresh-ledger --target <target> --repo-root <repo-root> --write",
            ),
        }

        for skill_name, expected_snippets in cases.items():
            text = (REPO_ROOT / ".agents" / "skills" / skill_name / "SKILL.md").read_text(encoding="utf-8")
            with self.subTest(skill=skill_name):
                self.assertNotIn("/root/work/AgentPlane", text)
                self.assertNotIn("ops.cli", text)
                for snippet in expected_snippets:
                    self.assertIn(snippet, text)

    def test_infra_skill_drops_author_site_specific_automation_names(self) -> None:
        text = (REPO_ROOT / ".agents" / "skills" / "agentplane-infra-ops" / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("infra automation search <target> --repo-root <repo-root>", text)
        self.assertIn("infra automation verify <target> --name <automation-name> --repo-root <repo-root>", text)
        self.assertNotIn("wsl-agentplane-secrets-backup", text)
        self.assertNotIn("wsl-zzz-skills-sync", text)

    def test_app_skill_routes_catalog_to_app_and_runtime_to_service(self) -> None:
        repo_skill_text = (REPO_ROOT / ".agents" / "skills" / "agentplane-app-ops" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        catalog_text = CATALOG_FILE.read_text(encoding="utf-8")

        self.assertIn("agentplane app object search --target <target>", repo_skill_text)
        self.assertIn("agentplane app object get --target <target> --app <app>", repo_skill_text)
        self.assertIn("App runtime restart or reconcile is a service task", repo_skill_text)
        self.assertIn(
            "App deploy/build/rollback/doc-sync is a delivery workflow",
            repo_skill_text,
        )
        self.assertNotIn("uv run python -m agentplane.cli onepanel --env <target> app", repo_skill_text)
        self.assertNotIn("uv run python -m agentplane.cli onepanel --env <target> project", repo_skill_text)
        self.assertIn("entrypoint: uv run python -m agentplane.cli", catalog_text)

    def test_tenant_skill_routes_to_formal_app_resource_cli(self) -> None:
        repo_skill_text = (REPO_ROOT / ".agents" / "skills" / "agentplane-app-ops" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        catalog_text = CATALOG_FILE.read_text(encoding="utf-8")

        self.assertIn("agentplane app resource search --target <target>", repo_skill_text)
        self.assertIn("agentplane app resource get --target <target> --app <app>", repo_skill_text)
        self.assertIn("agentplane app resource verify --target <target> --app <app>", repo_skill_text)
        self.assertIn("agentplane app resource refresh-ledger --target <target>", repo_skill_text)
        self.assertIn(
            "Use this domain skill when the user asks about app objects, app catalog state, app resource truth",
            repo_skill_text,
        )
        self.assertNotIn("tenant validate", repo_skill_text)
        self.assertNotIn("tenant audit", repo_skill_text)
        self.assertNotIn("tenant render-env", repo_skill_text)
        self.assertNotIn("tenant audit-live", repo_skill_text)
        self.assertIn("entrypoint: uv run python -m agentplane.cli app", catalog_text)

    def test_projection_skill_routes_to_formal_projection_cli(self) -> None:
        repo_skill_text = (REPO_ROOT / ".agents" / "skills" / "agentplane-projection-ops" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        catalog_text = CATALOG_FILE.read_text(encoding="utf-8")

        self.assertIn("agentplane project projection runtime-env plan --target <target> --app <app>", repo_skill_text)
        self.assertIn("agentplane project projection runtime-env apply --target <target> --app <app>", repo_skill_text)
        self.assertIn("agentplane project projection runtime-env verify --target <target> --app <app>", repo_skill_text)
        self.assertIn("agentplane project projection verification run --target <target> --profile <profile>", repo_skill_text)
        self.assertIn("agentplane project projection fixture plan --target <target> --profile <profile>", repo_skill_text)
        self.assertIn("agentplane project projection ledger refresh --target <target>", repo_skill_text)
        self.assertIn("entrypoint: uv run python -m agentplane.cli project projection", catalog_text)


# ======================================================================
# From: test_onepanel_app_plans.py
# ======================================================================


class OnePanelAppPlanTests(unittest.TestCase):
    def test_build_app_install_params_returns_empty_for_missing_or_non_mapping_params(self) -> None:
        self.assertEqual({}, build_app_install_params("demo", {}))

        for value in ([], "invalid", 42):
            with self.subTest(params=value):
                self.assertEqual({}, build_app_install_params("demo", {"params": value}))

    def test_build_app_install_params_keeps_form_field_defaults(self) -> None:
        detail = {
            "params": {
                "formFields": [
                    {"envKey": "PANEL_DB_HOST", "default": "postgres"},
                    {"envKey": "PANEL_PORT", "default": 8080},
                ]
            }
        }

        self.assertEqual(
            {"PANEL_DB_HOST": "postgres", "PANEL_PORT": 8080},
            build_app_install_params("demo", detail),
        )

    def test_plan_app_install_uses_empty_params_when_detail_params_is_none(self) -> None:
        plan = plan_app_install(
            app_key="openresty",
            app_type="ingress",
            detail={
                "id": 22,
                "params": None,
                "dockerCompose": "services:\n  openresty:\n    image: nginx:alpine\n",
                "hostMode": False,
            },
        )

        self.assertEqual("/api/v2/apps/install", plan.path)
        self.assertEqual("openresty", plan.body["name"])
        self.assertEqual(
            {
                "WEBSITE_DIR": "/data/1panel/www",
                "PANEL_APP_PORT_HTTP": 80,
                "PANEL_APP_PORT_HTTPS": 443,
            },
            plan.body["params"],
        )
        self.assertIn("services:", plan.body["dockerCompose"])

    def test_start_and_stop_plans_use_installed_app_operation_endpoint(self) -> None:
        for operate in ("start", "stop"):
            with self.subTest(operate=operate):
                plan = plan_installed_app_operation(install_id=3, operate=operate)

                self.assertEqual("/api/v2/apps/installed/op", plan.path)
                self.assertEqual(
                    {"installId": 3, "operate": operate}, {k: plan.body[k] for k in ("installId", "operate")}
                )
                self.assertFalse(plan.body["deleteDB"])
                self.assertFalse(plan.body["pullImage"])
