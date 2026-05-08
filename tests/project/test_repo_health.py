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


# ======================================================================
# From: test_repo_health_cli.py
# ======================================================================


class RepoHealthCliTests(unittest.TestCase):
    def test_repo_health_check_can_run_lightweight_checks(self) -> None:
        result = run_cli(
            "project",
            "health-check",
            "--repo-root",
            str(REPO_ROOT),
            "--skip-ruff",
            "--skip-tests",
        )

        payload = json.loads(result.stdout)
        self.assertEqual(
            ["cli-help", "secret-scan", "privacy-scan", "docs-sanity", "skills-check"],
            [check["name"] for check in payload["checks"]],
        )

    def test_docs_sanity_reports_retired_entrypoints(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            (root / "docs" / "bad.md").write_text("Use `agentplane host audit`.\n", encoding="utf-8")

            result = run_cli("project", "docs-sanity", "--repo-root", str(root))

        self.assertEqual(1, result.returncode)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["ok"])
        self.assertEqual("retired-host-entrypoint", payload["issues"][0]["kind"])

    def test_docs_sanity_reports_isolated_active_docs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("# Entry\n", encoding="utf-8")
            (root / "docs").mkdir()
            (root / "docs" / "orphan.md").write_text("# Orphan\n", encoding="utf-8")

            result = run_cli("project", "docs-sanity", "--repo-root", str(root))

        self.assertEqual(1, result.returncode)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["ok"])
        self.assertEqual("isolated-active-doc", payload["issues"][0]["kind"])
        self.assertEqual("docs/orphan.md", payload["issues"][0]["path"])

    def test_docs_sanity_accepts_docs_linked_from_documentation_map(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("[Docs](docs/README.md)\n", encoding="utf-8")
            (root / "docs").mkdir()
            (root / "docs" / "README.md").write_text("[Guide](guide.md)\n", encoding="utf-8")
            (root / "docs" / "guide.md").write_text("[Docs](README.md)\n", encoding="utf-8")

            result = run_cli("project", "docs-sanity", "--repo-root", str(root))

        self.assertEqual(0, result.returncode, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])

    def test_docs_sanity_reports_missing_frontmatter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("# Entry\n", encoding="utf-8")
            (root / "docs").mkdir()
            (root / "docs" / "reference").mkdir()
            (root / "docs" / "reference" / "spec.md").write_text(
                "# Spec\n\nSome content without frontmatter.\n", encoding="utf-8"
            )

            result = run_cli("project", "docs-sanity", "--repo-root", str(root))

        self.assertEqual(1, result.returncode)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["ok"])
        kinds = [i["kind"] for i in payload["issues"]]
        self.assertIn("missing-frontmatter", kinds)

    def test_docs_sanity_warns_on_readme_length(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("\n".join([f"Line {i}" for i in range(250)]), encoding="utf-8")
            (root / "docs").mkdir()

            result = run_cli("project", "docs-sanity", "--repo-root", str(root))

        payload = json.loads(result.stdout)
        # Warning should not cause failure
        self.assertTrue(payload["ok"])
        kinds = [i["kind"] for i in payload["issues"]]
        self.assertIn("readme-too-long", kinds)

    def test_docs_sanity_warns_on_missing_conclusion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("[Docs](docs/README.md)\n", encoding="utf-8")
            (root / "docs").mkdir()
            (root / "docs" / "README.md").write_text("[Spec](reference/spec.md)\n", encoding="utf-8")
            (root / "docs" / "reference").mkdir()
            (root / "docs" / "reference" / "spec.md").write_text(
                "---\nstatus: active\nowner: test\nlast_verified: 2026-04-25\nsuperseded_by: null\naudience: agent\n---\n\n# Spec\n\nNo conclusion here.\n",
                encoding="utf-8",
            )

            result = run_cli("project", "docs-sanity", "--repo-root", str(root))

        payload = json.loads(result.stdout)
        # Missing conclusion is a warning, not an error
        self.assertTrue(payload["ok"])
        kinds = [i["kind"] for i in payload["issues"]]
        self.assertIn("missing-conclusion", kinds)

    def test_docs_sanity_reports_broken_image_references(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("# Entry\n![missing](docs/assets/missing.png)\n", encoding="utf-8")
            (root / "docs").mkdir()

            result = run_cli("project", "docs-sanity", "--repo-root", str(root))

        self.assertEqual(1, result.returncode)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["ok"])
        kinds = [i["kind"] for i in payload["issues"]]
        self.assertIn("broken-image-reference", kinds)

    def test_docs_sanity_reports_archive_doc_active(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("# Entry\n", encoding="utf-8")
            (root / "docs").mkdir()
            (root / "docs" / "archive").mkdir()
            (root / "docs" / "archive" / "old.md").write_text(
                "---\nstatus: active\nowner: test\nlast_verified: 2026-04-25\nsuperseded_by: null\naudience: agent\n---\n\n# Old\n结论： archived.\n",
                encoding="utf-8",
            )

            result = run_cli("project", "docs-sanity", "--repo-root", str(root))

        self.assertEqual(1, result.returncode)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["ok"])
        kinds = [i["kind"] for i in payload["issues"]]
        self.assertIn("archive-doc-active", kinds)

    def test_secret_scan_reports_git_visible_secret_material(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init"], cwd=root, text=True, capture_output=True, check=True)
            token = "sk-" + "thisvalueislongenoughtolooksecret"
            (root / "app.env").write_text(f"OPENAI_API_KEY={token}\n", encoding="utf-8")

            result = run_cli("project", "secret-scan", "--repo-root", str(root))

        self.assertEqual(1, result.returncode)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["ok"])
        self.assertEqual("app.env", payload["issues"][0]["path"])

    def test_secret_scan_allowlist_suppresses_explicit_exception(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init"], cwd=root, text=True, capture_output=True, check=True)
            token = "sk-" + "thisvalueislongenoughtolooksecret"
            (root / "app.env").write_text(f"OPENAI_API_KEY={token}\n", encoding="utf-8")
            (root / ".secret-scan-allowlist").write_text("openai-token app.env 1\n", encoding="utf-8")

            result = run_cli("project", "secret-scan", "--repo-root", str(root))

        self.assertEqual(0, result.returncode, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])

    def test_privacy_scan_reports_private_public_endpoint_material(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init"], cwd=root, text=True, capture_output=True, check=True)
            private_domain = "token." + "zzzai" + ".cloud"
            (root / "README.md").write_text(f"Production endpoint: https://{private_domain}\n", encoding="utf-8")

            result = run_cli("project", "privacy-scan", "--repo-root", str(root))

        self.assertEqual(1, result.returncode)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["ok"])
        self.assertEqual("private-domain", payload["issues"][0]["kind"])

    def test_privacy_scan_reports_tracked_private_inventory_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init"], cwd=root, text=True, capture_output=True, check=True)
            inventory = root / "inventory" / "servers" / "prod0-main" / "inventory.json"
            inventory.parent.mkdir(parents=True)
            inventory.write_text("{}\n", encoding="utf-8")

            result = run_cli("project", "privacy-scan", "--repo-root", str(root))

        self.assertEqual(1, result.returncode)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["ok"])
        self.assertEqual("private-inventory", payload["issues"][0]["kind"])

    def test_release_check_reports_dirty_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init"], cwd=root, text=True, capture_output=True, check=True)
            (root / "README.md").write_text("dirty\n", encoding="utf-8")

            result = run_cli(
                "project",
                "release-check",
                "--repo-root",
                str(root),
            )

        self.assertEqual(1, result.returncode)
        payload = json.loads(result.stdout)
        git_check = next(check for check in payload["checks"] if check["name"] == "git-clean")
        self.assertFalse(git_check["ok"])


