from __future__ import annotations
from pathlib import Path
from unittest.mock import patch
import json
import subprocess
import sys
import unittest
import yaml
import pytest
from agentplane.cli.infra_onepanel import (
    _handle_cronjob_action,
    _handle_firewall_action,
    _handle_panel_action,
    _handle_task_action,
    onepanel_skeleton,
)
from agentplane.scripts.onepanel.object_api import (
    FakeLikeExecutorProtocol,
    get_panel_summary,
    load_firewall_base,
    plan_firewall_operation,
    search_cronjobs,
    search_firewall_rules,
)
from agentplane.scripts.onepanel.object_api import (
    build_app_install_params,
    plan_app_install,
    plan_installed_app_operation,
)

pytestmark = pytest.mark.e2e

REPO_ROOT = Path(__file__).resolve().parents[2]

def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "agentplane.cli", *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

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

        with patch("agentplane.cli.infra_onepanel._executor_for", return_value=FakeExecutor()):
            payload = _handle_panel_action(args)

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
                "value": "panel.zzzai.cloud",
                "execute": True,
            },
        )()

        with patch("agentplane.cli.infra_onepanel._executor_for", return_value=executor):
            payload = _handle_panel_action(args)

        self.assertEqual("panel", payload["scope"])
        self.assertEqual("apply", payload["action"])
        self.assertTrue(payload["payload"]["verified"]["ok"])
        self.assertIn(
            ("POST", "/api/v2/core/settings/update", {"key": "bindDomain", "value": "panel.zzzai.cloud"}),
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

        with patch("agentplane.cli.infra_onepanel._executor_for", return_value=FakeExecutor()):
            payload = _handle_firewall_action(args)

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

        with patch("agentplane.cli.infra_onepanel._executor_for", return_value=FakeExecutor()):
            payload = _handle_cronjob_action(args)

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

        with patch("agentplane.cli.infra_onepanel._executor_for", return_value=FakeExecutor()):
            payload = _handle_task_action(args)

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

REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG_FILE = REPO_ROOT / ".agents" / "skills" / "catalog.yaml"
REQUIRED_DOMAINS = {"infra", "service", "ingress", "app-resource", "app", "projection"}

class OnePanelPluginAndSkillsTests(unittest.TestCase):
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
        self.assertEqual(1, payload.get("version"))
        self.assertIsInstance(payload.get("skills"), list)
        return payload

    def test_catalog_covers_repo_skills_and_required_domains(self) -> None:
        payload = self._load_catalog()
        entries = payload["skills"]
        names = [entry["name"] for entry in entries]
        self.assertEqual(len(names), len(set(names)), msg="catalog skill names must be unique")

        repo_skill_names = sorted(path.parent.name for path in (REPO_ROOT / ".agents" / "skills").glob("*/SKILL.md"))
        self.assertEqual(sorted(names), repo_skill_names)

        covered_domains = {domain for entry in entries for domain in entry["domains"]}
        self.assertEqual(REQUIRED_DOMAINS, covered_domains)

    def test_catalog_tracks_skill_frontmatter_names(self) -> None:
        payload = self._load_catalog()
        entries = {entry["name"]: entry for entry in payload["skills"]}
        for path in sorted((REPO_ROOT / ".agents" / "skills").glob("*/SKILL.md")):
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
            REPO_ROOT / ".agents" / "skills" / "onepanel-openresty-site-migration" / "SKILL.md",
        )
        for path in cases:
            with self.subTest(path=str(path)):
                text = path.read_text(encoding="utf-8")
                self.assertNotIn("API wrappers", text)
                self.assertNotIn("raw signed request", text)
                self.assertNotIn("POST /api/v2/", text)

    def test_ingress_skill_routes_to_formal_ingress_cli(self) -> None:
        repo_skill_text = (REPO_ROOT / ".agents" / "skills" / "onepanel-website-ops" / "SKILL.md").read_text(encoding="utf-8")
        catalog_text = CATALOG_FILE.read_text(encoding="utf-8")

        self.assertIn("uv run python -m agentplane.cli ingress search --target <target>", repo_skill_text)
        self.assertIn("uv run python -m agentplane.cli ingress get --target <target> --alias <alias>", repo_skill_text)
        self.assertIn(
            "uv run python -m agentplane.cli ingress publish plan --target <target> --config-file <config-file> --cloudflare-env-file <cloudflare-env-file> --repo-root <repo-root>",
            repo_skill_text,
        )
        self.assertIn("entrypoint: uv run python -m agentplane.cli ingress", catalog_text)

    def test_service_skill_routes_to_formal_service_cli(self) -> None:
        repo_skill_text = (REPO_ROOT / ".agents" / "skills" / "onepanel-container-ops" / "SKILL.md").read_text(encoding="utf-8")
        catalog_text = CATALOG_FILE.read_text(encoding="utf-8")

        self.assertIn("uv run python -m agentplane.cli service search --target <target>", repo_skill_text)
        self.assertIn("uv run python -m agentplane.cli service get --target <target> --name <service>", repo_skill_text)
        self.assertIn("uv run python -m agentplane.cli service verify --target <target> --name <service>", repo_skill_text)
        self.assertIn(
            "uv run python -m agentplane.cli service plan --target <target> --name <service> --operation restart",
            repo_skill_text,
        )
        self.assertIn("entrypoint: uv run python -m agentplane.cli service", catalog_text)

    def test_template_surface_skills_use_repo_root_placeholders(self) -> None:
        cases = {
            "host-ops": (
                "--repo-root <repo-root>",
                "infra automation get <target> --name <automation-name>",
            ),
            "app-delivery-ops": (
                "--repo-root <repo-root>",
                "app delivery deploy --target <target> --app <app> --repo-root <repo-root> --dry-run",
            ),
            "app-resource-ops": (
                "--repo-root <repo-root>",
                "app resource refresh-ledger --target <target> --repo-root <repo-root> --write",
            ),
            "inventory-ledger-ops": (
                "--repo-root <repo-root>",
                "app delivery doc-sync --target <target> --app <app> --repo-root <repo-root> --write",
            ),
            "projection-ops": (
                "--repo-root <repo-root>",
                "projection verification run --target <target> --profile <profile> --repo-root <repo-root>",
            ),
            "onepanel-app-ops": (
                "--repo-root <repo-root>",
                "app delivery validate-contract --target <target> --app <app> --repo-root <repo-root>",
            ),
            "onepanel-container-ops": (
                "--repo-root <repo-root>",
                "service apply --target <target> --name <service> --operation restart --execute --repo-root <repo-root>",
            ),
            "onepanel-firewall-ops": (
                "--repo-root <repo-root>",
                "projection ledger refresh --target <target> --repo-root <repo-root> --write --json",
            ),
            "onepanel-website-ops": (
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
        text = (REPO_ROOT / ".agents" / "skills" / "host-ops" / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("infra automation search <target> --repo-root <repo-root>", text)
        self.assertIn("infra automation verify <target> --name <automation-name> --repo-root <repo-root>", text)
        self.assertNotIn("wsl-agentplane-secrets-backup", text)
        self.assertNotIn("wsl-zzz-skills-sync", text)

    def test_app_skill_routes_catalog_to_app_and_runtime_to_service(self) -> None:
        repo_skill_text = (REPO_ROOT / ".agents" / "skills" / "onepanel-app-ops" / "SKILL.md").read_text(encoding="utf-8")
        catalog_text = CATALOG_FILE.read_text(encoding="utf-8")

        self.assertIn("uv run python -m agentplane.cli app object search --target <target>", repo_skill_text)
        self.assertIn("uv run python -m agentplane.cli app object get --target <target> --app <app>", repo_skill_text)
        self.assertIn("uv run python -m agentplane.cli service get --target <target> --name <service>", repo_skill_text)
        self.assertIn(
            "uv run python -m agentplane.cli app delivery validate-contract --target <target> --app <app>",
            repo_skill_text,
        )
        self.assertNotIn("uv run python -m agentplane.cli onepanel --env <target> app", repo_skill_text)
        self.assertNotIn("uv run python -m agentplane.cli onepanel --env <target> project", repo_skill_text)
        self.assertIn("entrypoint: uv run python -m agentplane.cli", catalog_text)

    def test_tenant_skill_routes_to_formal_app_resource_cli(self) -> None:
        repo_skill_text = (REPO_ROOT / ".agents" / "skills" / "app-resource-ops" / "SKILL.md").read_text(encoding="utf-8")
        catalog_text = CATALOG_FILE.read_text(encoding="utf-8")

        self.assertIn("uv run python -m agentplane.cli app resource search --target <target>", repo_skill_text)
        self.assertIn("uv run python -m agentplane.cli app resource get --target <target> --app <app>", repo_skill_text)
        self.assertIn("uv run python -m agentplane.cli app resource verify --target <target> --app <app>", repo_skill_text)
        self.assertIn("uv run python -m agentplane.cli app resource refresh-ledger --target <target>", repo_skill_text)
        self.assertIn(
            "canonical entry is `uv run python -m agentplane.cli app resource ...`",
            repo_skill_text,
        )
        self.assertNotIn("tenant validate", repo_skill_text)
        self.assertNotIn("tenant audit", repo_skill_text)
        self.assertNotIn("tenant render-env", repo_skill_text)
        self.assertNotIn("tenant audit-live", repo_skill_text)
        self.assertIn("entrypoint: uv run python -m agentplane.cli app resource", catalog_text)

    def test_projection_skill_routes_to_formal_projection_cli(self) -> None:
        repo_skill_text = (REPO_ROOT / ".agents" / "skills" / "projection-ops" / "SKILL.md").read_text(encoding="utf-8")
        catalog_text = CATALOG_FILE.read_text(encoding="utf-8")

        self.assertIn("uv run python -m agentplane.cli projection runtime-env plan --target <target> --app <app>", repo_skill_text)
        self.assertIn("uv run python -m agentplane.cli projection runtime-env apply --target <target> --app <app>", repo_skill_text)
        self.assertIn("uv run python -m agentplane.cli projection runtime-env verify --target <target> --app <app>", repo_skill_text)
        self.assertIn("uv run python -m agentplane.cli projection verification run --target <target> --profile <profile>", repo_skill_text)
        self.assertIn("uv run python -m agentplane.cli projection fixture plan --target <target> --profile wsl-fixture", repo_skill_text)
        self.assertIn("uv run python -m agentplane.cli projection ledger refresh --target <target>", repo_skill_text)
        self.assertIn("entrypoint: uv run python -m agentplane.cli projection", catalog_text)

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
                self.assertEqual({"installId": 3, "operate": operate}, {k: plan.body[k] for k in ("installId", "operate")})
                self.assertFalse(plan.body["deleteDB"])
                self.assertFalse(plan.body["pullImage"])
