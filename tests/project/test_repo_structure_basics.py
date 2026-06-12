from __future__ import annotations

import re
import subprocess
import tomllib
import unittest
from pathlib import Path

import pytest
from tests.support.paths import REPO_ROOT

pytestmark = pytest.mark.integration

ALLOWED_TRACKED_TOP_LEVELS = {
    ".agents",
    ".codex",
    ".editorconfig",
    ".gitattributes",
    ".github",
    ".gitignore",
    ".pre-commit-config.yaml",
    ".secret-scan-allowlist",
    "AGENTS.md",
    "CHANGELOG.md",
    "CLAUDE.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "README.md",
    "agentplane",
    "docs",
    "infra",
    "inventory",
    "pyproject.toml",
    "templates",
    "tests",
    "uv.lock",
    "PROGRESS.md",
    ".claude",
    "scripts",
}
FORBIDDEN_TRACKED_TOP_LEVELS = {"ops", "tools"}
FORBIDDEN_PRODUCTION_MODULE_NAMES = {"utils.py", "helpers.py", "misc.py"}
ACTIVE_DOC_ROOTS = (
    REPO_ROOT / "README.md",
    REPO_ROOT / "AGENTS.md",
    REPO_ROOT / "docs" / "core",
    REPO_ROOT / "docs" / "decisions",
)
REMOVED_ENTRYPOINT_MARKERS = (
    "scripts/check_commit_message.py",
    "agentplane/scripts/remote/run_remote_bash.sh",
    "agentplane/scripts/onepanel/api_request.py",
    "docs/archive/reference/compat-retirement-ledger.md",
)
REQUIRED_GITIGNORE_PATTERNS = {
    "secrets/",
    "local/",
    "tmp/",
    ".venv/",
    ".pytest_cache/",
    ".ruff_cache/",
    ".worktrees/",
    ".workbuddy/",
    "__pycache__/",
    "*.pyc",
    "node_modules/",
}
REQUIRED_LOCAL_STATE_DOC_MARKERS = {
    "## 🔒 本地态合同",
    "`secrets/`",
    "`tmp/`",
    "`.venv/`",
    "`.pytest_cache/`、`.ruff_cache/`、`__pycache__/`",
    "`.workbuddy/`",
}


def tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line.strip() and (REPO_ROOT / line).exists()]


def active_doc_files() -> list[Path]:
    files: list[Path] = []
    for root in ACTIVE_DOC_ROOTS:
        if root.is_file():
            files.append(root)
        elif root.is_dir():
            files.extend(sorted(root.rglob("*.md")))
    return files


def collect_active_docs() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in ACTIVE_TEMPLATE_DOCS)


def collect_active_template_surface() -> str:
    files = (*ACTIVE_TEMPLATE_DOCS, *ACTIVE_TEMPLATE_SKILLS)
    return "\n".join(path.read_text(encoding="utf-8") for path in files)




class RepositoryStructureTests(unittest.TestCase):
    def test_tracked_top_level_entries_are_declared(self) -> None:
        top_levels = {path.split("/", 1)[0] for path in tracked_files()}

        self.assertFalse(top_levels & FORBIDDEN_TRACKED_TOP_LEVELS)
        self.assertLessEqual(top_levels, ALLOWED_TRACKED_TOP_LEVELS)

    def test_no_public_compatibility_entrypoints_are_tracked(self) -> None:
        tracked = set(tracked_files())

        for marker in REMOVED_ENTRYPOINT_MARKERS:
            with self.subTest(marker=marker):
                self.assertNotIn(marker, tracked)

    def test_active_docs_do_not_reference_removed_entrypoints(self) -> None:
        for path in active_doc_files():
            text = path.read_text(encoding="utf-8")
            for marker in REMOVED_ENTRYPOINT_MARKERS:
                with self.subTest(path=str(path.relative_to(REPO_ROOT)), marker=marker):
                    self.assertNotIn(marker, text)

    def test_new_production_modules_do_not_use_bucket_names(self) -> None:
        production_modules = [
            path
            for path in tracked_files()
            if path.startswith("agentplane/") and Path(path).name in FORBIDDEN_PRODUCTION_MODULE_NAMES
        ]

        self.assertEqual([], production_modules)

    def test_local_state_is_ignored_and_documented(self) -> None:
        gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
        structure_doc = (REPO_ROOT / "docs" / "archive" / "reference" / "repository-structure.md").read_text(encoding="utf-8")

        for pattern in REQUIRED_GITIGNORE_PATTERNS:
            with self.subTest(kind="gitignore", pattern=pattern):
                self.assertIn(pattern, gitignore)

        for marker in REQUIRED_LOCAL_STATE_DOC_MARKERS:
            with self.subTest(kind="structure-doc", marker=marker):
                self.assertIn(marker, structure_doc)



