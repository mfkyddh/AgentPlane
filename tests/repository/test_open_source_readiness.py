from __future__ import annotations

import re
import tomllib
import unittest

from tests.support.paths import REPO_ROOT


class OpenSourceReadinessTests(unittest.TestCase):
    def test_root_open_source_governance_files_exist(self) -> None:
        expected = (
            "LICENSE",
            "CONTRIBUTING.md",
            "SECURITY.md",
            "CODE_OF_CONDUCT.md",
            "SUPPORT.md",
            "README.md",
            ".github/workflows/ci.yml",
        )
        for relative_path in expected:
            with self.subTest(path=relative_path):
                self.assertTrue((REPO_ROOT / relative_path).is_file(), f"missing {relative_path}")

    def test_pyproject_exposes_public_package_metadata(self) -> None:
        payload = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        project = payload["project"]

        self.assertEqual("agentplane-cli", project["name"])
        self.assertEqual("README.md", project["readme"])
        self.assertEqual("MIT", project["license"])
        self.assertIn("AgentPlane Maintainers", {author["name"] for author in project["authors"]})
        self.assertIn("Topic :: System :: Systems Administration", project["classifiers"])
        self.assertIn("Operating System :: OS Independent", project["classifiers"])

    def test_reference_docs_include_testing_and_open_source_readiness(self) -> None:
        for relative_path in (
            "docs/reference/testing-architecture.md",
            "docs/reference/open-source-readiness.md",
        ):
            with self.subTest(path=relative_path):
                text = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
                self.assertIn("single checkout" if "open-source" in relative_path else "Default Gate", text)

    def test_architecture_directory_contains_only_active_contract_docs(self) -> None:
        actual = {path.name for path in (REPO_ROOT / "docs" / "architecture").glob("*.md")}
        expected = {
            "README.md",
            "control-plane.md",
            "linux-governance.md",
            "agentplane-app-collaboration.md",
        }
        self.assertEqual(expected, actual)

    def test_reference_and_maintainer_docs_have_standard_metadata(self) -> None:
        roots = (
            REPO_ROOT / "docs" / "reference",
            REPO_ROOT / "docs" / "maintainers",
        )
        for root in roots:
            for path in root.glob("*.md"):
                with self.subTest(path=path.relative_to(REPO_ROOT)):
                    text = path.read_text(encoding="utf-8")
                    self.assertTrue(text.startswith("---\n"), "missing metadata block")
                    header = text.split("---", 2)[1]
                    self.assertRegex(header, r"(?m)^status: active$")
                    self.assertRegex(header, r"(?m)^owner: .+$")
                    self.assertRegex(header, r"(?m)^last_verified: \d{4}-\d{2}-\d{2}$")
                    self.assertRegex(header, r"(?m)^superseded_by: null$")

    def test_active_architecture_and_runbooks_do_not_keep_redirect_stubs(self) -> None:
        forbidden = re.compile(
            r"本文已 superseded|本手册已并入|正文已归档到|过渡 stub|redirect stub|跳转页|仅保留历史重定向|仅保留给历史引用|本页已降级",
            re.IGNORECASE,
        )
        for root in (REPO_ROOT / "docs" / "architecture", REPO_ROOT / "docs" / "runbooks"):
            for path in root.glob("*.md"):
                with self.subTest(path=path.relative_to(REPO_ROOT)):
                    text = path.read_text(encoding="utf-8")
                    self.assertIsNone(forbidden.search(text))

    def test_readme_presents_cross_platform_first_run_path(self) -> None:
        text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

        # README is a thin entry; detailed platform steps live in cross-platform.md
        self.assertIn("bootstrap inspect-local", text)
        self.assertIn("bootstrap doctor", text)
        # Cross-platform details are linked from README, not duplicated
        open_source = (REPO_ROOT / "docs" / "reference" / "open-source-readiness.md").read_text(encoding="utf-8")
        self.assertIn("single checkout", open_source)

    def test_docs_and_truth_do_not_embed_author_machine_paths(self) -> None:
        roots = ("README.md", "docs", "inventory", "infra", "templates")
        forbidden = re.compile(r"D:[/\\]Projects[/\\]AgentPlane|C:[/\\]Users[/\\]Administrator", re.IGNORECASE)

        for root in roots:
            path = REPO_ROOT / root
            files = [path] if path.is_file() else [item for item in path.rglob("*") if item.is_file()]
            for file in files:
                with self.subTest(path=file.relative_to(REPO_ROOT)):
                    text = file.read_text(encoding="utf-8", errors="ignore")
                    self.assertIsNone(forbidden.search(text))

    def test_tests_support_layer_owns_shared_helpers(self) -> None:
        support_files = {
            path.name for path in (REPO_ROOT / "tests" / "support").glob("*.py")
        }
        self.assertTrue(
            {
                "paths.py",
                "cli.py",
                "markers.py",
                "app_resources.py",
                "app_object.py",
                "service_cli.py",
            }.issubset(support_files)
        )
        self.assertFalse((REPO_ROOT / "tests" / "app_resource_path_fixtures.py").exists())
        self.assertFalse((REPO_ROOT / "tests" / "test_app_cli.py").exists())

    def test_tests_are_grouped_by_domain_directory(self) -> None:
        expected_dirs = {
            "app",
            "compose",
            "infra",
            "inventory",
            "onepanel",
            "projection",
            "repository",
            "runtime",
            "secret_management",
            "service",
            "ingress",
        }
        actual_dirs = {
            path.name for path in (REPO_ROOT / "tests").iterdir() if path.is_dir() and not path.name.startswith("__")
        }

        self.assertTrue(expected_dirs.issubset(actual_dirs))
        root_test_files = list((REPO_ROOT / "tests").glob("test_*.py"))
        self.assertEqual([], root_test_files)

    def test_ci_runs_default_gate_on_supported_host_platforms(self) -> None:
        text = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

        self.assertIn("ubuntu-latest", text)
        self.assertIn("macos-latest", text)
        self.assertIn("windows-latest", text)
        self.assertIn("uv run python -m agentplane.cli repo health-check --repo-root .", text)
        self.assertNotIn("live-gate run --execute", text)

    def test_ci_never_executes_live_gate(self) -> None:
        for workflow in (REPO_ROOT / ".github" / "workflows").glob("*.yml"):
            text = workflow.read_text(encoding="utf-8")
            with self.subTest(path=workflow.name):
                self.assertIsNone(re.search(r"infra\s+live-gate\s+run[\s\S]{0,200}--execute", text))

    def test_release_process_uses_formal_release_check(self) -> None:
        text = (REPO_ROOT / "docs" / "reference" / "release-process.md").read_text(encoding="utf-8")

        self.assertIn("agentplane.cli repo release-check --repo-root .", text)
        self.assertIn("agentplane.cli repo health-check --repo-root .", text)


if __name__ == "__main__":
    unittest.main()
