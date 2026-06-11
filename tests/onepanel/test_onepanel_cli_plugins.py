from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

import pytest
import yaml
from agentplane.scripts.onepanel.object_api import (
    build_app_install_params,
    plan_app_install,
    plan_installed_app_operation,
)
from tests.support.paths import REPO_ROOT

CATALOG_FILE = REPO_ROOT / ".agents" / "skills" / "catalog.yaml"
REQUIRED_DOMAINS = {"infra", "service", "ingress", "app", "project"}

pytestmark = pytest.mark.integration


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
