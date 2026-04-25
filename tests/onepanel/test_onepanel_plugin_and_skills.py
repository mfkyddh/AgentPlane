from __future__ import annotations

import unittest
from pathlib import Path

import yaml

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
            with self.subTest(path=path):
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


if __name__ == "__main__":
    unittest.main()
