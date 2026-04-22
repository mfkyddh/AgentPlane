from __future__ import annotations

import unittest
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG_FILE = REPO_ROOT / ".codex" / "skills" / "catalog.yaml"
REQUIRED_DOMAINS = {"host", "service", "website", "app-resource", "app", "projection"}
REQUIRED_PLUGIN_GROUPS = {"websites", "containers", "firewall", "cronjobs", "apps", "ledgers", "hosts"}
COMPAT_SKILLS = {"onepanel-app-lifecycle", "openclaw-1panel"}


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
        self.assertIsInstance(payload.get("plugin_groups"), dict)
        return payload

    def test_catalog_covers_repo_skills_and_required_domains(self) -> None:
        payload = self._load_catalog()
        entries = payload["skills"]
        names = [entry["name"] for entry in entries]
        self.assertEqual(len(names), len(set(names)), msg="catalog skill names must be unique")

        repo_skill_names = sorted(path.parent.name for path in (REPO_ROOT / ".codex" / "skills").glob("*/SKILL.md"))
        self.assertEqual(sorted(names), repo_skill_names)

        covered_domains = {domain for entry in entries for domain in entry["domains"]}
        self.assertEqual(REQUIRED_DOMAINS, covered_domains)

    def test_catalog_tracks_skill_frontmatter_names(self) -> None:
        payload = self._load_catalog()
        entries = {entry["name"]: entry for entry in payload["skills"]}
        for path in sorted((REPO_ROOT / ".codex" / "skills").glob("*/SKILL.md")):
            name = path.parent.name
            with self.subTest(name=name):
                frontmatter = self._load_frontmatter(path)
                self.assertEqual(frontmatter["name"], entries[name]["frontmatter_name"])
                self.assertEqual(path.relative_to(REPO_ROOT).as_posix(), entries[name]["source_path"])

    def test_agents_pointer_layer_matches_catalog(self) -> None:
        payload = self._load_catalog()
        pointer_entries = {
            entry["name"]: entry
            for entry in payload["skills"]
            if "agents_pointer" in entry.get("projection_targets", [])
        }
        pointer_root = REPO_ROOT / ".agents" / "skills"
        actual_pointers = {}
        for path in sorted(pointer_root.iterdir()):
            if path.name == "README.md" or path.is_dir():
                continue
            actual_pointers[path.name] = path.read_text(encoding="utf-8").strip()

        self.assertEqual(set(pointer_entries), set(actual_pointers))
        for name, entry in pointer_entries.items():
            with self.subTest(name=name):
                self.assertEqual(f"../../.codex/skills/{name}", actual_pointers[name])
                self.assertEqual(f".codex/skills/{name}/SKILL.md", entry["source_path"])

    def test_plugin_groups_follow_catalog_projection(self) -> None:
        payload = self._load_catalog()
        entries = {entry["name"]: entry for entry in payload["skills"]}
        plugin_groups = payload["plugin_groups"]
        self.assertEqual(REQUIRED_PLUGIN_GROUPS, set(plugin_groups))
        plugin_root = REPO_ROOT / "plugins" / "agentplane-control-plane" / "skills"
        actual_groups = {path.name for path in plugin_root.iterdir() if path.is_dir()}
        self.assertEqual(set(plugin_groups), actual_groups)

        grouped_skills: set[str] = set()
        for group_name, group in plugin_groups.items():
            with self.subTest(group=group_name):
                self.assertEqual({"SKILL.md"}, {path.name for path in (plugin_root / group_name).iterdir()})
                skill_file = plugin_root / group_name / "SKILL.md"
                self.assertTrue(skill_file.is_file(), msg=f"missing {skill_file}")
                text = skill_file.read_text(encoding="utf-8")
                self.assertIn("Generated from `.codex/skills/catalog.yaml`.", text)
                self.assertIn("uv run python -m agentplane.cli", text)
                self.assertNotIn("uv run python -m ops.cli", text)
                self.assertNotIn("op-linux-control-plane", text)
                frontmatter = self._load_frontmatter(skill_file)
                self.assertEqual(f"agentplane-control-plane-{group_name}", frontmatter["name"])
                self.assertEqual(
                    f"Generated plugin skill group for {group_name}; routes to AgentPlane CLI-first commands.",
                    frontmatter["description"],
                )
                self.assertEqual(".codex/skills/catalog.yaml", frontmatter["generated_from"])
                self.assertEqual(group_name, frontmatter["group"])
                self.assertEqual(sorted(group["domains"]), sorted(frontmatter["domains"]))
                self.assertEqual(group["source_skills"], frontmatter["source_skills"])
                self.assertEqual(group_name, group["name"])
                self.assertTrue(group["source_skills"])
                self.assertTrue(group["domains"])
                expected_domains = sorted(
                    {
                        domain
                        for skill_name in group["source_skills"]
                        for domain in entries[skill_name]["domains"]
                    }
                )
                self.assertEqual(expected_domains, sorted(group["domains"]))
                overlap = grouped_skills.intersection(group["source_skills"])
                self.assertFalse(overlap, msg=f"skills assigned to multiple plugin groups: {sorted(overlap)}")
                grouped_skills.update(group["source_skills"])

    def test_plugin_group_metadata_stays_thin_in_catalog(self) -> None:
        payload = self._load_catalog()
        for group_name, group in payload["plugin_groups"].items():
            with self.subTest(group=group_name):
                self.assertEqual({"name", "domains", "source_skills"}, set(group))

    def test_catalog_does_not_duplicate_plugin_membership_metadata(self) -> None:
        payload = self._load_catalog()
        for entry in payload["skills"]:
            with self.subTest(name=entry["name"]):
                self.assertNotIn("plugin_group", entry)
                self.assertNotIn("plugin_skill", entry.get("projection_targets", []))

    def test_compat_skills_are_marked_as_routers_in_catalog_and_text(self) -> None:
        payload = self._load_catalog()
        entries = {entry["name"]: entry for entry in payload["skills"]}
        for name in COMPAT_SKILLS:
            with self.subTest(name=name):
                self.assertEqual("compat", entries[name]["kind"])
                self.assertTrue(entries[name]["aliases"])
                text = (REPO_ROOT / ".codex" / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
                self.assertIn("CLI-first", text)
                self.assertNotIn("## Commands", text)
                self.assertIn("router", text.lower())

    def test_active_skills_do_not_route_back_to_openclaw_direct_wrappers(self) -> None:
        cases = (
            REPO_ROOT / ".codex" / "skills" / "onepanel-openresty-site-migration" / "SKILL.md",
        )
        for path in cases:
            with self.subTest(path=path):
                text = path.read_text(encoding="utf-8")
                self.assertNotIn("API wrappers", text)
                self.assertNotIn("raw signed request", text)
                self.assertNotIn("POST /api/v2/", text)

    def test_pointer_and_plugin_docs_explain_generated_layers(self) -> None:
        agents_readme = (REPO_ROOT / ".agents" / "skills" / "README.md").read_text(encoding="utf-8")
        plugin_readme = (REPO_ROOT / "plugins" / "agentplane-control-plane" / "README.md").read_text(encoding="utf-8")

        self.assertIn(".codex/skills/catalog.yaml", agents_readme)
        self.assertIn("generated", agents_readme.lower())
        self.assertIn(".codex/skills/catalog.yaml", plugin_readme)
        self.assertIn("generated", plugin_readme.lower())
        self.assertNotIn("op-linux-control-plane", plugin_readme)
        self.assertNotIn("ops/scripts/", plugin_readme)

    def test_website_skill_and_plugin_route_to_formal_website_cli(self) -> None:
        repo_skill_text = (REPO_ROOT / ".codex" / "skills" / "onepanel-website-ops" / "SKILL.md").read_text(encoding="utf-8")
        plugin_skill_text = (
            REPO_ROOT / "plugins" / "agentplane-control-plane" / "skills" / "websites" / "SKILL.md"
        ).read_text(encoding="utf-8")
        catalog_text = CATALOG_FILE.read_text(encoding="utf-8")

        self.assertIn("uv run python -m agentplane.cli website search --target <target>", repo_skill_text)
        self.assertIn("uv run python -m agentplane.cli website get --target <target> --alias <alias>", repo_skill_text)
        self.assertIn(
            "uv run python -m agentplane.cli website publish plan --target <target> --config-file <config-file> --cloudflare-env-file <cloudflare-env-file> --repo-root <repo-root>",
            repo_skill_text,
        )
        self.assertIn("uv run python -m agentplane.cli website ...", plugin_skill_text)
        self.assertNotIn("uv run python -m agentplane.cli onepanel --env <target> website", plugin_skill_text)
        self.assertNotIn("op-linux-control-plane", plugin_skill_text)
        self.assertIn("entrypoint: uv run python -m agentplane.cli website", catalog_text)

    def test_service_skill_and_plugin_route_to_formal_service_cli(self) -> None:
        repo_skill_text = (REPO_ROOT / ".codex" / "skills" / "onepanel-container-ops" / "SKILL.md").read_text(encoding="utf-8")
        plugin_skill_text = (
            REPO_ROOT / "plugins" / "agentplane-control-plane" / "skills" / "containers" / "SKILL.md"
        ).read_text(encoding="utf-8")
        catalog_text = CATALOG_FILE.read_text(encoding="utf-8")

        self.assertIn("uv run python -m agentplane.cli service search --target <target>", repo_skill_text)
        self.assertIn("uv run python -m agentplane.cli service get --target <target> --name <service>", repo_skill_text)
        self.assertIn("uv run python -m agentplane.cli service verify --target <target> --name <service>", repo_skill_text)
        self.assertIn(
            "uv run python -m agentplane.cli service plan --target <target> --name <service> --operation restart",
            repo_skill_text,
        )
        self.assertIn("uv run python -m agentplane.cli service ...", plugin_skill_text)
        self.assertNotIn("uv run python -m agentplane.cli onepanel --env <target> container", plugin_skill_text)
        self.assertNotIn("op-linux-control-plane", plugin_skill_text)
        self.assertIn("entrypoint: uv run python -m agentplane.cli service", catalog_text)

    def test_host_plugin_routes_to_formal_host_cli(self) -> None:
        plugin_skill_text = (
            REPO_ROOT / "plugins" / "agentplane-control-plane" / "skills" / "hosts" / "SKILL.md"
        ).read_text(encoding="utf-8")

        self.assertIn("uv run python -m agentplane.cli host ...", plugin_skill_text)
        self.assertNotIn("uv run python -m agentplane.cli ...`", plugin_skill_text)

    def test_template_surface_skills_use_repo_root_placeholders(self) -> None:
        cases = {
            "host-ops": (
                "--repo-root <repo-root>",
                "host automation get <target> --name <automation-name>",
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
                "website refresh-ledger --target <target> --repo-root <repo-root> --write",
            ),
        }

        for skill_name, expected_snippets in cases.items():
            text = (REPO_ROOT / ".codex" / "skills" / skill_name / "SKILL.md").read_text(encoding="utf-8")
            with self.subTest(skill=skill_name):
                self.assertNotIn("/root/work/AgentPlane", text)
                self.assertNotIn("ops.cli", text)
                for snippet in expected_snippets:
                    self.assertIn(snippet, text)

    def test_host_skill_drops_author_site_specific_automation_names(self) -> None:
        text = (REPO_ROOT / ".codex" / "skills" / "host-ops" / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("host automation search <target> --repo-root <repo-root>", text)
        self.assertIn("host automation verify <target> --name <automation-name> --repo-root <repo-root>", text)
        self.assertNotIn("wsl-agentplane-secrets-backup", text)
        self.assertNotIn("wsl-zzz-skills-sync", text)

    def test_app_skill_routes_catalog_to_app_and_runtime_to_service(self) -> None:
        repo_skill_text = (REPO_ROOT / ".codex" / "skills" / "onepanel-app-ops" / "SKILL.md").read_text(encoding="utf-8")
        plugin_skill_text = (
            REPO_ROOT / "plugins" / "agentplane-control-plane" / "skills" / "apps" / "SKILL.md"
        ).read_text(encoding="utf-8")
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
        self.assertIn("uv run python -m agentplane.cli app ...", plugin_skill_text)
        self.assertNotIn("uv run python -m agentplane.cli onepanel --env <target>", plugin_skill_text)
        self.assertNotIn("op-linux-control-plane", plugin_skill_text)
        self.assertIn("entrypoint: uv run python -m agentplane.cli", catalog_text)

    def test_tenant_skill_routes_to_formal_app_resource_cli(self) -> None:
        repo_skill_text = (REPO_ROOT / ".codex" / "skills" / "app-resource-ops" / "SKILL.md").read_text(encoding="utf-8")
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
        repo_skill_text = (REPO_ROOT / ".codex" / "skills" / "projection-ops" / "SKILL.md").read_text(encoding="utf-8")
        plugin_skill_text = (
            REPO_ROOT / "plugins" / "agentplane-control-plane" / "skills" / "ledgers" / "SKILL.md"
        ).read_text(encoding="utf-8")
        catalog_text = CATALOG_FILE.read_text(encoding="utf-8")

        self.assertIn("uv run python -m agentplane.cli projection runtime-env plan --target <target> --app <app>", repo_skill_text)
        self.assertIn("uv run python -m agentplane.cli projection runtime-env apply --target <target> --app <app>", repo_skill_text)
        self.assertIn("uv run python -m agentplane.cli projection runtime-env verify --target <target> --app <app>", repo_skill_text)
        self.assertIn("uv run python -m agentplane.cli projection verification run --target <target> --profile <profile>", repo_skill_text)
        self.assertIn("uv run python -m agentplane.cli projection fixture plan --target <target> --profile wsl-fixture", repo_skill_text)
        self.assertIn("uv run python -m agentplane.cli projection ledger refresh --target <target>", repo_skill_text)
        self.assertIn("uv run python -m agentplane.cli projection ...", plugin_skill_text)
        self.assertNotIn("op-linux-control-plane", plugin_skill_text)
        self.assertIn("entrypoint: uv run python -m agentplane.cli projection", catalog_text)


if __name__ == "__main__":
    unittest.main()