# ======================================================================
# From: test_open_source_readiness.py
# ======================================================================


class OpenSourceReadinessTests(unittest.TestCase):
    def test_root_open_source_governance_files_exist(self) -> None:
        expected = (
            "LICENSE",
            "CONTRIBUTING.md",
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
            "docs/archive/reference/testing-architecture.md",
            "docs/archive/reference/open-source-readiness.md",
        ):
            with self.subTest(path=relative_path):
                text = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
                self.assertIn("single checkout" if "open-source" in relative_path else "默认门禁", text)

    def test_architecture_directory_contains_only_active_contract_docs(self) -> None:
        actual = {path.name for path in (REPO_ROOT / "docs" / "archive" / "architecture").glob("*.md")}
        expected = {
            "README.md",
            "control-plane.md",
            "linux-governance.md",
            "agentplane-app-collaboration.md",
            "1panel-v2.1.5-project.md",
        }
        self.assertEqual(expected, actual)

    def test_reference_and_maintainer_docs_have_standard_metadata(self) -> None:
        roots = (
            REPO_ROOT / "docs" / "core",
            REPO_ROOT / "docs" / "decisions",
        )
        for root in roots:
            for path in root.glob("*.md"):
                with self.subTest(path=str(path.relative_to(REPO_ROOT))):
                    text = path.read_text(encoding="utf-8")
                    self.assertTrue(text.startswith("---\n"), "missing metadata block")
                    header = text.split("---", 2)[1]
                    self.assertRegex(header, r"(?m)^status: active$")
                    self.assertRegex(header, r"(?m)^owner: .+$")
                    self.assertRegex(header, r"(?m)^last_verified: \d{4}-\d{2}-\d{2}$")

    def test_active_architecture_and_runbooks_do_not_keep_redirect_stubs(self) -> None:
        forbidden = re.compile(
            r"本文已 superseded|本手册已并入|正文已归档到|过渡 stub|redirect stub|跳转页|仅保留历史重定向|仅保留给历史引用|本页已降级",
            re.IGNORECASE,
        )
        for root in (REPO_ROOT / "docs" / "archive" / "architecture", REPO_ROOT / "docs" / "archive" / "runbooks"):
            for path in root.glob("*.md"):
                with self.subTest(path=str(path.relative_to(REPO_ROOT))):
                    text = path.read_text(encoding="utf-8")
                    self.assertIsNone(forbidden.search(text))

    def test_readme_presents_cross_platform_first_run_path(self) -> None:
        text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

        # README is a thin entry; detailed platform steps live in getting-started.md
        self.assertIn("infra bootstrap doctor", text)

    def test_docs_and_truth_do_not_embed_author_machine_paths(self) -> None:
        roots = ("README.md", "docs", "inventory", "infra", "templates")
        forbidden = re.compile(r"D:[/\\]Projects[/\\]AgentPlane|C:[/\\]Users[/\\]Administrator", re.IGNORECASE)

        for root in roots:
            path = REPO_ROOT / root
            files = [path] if path.is_file() else [item for item in path.rglob("*") if item.is_file()]
            for file in files:
                with self.subTest(path=str(file.relative_to(REPO_ROOT))):
                    text = file.read_text(encoding="utf-8", errors="ignore")
                    self.assertIsNone(forbidden.search(text))

    def test_tests_support_layer_owns_shared_helpers(self) -> None:
        support_files = {path.name for path in (REPO_ROOT / "tests" / "support").glob("*.py")}
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
            "project",
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
        self.assertIn("uv run python -m agentplane.cli test fast --tb=short", text)
        self.assertIn("uv run python -m agentplane.cli project docs-sanity --repo-root .", text)
        self.assertIn("uv run python -m agentplane.cli project secret-scan --repo-root .", text)
        self.assertIn("uv run python -m agentplane.cli project privacy-scan --repo-root .", text)
        self.assertIn("uv run python -m agentplane.cli project release-check --repo-root .", text)
        self.assertNotIn("live-gate run --execute", text)

    def test_ci_never_executes_live_gate(self) -> None:
        for workflow in (REPO_ROOT / ".github" / "workflows").glob("*.yml"):
            text = workflow.read_text(encoding="utf-8")
            with self.subTest(path=workflow.name):
                self.assertIsNone(re.search(r"infra\s+live-gate\s+run[\s\S]{0,200}--execute", text))

    def test_release_process_uses_formal_release_check(self) -> None:
        text = (REPO_ROOT / "docs" / "archive" / "reference" / "release-process.md").read_text(encoding="utf-8")

        self.assertIn("repo release-check --repo-root .", text)
        self.assertIn("repo health-check --repo-root .", text)



