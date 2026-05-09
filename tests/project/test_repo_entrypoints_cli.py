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

