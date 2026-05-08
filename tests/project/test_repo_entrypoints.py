from __future__ import annotations

import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

import pytest
from tests.support.cli import run_agentplane_cli as run_cli
from tests.support.paths import REPO_ROOT

pytestmark = pytest.mark.e2e


def _listed_help_commands(help_text: str) -> set[str]:
    return set(re.findall(r"(?m)^\s{2,}([a-z][a-z0-9-]*)\b(?:\s{2,}|\s*$)", help_text))


def _listed_targets(help_text: str) -> set[str]:
    targets: set[str] = set()
    for choice_group in re.findall(r"\{([^}]+)\}", help_text):
        for token in choice_group.split(","):
            candidate = token.strip()
            if candidate in {"wsl", "prod0-main", "prod0-main"}:
                targets.add(candidate)
    return targets


def _assert_help_commands(
    testcase: unittest.TestCase,
    help_text: str,
    *,
    expected: set[str] | None = None,
    absent: set[str] | None = None,
) -> set[str]:
    commands = _listed_help_commands(help_text)
    if expected is not None:
        testcase.assertTrue(expected.issubset(commands), msg=f"missing commands: {sorted(expected - commands)}")
    if absent is not None:
        testcase.assertTrue(absent.isdisjoint(commands), msg=f"unexpected commands: {sorted(absent & commands)}")
    return commands


def _write_fake_onepanel_router(source_root: Path, *, include_extra_route: bool = False) -> None:
    router_root = source_root / "agent" / "router"
    router_root.mkdir(parents=True, exist_ok=True)
    extra_route = '\n\t\tbaRouter.POST("/inspect", baseApi.Inspect)' if include_extra_route else ""
    (router_root / "ro_container.go").write_text(
        f"""package router

func (s *ContainerRouter) InitRouter(Router *gin.RouterGroup) {{
\tbaRouter := Router.Group("containers")
\tbaseApi := v2.ApiGroupApp.BaseApi
\t{{
\t\tbaRouter.POST("/search", baseApi.SearchContainer)
\t\tbaRouter.GET("/status", baseApi.LoadContainerStatus){extra_route}
\t}}
}}
""",
        encoding="utf-8",
    )
    (router_root / "ro_website.go").write_text(
        """package router

func (a *WebsiteRouter) InitRouter(Router *gin.RouterGroup) {
\twebsiteRouter := Router.Group("websites")
\tbaseApi := v2.ApiGroupApp.BaseApi
\t{
\t\twebsiteRouter.POST("", baseApi.CreateWebsite)
\t\twebsiteRouter.GET("/:id", baseApi.GetWebsite)
\t}
}
""",
        encoding="utf-8",
    )