class SkillCatalogTests(unittest.TestCase):
    def _catalog_entries(self) -> list[dict[str, str]]:
        text = (REPO_ROOT / ".agents" / "skills" / "catalog.yaml").read_text(encoding="utf-8")
        entries: list[dict[str, str]] = []
        current: dict[str, str] | None = None
        for line in text.splitlines():
            if line.startswith("  - name: "):
                if current is not None:
                    entries.append(current)
                current = {"name": line.split(": ", 1)[1]}
            elif current is not None and line.startswith("    source_path: "):
                current["source_path"] = line.split(": ", 1)[1]
            elif current is not None and line.startswith("    frontmatter_name: "):
                current["frontmatter_name"] = line.split(": ", 1)[1]
        if current is not None:
            entries.append(current)
        return entries

    def test_tracked_skills_are_registered_in_catalog(self) -> None:
        result = subprocess.run(
            ["git", "ls-files", ".agents/skills"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        tracked_skill_names = {
            line.split("/")[2]
            for line in result.stdout.splitlines()
            if line.startswith(".agents/skills/") and line.endswith("/SKILL.md")
        }
        catalog_names = {entry["name"] for entry in self._catalog_entries()}

        self.assertEqual(tracked_skill_names, catalog_names)

    def test_catalog_skill_paths_and_frontmatter_match(self) -> None:
        for entry in self._catalog_entries():
            with self.subTest(skill=entry["name"]):
                source_path = entry["source_path"]
                skill_path = REPO_ROOT / source_path

                self.assertTrue(skill_path.is_file(), msg=f"missing catalog skill path: {source_path}")
                text = skill_path.read_text(encoding="utf-8")
                frontmatter_name = re.search(r"^name:\s*(.+)$", text, flags=re.MULTILINE)
                self.assertEqual(entry["name"], Path(source_path).parent.name)
                self.assertIsNotNone(frontmatter_name)
                self.assertEqual(entry["name"], frontmatter_name.group(1).strip('"'))
                self.assertEqual(entry["name"], entry["frontmatter_name"])


# ======================================================================
# From: test_docs_no_legacy_terms.py
# ======================================================================

ACTIVE_TEMPLATE_DOCS = (
    REPO_ROOT / "README.md",
    REPO_ROOT / "AGENTS.md",
    REPO_ROOT / "docs" / "archive" / "architecture" / "README.md",
    REPO_ROOT / "docs" / "archive" / "architecture" / "control-plane.md",
    REPO_ROOT / "docs" / "archive" / "architecture" / "agentplane-app-collaboration.md",
    REPO_ROOT / "docs" / "archive" / "architecture" / "linux-governance.md",
    REPO_ROOT / "docs" / "archive" / "reference" / "app-repository-standard.md",
    REPO_ROOT / "docs" / "archive" / "runbooks" / "control-plane-domain-onboarding.md",
    REPO_ROOT / "docs" / "archive" / "runbooks" / "control-plane-agent-execution-flow.md",
)
ACTIVE_TEMPLATE_SKILLS = (
    REPO_ROOT / ".agents" / "skills" / "agentplane-app-ops" / "SKILL.md",
    REPO_ROOT / ".agents" / "skills" / "agentplane-service-ops" / "SKILL.md",
    REPO_ROOT / ".agents" / "skills" / "agentplane-infra-ops" / "SKILL.md",
    REPO_ROOT / ".agents" / "skills" / "agentplane-ingress-ops" / "SKILL.md",
)
ARCHITECTURE_CORE_CONTRACT_LINKS = (
    "[control-plane.md](control-plane.md)",
    "[linux-governance.md](linux-governance.md)",
    "[agentplane-app-collaboration.md](agentplane-app-collaboration.md)",
)
ARCHITECTURE_TEMPLATE_LINKS = ("[app-repository-standard.md](../reference/app-repository-standard.md)",)
FORBIDDEN_TEMPLATE_DEFAULTS = (
    "/root/work/AgentPlane",
    "D:\\Projects\\AgentPlane",
    "ops.cli",
    "separate checkout",
    "separate checkouts",
)


# ======================================================================
# From: test_pyproject_config.py
# ======================================================================


class PyprojectConfigTests(unittest.TestCase):
    def test_project_declares_build_system_for_local_package(self) -> None:
        payload = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

        self.assertIn("build-system", payload)
        self.assertEqual("hatchling.build", payload["build-system"]["build-backend"])
        self.assertIn("tool", payload)
        self.assertEqual("agentplane-cli", payload["project"]["name"])
        self.assertEqual("agentplane.cli.app:main", payload["project"]["scripts"]["agentplane"])
        self.assertEqual(["agentplane"], payload["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"])



# ======================================================================
# Drift prevention: no local REPO_ROOT or run_cli definitions
# ======================================================================


class TestInfrastructureDriftPrevention(unittest.TestCase):
    """Guard tests that prevent re-introduction of duplicated test helpers."""

    def test_no_local_repo_root_definitions_in_test_files(self) -> None:
        """Every test file must import REPO_ROOT from tests.support.paths, not define it locally."""
        test_dir = REPO_ROOT / "tests"
        violations: list[str] = []
        for path in sorted(test_dir.rglob("*.py")):
            if path.name == "paths.py":
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if re.search(r"^REPO_ROOT\s*=\s*Path\(__file__\)", text, re.MULTILINE):
                violations.append(str(path.relative_to(REPO_ROOT)))
        self.assertEqual([], violations, msg=f"Local REPO_ROOT definitions found: {violations}")

    def test_no_local_run_cli_definitions_in_test_files(self) -> None:
        """Every test file must import run_agentplane_cli from tests.support.cli, not define run_cli locally."""
        test_dir = REPO_ROOT / "tests"
        violations: list[str] = []
        for path in sorted(test_dir.rglob("*.py")):
            if path.parent.name == "support" and path.name in {"cli.py", "app_delivery_cli.py", "service_cli.py"}:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if re.search(r"^def run_cli\(", text, re.MULTILINE):
                violations.append(str(path.relative_to(REPO_ROOT)))
        self.assertEqual([], violations, msg=f"Local run_cli definitions found: {violations}")
