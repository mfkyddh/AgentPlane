from __future__ import annotations

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

    def test_tests_support_layer_owns_shared_helpers(self) -> None:
        support_files = {
            path.name for path in (REPO_ROOT / "tests" / "support").glob("*.py")
        }
        self.assertTrue({"paths.py", "cli.py", "markers.py", "app_resources.py"}.issubset(support_files))
        self.assertFalse((REPO_ROOT / "tests" / "app_resource_path_fixtures.py").exists())
        self.assertFalse((REPO_ROOT / "tests" / "test_app_cli.py").exists())

    def test_tests_are_grouped_by_domain_directory(self) -> None:
        expected_dirs = {
            "app",
            "compose",
            "host",
            "inventory",
            "onepanel",
            "projection",
            "repository",
            "runtime",
            "secret_management",
            "service",
            "website",
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
        self.assertIn("uv run python -m pytest", text)
        self.assertIn("uv run python -m agentplane.cli --help", text)
        self.assertNotIn("live-gate run --execute", text)


if __name__ == "__main__":
    unittest.main()