class CliEntrypointsTests(unittest.TestCase):
    def test_module_help_lists_required_subcommands_with_app_resource(self) -> None:
        result = run_cli("--help")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        _assert_help_commands(
            self,
            result.stdout,
            expected={"infra", "ingress", "service", "app", "project"},
            absent={"network", "tenant", "automation", "cleanup", "inventory", "audit", "remote", "secrets"},
        )

        projection_help = run_cli("project", "projection", "--help")
        self.assertEqual(projection_help.returncode, 0, msg=projection_help.stderr)
        _assert_help_commands(
            self,
            projection_help.stdout,
            expected={"runtime-env", "verification", "fixture", "ledger"},
        )

        projection_runtime_env_help = run_cli("project", "projection", "runtime-env", "--help")
        self.assertEqual(projection_runtime_env_help.returncode, 0, msg=projection_runtime_env_help.stderr)
        _assert_help_commands(
            self,
            projection_runtime_env_help.stdout,
            expected={"plan", "apply", "verify"},
        )

        projection_verification_help = run_cli("project", "projection", "verification", "--help")
        self.assertEqual(projection_verification_help.returncode, 0, msg=projection_verification_help.stderr)
        _assert_help_commands(self, projection_verification_help.stdout, expected={"run"})

        projection_fixture_help = run_cli("project", "projection", "fixture", "--help")
        self.assertEqual(projection_fixture_help.returncode, 0, msg=projection_fixture_help.stderr)
        _assert_help_commands(
            self,
            projection_fixture_help.stdout,
            expected={"plan", "apply", "cleanup"},
        )

        projection_ledger_help = run_cli("project", "projection", "ledger", "--help")
        self.assertEqual(projection_ledger_help.returncode, 0, msg=projection_ledger_help.stderr)
        _assert_help_commands(self, projection_ledger_help.stdout, expected={"refresh"})

        service_help = run_cli("service", "--help")
        self.assertEqual(service_help.returncode, 0, msg=service_help.stderr)
        _assert_help_commands(
            self,
            service_help.stdout,
            expected={"search", "get", "verify", "plan", "apply"},
        )

        website_help = run_cli("ingress", "--help")
        self.assertEqual(website_help.returncode, 0, msg=website_help.stderr)
        _assert_help_commands(
            self,
            website_help.stdout,
            expected={"search", "get", "verify", "plan", "apply", "refresh-ledger", "publish"},
        )

        website_publish_help = run_cli("ingress", "publish", "--help")
        self.assertEqual(website_publish_help.returncode, 0, msg=website_publish_help.stderr)
        _assert_help_commands(
            self,
            website_publish_help.stdout,
            expected={"plan", "apply", "verify"},
        )

        app_help = run_cli("app", "--help")
        self.assertEqual(app_help.returncode, 0, msg=app_help.stderr)
        _assert_help_commands(self, app_help.stdout, expected={"object", "resource", "delivery"})

        app_object_help = run_cli("app", "object", "--help")
        self.assertEqual(app_object_help.returncode, 0, msg=app_object_help.stderr)
        _assert_help_commands(
            self,
            app_object_help.stdout,
            expected={"search", "get", "verify", "refresh-ledger"},
        )

        app_resource_help = run_cli("app", "resource", "--help")
        self.assertEqual(app_resource_help.returncode, 0, msg=app_resource_help.stderr)
        _assert_help_commands(
            self,
            app_resource_help.stdout,
            expected={"search", "get", "verify", "refresh-ledger"},
        )

        app_delivery_help = run_cli("app", "delivery", "--help")
        self.assertEqual(app_delivery_help.returncode, 0, msg=app_delivery_help.stderr)
        _assert_help_commands(
            self,
            app_delivery_help.stdout,
            expected={
                "validate-contract",
                "onboard",
                "offboard",
                "build-artifact",
                "ship-image",
                "render-runtime",
                "deploy",
                "rollback",
                "verify",
                "inventory-refresh",
                "doc-sync",
            },
        )

        host_help = run_cli("infra", "--help")
        self.assertEqual(host_help.returncode, 0, msg=host_help.stderr)
        _assert_help_commands(
            self,
            host_help.stdout,
            expected={
                "inventory",
                "audit",
                "live-gate",
                "cleanup",
                "automation",
                "network",
                "remote",
                "secrets",
                "local",
            },
            absent={"secrets-layout"},
        )

        host_live_gate_help = run_cli("infra", "live-gate", "--help")
        self.assertEqual(host_live_gate_help.returncode, 0, msg=host_live_gate_help.stderr)
        _assert_help_commands(self, host_live_gate_help.stdout, expected={"plan", "run"})

        host_cleanup_help = run_cli("infra", "cleanup", "--help")
        self.assertEqual(host_cleanup_help.returncode, 0, msg=host_cleanup_help.stderr)
        _assert_help_commands(self, host_cleanup_help.stdout, expected={"plan", "apply"})

        host_automation_help = run_cli("infra", "automation", "--help")
        self.assertEqual(host_automation_help.returncode, 0, msg=host_automation_help.stderr)
        _assert_help_commands(
            self,
            host_automation_help.stdout,
            expected={"search", "get", "verify", "plan", "apply"},
        )

        host_secrets_help = run_cli("infra", "secrets", "--help")
        self.assertEqual(host_secrets_help.returncode, 0, msg=host_secrets_help.stderr)
        _assert_help_commands(
            self,
            host_secrets_help.stdout,
            expected={"init-data-services", "sync-layout"},
        )

        host_network_help = run_cli("infra", "network", "--help")
        self.assertEqual(host_network_help.returncode, 0, msg=host_network_help.stderr)
        _assert_help_commands(self, host_network_help.stdout, expected={"audit", "ensure"})

        repo_help = run_cli("project", "--help")
        self.assertEqual(repo_help.returncode, 0, msg=repo_help.stderr)
        _assert_help_commands(
            self,
            repo_help.stdout,
            expected={
                "health-check",
                "status",
                "docs-sanity",
                "secret-scan",
                "privacy-scan",
                "release-check",
                "provider",
                "skills",
            },
        )

        repo_skills_help = run_cli("project", "skills", "--help")
        self.assertEqual(repo_skills_help.returncode, 0, msg=repo_skills_help.stderr)
        _assert_help_commands(
            self,
            repo_skills_help.stdout,
            expected={"check", "list", "export", "sync"},
        )

    def test_app_help_hides_legacy_flat_entrypoints(self) -> None:
        app_help = run_cli("app", "--help")

        self.assertEqual(app_help.returncode, 0, msg=app_help.stderr)
        _assert_help_commands(
            self,
            app_help.stdout,
            absent={
                "validate-contract",
                "render-runtime",
                "inventory-refresh",
                "doc-sync",
                "build-artifact",
                "ship-image",
                "deploy",
                "verify",
                "rollback",
                "onboard",
                "offboard",
            },
        )

    def test_required_subcommands_emit_json(self) -> None:
        cases = [
            ("infra", "local", "inspect", "--repo-root", "C:/repos/agentplane"),
            ("infra", "inventory", "wsl", "--repo-root", str(REPO_ROOT)),
            ("infra", "inventory", "prod0-main", "--repo-root", str(REPO_ROOT)),
            ("infra", "audit", "wsl", "--repo-root", str(REPO_ROOT)),
            ("infra", "audit", "prod0-main", "--repo-root", str(REPO_ROOT)),
            ("infra", "live-gate", "plan", "--profile", "wsl", "--repo-root", str(REPO_ROOT)),
            ("infra", "cleanup", "plan", "wsl", "--repo-root", str(REPO_ROOT)),
            ("infra", "automation", "search", "wsl", "--repo-root", str(REPO_ROOT)),
            ("project", "secret-scan", "--repo-root", str(REPO_ROOT)),
            ("project", "privacy-scan", "--repo-root", str(REPO_ROOT)),
            ("project", "docs-sanity", "--repo-root", str(REPO_ROOT)),
            ("project", "status", "--repo-root", str(REPO_ROOT)),
            ("project", "skills", "check", "--repo-root", str(REPO_ROOT)),
            ("project", "skills", "list", "--repo-root", str(REPO_ROOT)),
            ("project", "skills", "sync", "--repo-root", str(REPO_ROOT)),
        ]
        for args in cases:
            with self.subTest(args=args):
                result = run_cli(*args)
                payload = json.loads(result.stdout)
                self.assertIsInstance(payload, dict)
                self.assertIn("command", payload)

    def test_repo_status_summarizes_control_plane_state(self) -> None:
        result = run_cli("project", "status", "--repo-root", str(REPO_ROOT))

        payload = json.loads(result.stdout)
        self.assertEqual("repo", payload["command"])
        self.assertEqual("status", payload["action"])
        self.assertIn("summary", payload)
        self.assertIn("checks", payload)
        self.assertIn("skills", payload["checks"])
        self.assertIn("apps", payload)
        self.assertIn("targets", payload)
        self.assertGreaterEqual(payload["summary"]["public_skills"], 1)
        self.assertIsNone(payload["dashboard"]["html"])

    def test_repo_status_writes_static_html_dashboard(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agentplane-status-") as tmp:
            output = Path(tmp) / "status.html"
            result = run_cli("project", "status", "--repo-root", str(REPO_ROOT), "--html", str(output))
            html_text = output.read_text(encoding="utf-8")

        payload = json.loads(result.stdout)
        self.assertEqual(str(output), payload["dashboard"]["html"])
        self.assertIn("<!doctype html>", html_text)
        self.assertIn("AgentPlane Status", html_text)
        self.assertIn("Public Skills", html_text)
        self.assertIn("Targets", html_text)

    def test_repo_provider_onepanel_route_fingerprint_reports_routes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agentplane-onepanel-source-") as tmp:
            source_root = Path(tmp) / "1Panel"
            output = Path(tmp) / "fingerprint.json"
            _write_fake_onepanel_router(source_root)

            result = run_cli(
                "project",
                "provider",
                "onepanel",
                "route-fingerprint",
                "--source-root",
                str(source_root),
                "--output",
                str(output),
                "--repo-root",
                str(REPO_ROOT),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            written = json.loads(output.read_text(encoding="utf-8"))

        self.assertTrue(payload["ok"])
        self.assertEqual("provider.onepanel.route-fingerprint", payload["action"])
        self.assertEqual("onepanel", payload["payload"]["provider"])
        self.assertEqual(4, payload["payload"]["route_count"])
        self.assertEqual(payload["payload"]["fingerprint"], written["fingerprint"])
        routes = {(item["method"], item["path"], item["handler"]) for item in payload["payload"]["routes"]}
        self.assertIn(("POST", "/containers/search", "baseApi.SearchContainer"), routes)
        self.assertIn(("POST", "/websites", "baseApi.CreateWebsite"), routes)
        self.assertIn(("GET", "/websites/:id", "baseApi.GetWebsite"), routes)
        surface_counts = {item["surface"]: item["routes"] for item in payload["payload"]["impact_summary"]["surfaces"]}
        self.assertEqual(2, surface_counts["ingress"])
        self.assertEqual(2, surface_counts["service"])
        self.assertEqual(2, surface_counts["app.delivery"])
        container_route = next(item for item in payload["payload"]["routes"] if item["path"] == "/containers/search")
        self.assertEqual("P0", container_route["impact"]["priority"])
        self.assertEqual(["app.delivery", "service"], container_route["impact"]["surfaces"])

    def test_repo_provider_onepanel_route_fingerprint_can_fail_on_drift(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agentplane-onepanel-drift-") as tmp:
            source_root = Path(tmp) / "1Panel"
            baseline = Path(tmp) / "baseline.json"
            _write_fake_onepanel_router(source_root)

            baseline_result = run_cli(
                "project",
                "provider",
                "onepanel",
                "route-fingerprint",
                "--source-root",
                str(source_root),
                "--output",
                str(baseline),
                "--repo-root",
                str(REPO_ROOT),
            )
            self.assertEqual(baseline_result.returncode, 0, msg=baseline_result.stderr)

            _write_fake_onepanel_router(source_root, include_extra_route=True)
            drift_result = run_cli(
                "project",
                "provider",
                "onepanel",
                "route-fingerprint",
                "--source-root",
                str(source_root),
                "--baseline",
                str(baseline),
                "--fail-on-drift",
                "--repo-root",
                str(REPO_ROOT),
            )

        self.assertEqual(drift_result.returncode, 1, msg=drift_result.stderr)
        payload = json.loads(drift_result.stdout)
        self.assertFalse(payload["ok"])
        self.assertTrue(payload["drift"]["changed"])
        self.assertEqual(1, payload["drift"]["counts"]["added"])
        self.assertEqual("/containers/inspect", payload["drift"]["added"][0]["path"])
        self.assertEqual("P0", payload["drift"]["impact"]["highest_priority"])
        drift_surfaces = {item["surface"]: item["routes"] for item in payload["drift"]["impact"]["surfaces"]}
        self.assertEqual(1, drift_surfaces["service"])
        self.assertEqual(1, drift_surfaces["app.delivery"])

    def test_repo_health_check_can_include_onepanel_provider_gate(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agentplane-onepanel-health-") as tmp:
            source_root = Path(tmp) / "1Panel"
            _write_fake_onepanel_router(source_root)

            result = run_cli(
                "project",
                "health-check",
                "--repo-root",
                str(REPO_ROOT),
                "--skip-ruff",
                "--skip-tests",
                "--skip-secrets",
                "--skip-cli-help",
                "--skip-docs",
                "--onepanel-source-root",
                str(source_root),
            )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        checks = {item["name"]: item for item in payload["checks"]}
        self.assertTrue(checks["onepanel-route-fingerprint"]["ok"])
        self.assertEqual(4, checks["onepanel-route-fingerprint"]["route_count"])
        self.assertEqual("P0", checks["onepanel-route-fingerprint"]["impact_summary"]["highest_priority"])
        self.assertIn("skills-check", checks)

    def test_repo_health_check_can_fail_on_onepanel_drift(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agentplane-onepanel-health-drift-") as tmp:
            source_root = Path(tmp) / "1Panel"
            baseline = Path(tmp) / "baseline.json"
            _write_fake_onepanel_router(source_root)
            baseline_result = run_cli(
                "project",
                "provider",
                "onepanel",
                "route-fingerprint",
                "--source-root",
                str(source_root),
                "--output",
                str(baseline),
                "--repo-root",
                str(REPO_ROOT),
            )
            self.assertEqual(baseline_result.returncode, 0, msg=baseline_result.stderr)

            _write_fake_onepanel_router(source_root, include_extra_route=True)
            result = run_cli(
                "project",
                "health-check",
                "--repo-root",
                str(REPO_ROOT),
                "--skip-ruff",
                "--skip-tests",
                "--skip-secrets",
                "--skip-cli-help",
                "--skip-docs",
                "--onepanel-source-root",
                str(source_root),
                "--onepanel-baseline",
                str(baseline),
                "--fail-on-onepanel-drift",
            )

        self.assertEqual(result.returncode, 1, msg=result.stderr)
        payload = json.loads(result.stdout)
        checks = {item["name"]: item for item in payload["checks"]}
        provider_check = checks["onepanel-route-fingerprint"]
        self.assertFalse(provider_check["ok"])
        self.assertTrue(provider_check["drift"]["changed"])
        self.assertEqual(1, provider_check["drift"]["counts"]["added"])

    def test_repo_skills_check_validates_public_skill_surface(self) -> None:
        result = run_cli("project", "skills", "check", "--repo-root", str(REPO_ROOT))

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual("skills.check", payload["action"])
        self.assertEqual([], payload["issues"])

    def test_repo_skills_list_and_export_report_catalog_entries(self) -> None:
        list_result = run_cli("project", "skills", "list", "--repo-root", str(REPO_ROOT))
        self.assertEqual(list_result.returncode, 0, msg=list_result.stderr)
        list_payload = json.loads(list_result.stdout)
        names = {skill["name"] for skill in list_payload["skills"]}

        self.assertIn("agentplane-infra-ops", names)
        self.assertIn("app-delivery-ops", names)
        self.assertTrue(all(skill["exists"] for skill in list_payload["skills"]))

        with tempfile.TemporaryDirectory(prefix="agentplane-skills-export-") as tmp:
            output = Path(tmp) / "skills.json"
            export_result = run_cli(
                "project",
                "skills",
                "export",
                "--repo-root",
                str(REPO_ROOT),
                "--output",
                str(output),
            )
            self.assertEqual(export_result.returncode, 0, msg=export_result.stderr)
            export_payload = json.loads(export_result.stdout)
            written = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual("skills.export", export_payload["action"])
        self.assertEqual(2, export_payload["payload"]["version"])
        self.assertEqual(export_payload["payload"], written)

    def test_repo_skills_sync_is_dry_run_report(self) -> None:
        result = run_cli("project", "skills", "sync", "--repo-root", str(REPO_ROOT))

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual("skills.sync", payload["action"])
        self.assertTrue(payload["ok"])
        self.assertFalse(payload["would_write"])
        self.assertEqual([], payload["catalog_only"])
        self.assertEqual([], payload["tracked_only"])

    def test_infra_cleanup_apply_emits_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".playwright-cli").mkdir(parents=True)
            result = run_cli("infra", "cleanup", "apply", "wsl", "--repo-root", str(root), cwd=REPO_ROOT)
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("infra", payload.get("command"))
            self.assertEqual("cleanup.apply", payload.get("action"))
            self.assertEqual("wsl", payload.get("target"))
            self.assertIn("removed", payload["payload"])

    def test_infra_automation_search_emits_json(self) -> None:
        result = run_cli("infra", "automation", "search", "wsl", "--repo-root", str(REPO_ROOT), cwd=REPO_ROOT)

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual("infra", payload.get("command"))
        self.assertEqual("automation.search", payload.get("action"))
        self.assertEqual("wsl", payload.get("target"))
        self.assertIn("items", payload["payload"])

    def test_infra_automation_help_lists_formal_targets(self) -> None:
        result = run_cli("infra", "automation", "search", "--help")

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertTrue({"wsl", "prod0-main", "prod0-main"}.issubset(_listed_targets(result.stdout)))

    def test_top_level_automation_entry_is_removed(self) -> None:
        result = run_cli("automation", "--help")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid choice", result.stderr)

    def test_infra_live_gate_run_without_execute_is_plan_only(self) -> None:
        result = run_cli(
            "infra",
            "live-gate",
            "run",
            "--profile",
            "wsl",
            "--repo-root",
            str(REPO_ROOT),
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["payload"]["executed"])
        self.assertEqual("single-checkout", payload["payload"]["required_checkout"])


