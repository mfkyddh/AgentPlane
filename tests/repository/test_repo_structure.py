from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

import pytest
from agentplane.cli.cleanup import apply_cleanup_plan, build_cleanup_plan
from agentplane.domain.app.catalog import load_app_catalog, write_app_catalog
from agentplane.domain.app.models import AppCatalogEntry
from agentplane.runtime.path_policy import assert_canonical_ref, is_host_specific_path
from tests.support.paths import REPO_ROOT

pytestmark = pytest.mark.e2e

ALLOWED_TRACKED_TOP_LEVELS = {
    ".agents",
    ".editorconfig",
    ".gitattributes",
    ".githooks",
    ".github",
    ".gitignore",
    ".secret-scan-allowlist",
    "AGENTS.md",
    "CHANGELOG.md",
    "CODE_OF_CONDUCT.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "README.md",
    "ROADMAP.md",
    "SECURITY.md",
    "SUPPORT.md",
    "agentplane",
    "docs",
    "infra",
    "inventory",
    "pyproject.toml",
    "templates",
    "tests",
    "uv.lock",
}
FORBIDDEN_TRACKED_TOP_LEVELS = {"scripts", "ops", "tools"}
FORBIDDEN_PRODUCTION_MODULE_NAMES = {"utils.py", "helpers.py", "misc.py"}
ACTIVE_DOC_ROOTS = (
    REPO_ROOT / "README.md",
    REPO_ROOT / "AGENTS.md",
    REPO_ROOT / "docs" / "architecture",
    REPO_ROOT / "docs" / "reference",
    REPO_ROOT / "docs" / "runbooks",
    REPO_ROOT / "docs" / "maintainers",
)
REMOVED_ENTRYPOINT_MARKERS = (
    "scripts/check_commit_message.py",
    "agentplane/scripts/remote/run_remote_bash.sh",
    "agentplane/scripts/onepanel/api_request.py",
    "docs/reference/compat-retirement-ledger.md",
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
    "## 本地态合同",
    "`secrets/`",
    "`local/`",
    "`tmp/`",
    "`.venv/`",
    "`.pytest_cache/`、`.ruff_cache/`、`__pycache__/`",
    "`.worktrees/`",
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
        structure_doc = (REPO_ROOT / "docs" / "reference" / "repository-structure.md").read_text(encoding="utf-8")

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
                with self.subTest(path=str(path.relative_to(REPO_ROOT))):
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
                with self.subTest(path=str(path.relative_to(REPO_ROOT))):
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
                with self.subTest(path=str(file.relative_to(REPO_ROOT))):
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

# ======================================================================
# From: test_docs_no_legacy_terms.py
# ======================================================================

REPO_ROOT = Path(__file__).resolve().parents[2]
ACTIVE_TEMPLATE_DOCS = (
    REPO_ROOT / "README.md",
    REPO_ROOT / "AGENTS.md",
    REPO_ROOT / "docs" / "architecture" / "README.md",
    REPO_ROOT / "docs" / "architecture" / "control-plane.md",
    REPO_ROOT / "docs" / "architecture" / "agentplane-app-collaboration.md",
    REPO_ROOT / "docs" / "architecture" / "linux-governance.md",
    REPO_ROOT / "docs" / "reference" / "app-repository-standard.md",
    REPO_ROOT / "docs" / "runbooks" / "control-plane-domain-onboarding.md",
    REPO_ROOT / "docs" / "runbooks" / "control-plane-agent-execution-flow.md",
)
ACTIVE_TEMPLATE_SKILLS = (
    REPO_ROOT / ".agents" / "skills" / "onepanel-app-ops" / "SKILL.md",
    REPO_ROOT / ".agents" / "skills" / "onepanel-container-ops" / "SKILL.md",
    REPO_ROOT / ".agents" / "skills" / "onepanel-firewall-ops" / "SKILL.md",
    REPO_ROOT / ".agents" / "skills" / "onepanel-website-ops" / "SKILL.md",
)
ARCHITECTURE_CORE_CONTRACT_LINKS = (
    "[control-plane.md](control-plane.md)",
    "[linux-governance.md](linux-governance.md)",
    "[agentplane-app-collaboration.md](agentplane-app-collaboration.md)",
)
ARCHITECTURE_TEMPLATE_LINKS = (
    "[control-plane-path-policy.md](../reference/control-plane-path-policy.md)",
    "[app-repository-standard.md](../reference/app-repository-standard.md)",
)
FORBIDDEN_TEMPLATE_DEFAULTS = (
    "/root/work/AgentPlane",
    "D:\\Projects\\AgentPlane",
    "ops.cli",
    "separate checkout",
    "separate checkouts",
)

def collect_active_docs() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in ACTIVE_TEMPLATE_DOCS)

def collect_active_template_surface() -> str:
    files = (*ACTIVE_TEMPLATE_DOCS, *ACTIVE_TEMPLATE_SKILLS)
    return "\n".join(path.read_text(encoding="utf-8") for path in files)

class DocsNoLegacyTermsTests(unittest.TestCase):
    def test_template_docs_do_not_reintroduce_author_site_defaults(self) -> None:
        text = collect_active_template_surface()
        for forbidden in FORBIDDEN_TEMPLATE_DEFAULTS:
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, text)

    def test_readme_describes_template_bootstrap_path(self) -> None:
        text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("bootstrap inspect-local", text)
        self.assertIn("bootstrap init-secrets", text)
        self.assertIn("bootstrap verify-secrets", text)
        self.assertIn("bootstrap doctor", text)

    def test_readme_describes_template_truth_and_runtime_model(self) -> None:
        text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("Agent-first control plane template repository", text)
        # Detailed truth/runtime model lives in execution-flow runbook
        execution_flow = (
            REPO_ROOT / "docs" / "runbooks" / "control-plane-agent-execution-flow.md"
        ).read_text(encoding="utf-8")
        self.assertIn("Git tracked truth + local secrets", execution_flow)

    def test_entry_indexes_link_template_contracts(self) -> None:
        # Core contract links live in docs/architecture/README.md (thin README delegates there)
        architecture_index_text = (
            REPO_ROOT / "docs" / "architecture" / "README.md"
        ).read_text(encoding="utf-8")

        for link in ARCHITECTURE_CORE_CONTRACT_LINKS:
            with self.subTest(doc="architecture", link=link):
                self.assertIn(link, architecture_index_text)

        for link in ARCHITECTURE_TEMPLATE_LINKS:
            with self.subTest(doc="architecture", link=link):
                self.assertIn(link, architecture_index_text)

        # History/archive links live in architecture index, not root README
        self.assertIn("[docs/history/index.md](../history/index.md)", architecture_index_text)
        self.assertIn("[docs/archive/README.md](../archive/README.md)", architecture_index_text)

    def test_agents_doc_declares_template_backend_aware_rules(self) -> None:
        text = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")

        self.assertIn("所有正式操作必须从 `agentplane ...` 进入", text)
        self.assertIn("Windows 默认 `pwsh`", text)
        self.assertIn("`wsl.exe -e <程序>`", text)
        self.assertIn("远程 Linux 走 `agentplane infra remote bash`", text)
        self.assertNotIn("retained as the WSL/Linux backend path during migration", text)

    def test_app_repository_standard_defines_template_boundary(self) -> None:
        text = (REPO_ROOT / "docs" / "reference" / "app-repository-standard.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("应用仓库只负责代码、构建资产、合同与非敏感模板", text)
        self.assertIn("控制面模板仓库负责 bootstrap、正式执行、验证、回写与对外 runbook", text)
        self.assertIn("默认采用 host-entry-first, backend-aware", text)
        self.assertIn("不要再维护第二控制面", text)
        self.assertIn("`deploy/agentplane/contract.yaml`", text)
        self.assertNotIn("WSL-first", text)

    def test_domain_onboarding_and_execution_flow_use_template_placeholders(self) -> None:
        onboarding_text = (
            REPO_ROOT / "docs" / "runbooks" / "control-plane-domain-onboarding.md"
        ).read_text(encoding="utf-8")
        flow_text = (
            REPO_ROOT / "docs" / "runbooks" / "control-plane-agent-execution-flow.md"
        ).read_text(encoding="utf-8")

        self.assertIn("bootstrap inspect-local --repo-root <repo-root>", onboarding_text)
        self.assertIn("infra inventory <target> --repo-root <repo-root>", onboarding_text)
        self.assertIn("只写 formal CLI、skill、runbook 与测试合同", onboarding_text)

        self.assertIn("bootstrap inspect-local --repo-root <repo-root>", flow_text)
        self.assertIn("bootstrap doctor --repo-root <repo-root>", flow_text)
        self.assertIn("Windows / Linux / macOS 只在 `resolver / backend` 层分叉", flow_text)
        self.assertIn("plan -> apply -> verify -> ledger -> inventory -> doc-sync", flow_text)
        self.assertIn("`pwsh`", flow_text)
        self.assertNotIn("确认当前在 WSL 环境执行", flow_text)

    def test_core_contract_docs_use_template_placeholders(self) -> None:
        control_plane = (REPO_ROOT / "docs" / "architecture" / "control-plane.md").read_text(
            encoding="utf-8"
        )
        collaboration = (
            REPO_ROOT / "docs" / "architecture" / "agentplane-app-collaboration.md"
        ).read_text(encoding="utf-8")
        governance = (REPO_ROOT / "docs" / "architecture" / "linux-governance.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("infra inventory <target> --repo-root <repo-root>", control_plane)
        self.assertIn("service search --target <target> --repo-root <repo-root>", control_plane)
        self.assertIn(
            "ingress publish plan --target <target> --config-file <config-file> --cloudflare-env-file <cloudflare-env-file> --repo-root <repo-root>",
            control_plane,
        )
        self.assertIn(
            "app delivery validate-contract --target <target> --app <app> --repo-root <repo-root>",
            collaboration,
        )
        self.assertIn(
            "app delivery deploy --target <target> --app <app> --repo-root <repo-root> --image-ref <image:tag> --dry-run",
            collaboration,
        )
        self.assertIn("本页只定义 Linux / WSL backend 约束，不改变宿主入口选择。", governance)
        self.assertIn("[bootstrap-secrets.md](../runbooks/bootstrap-secrets.md)", governance)
        self.assertIn("`infra automation` 管“何时执行、执行什么周期任务”", control_plane)
        self.assertIn(
            "projection verification run --target <target> --profile <profile> --repo-root <repo-root>",
            control_plane,
        )
        self.assertIn(
            "projection ledger refresh --target <target> --repo-root <repo-root> --write",
            control_plane,
        )

# ======================================================================
# From: test_truth_path_policy.py
# ======================================================================

class TruthPathPolicyTests(unittest.TestCase):
    def test_truth_contract_rejects_windows_drive_paths(self) -> None:
        self.assertTrue(is_host_specific_path("D:/Projects/AgentPlane"))

    def test_truth_contract_rejects_unc_paths(self) -> None:
        self.assertTrue(is_host_specific_path(r"\\wsl.localhost\Ubuntu\root\work\sub2api"))

    def test_truth_contract_allows_canonical_refs(self) -> None:
        self.assertFalse(is_host_specific_path("apps/sub2api/contracts/prod0-main"))
        self.assertEqual("apps/sub2api/contracts/prod0-main", assert_canonical_ref("apps/sub2api/contracts/prod0-main"))

    def test_write_app_catalog_persists_canonical_refs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            entry = AppCatalogEntry(
                app="sub2api",
                repo_name="sub2api",
                repo_root=Path("<app-repo-root>"),
                service_key="sub2api",
                contracts={
                    "wsl": "deploy/agentplane/contract.wsl.yaml",
                    "prod0-main": "deploy/agentplane/contract.yaml",
                },
            )

            catalog_file = write_app_catalog(repo_root, [entry])
            payload = json.loads(catalog_file.read_text(encoding="utf-8"))

            self.assertEqual(
                {
                    "apps": [
                        {
                            "app": "sub2api",
                            "repo_name": "sub2api",
                            "repo_ref": "apps/sub2api",
                            "service_key": "sub2api",
                            "contracts": {
                                "prod0-main": "apps/sub2api/contracts/prod0-main",
                                "wsl": "apps/sub2api/contracts/wsl",
                            },
                        }
                    ]
                },
                payload,
            )

    def test_load_app_catalog_resolves_runtime_path_from_canonical_refs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_root = root / "AgentPlane"
            app_root = root / "sub2api"
            (repo_root / "inventory" / "apps").mkdir(parents=True, exist_ok=True)
            app_root.mkdir(parents=True, exist_ok=True)
            (repo_root / "inventory" / "apps" / "catalog.json").write_text(
                json.dumps(
                    {
                        "apps": [
                            {
                                "app": "sub2api",
                                "repo_name": "sub2api",
                                "repo_ref": "apps/sub2api",
                                "service_key": "sub2api",
                                "contracts": {"prod0-main": "apps/sub2api/contracts/prod0-main"},
                            }
                        ]
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            entries = load_app_catalog(repo_root)

            self.assertEqual(1, len(entries))
            self.assertEqual(app_root.resolve(), entries[0].repo_root.resolve())
            self.assertEqual("deploy/agentplane/contract.yaml", entries[0].contracts["prod0-main"])

# ======================================================================
# From: test_commit_message_policy.py
# ======================================================================

class CommitMessagePolicyTests(unittest.TestCase):
    def test_accepts_conventional_commit_subject(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "agentplane.domain.repository.commit_message",
                "--message",
                "docs(standards): add project health guardrails",
            ],
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual("", result.stderr)
        self.assertEqual(0, result.returncode)

    def test_rejects_non_conventional_subject(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "agentplane.domain.repository.commit_message",
                "--message",
                "Update stuff",
            ],
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("Invalid commit message", result.stdout)

    def test_validates_commit_range(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init"], cwd=root, text=True, capture_output=True, check=True)
            subprocess.run(["git", "config", "user.name", "Codex"], cwd=root, text=True, capture_output=True, check=True)
            subprocess.run(
                ["git", "config", "user.email", "codex@example.com"],
                cwd=root,
                text=True,
                capture_output=True,
                check=True,
            )
            (root / "README.md").write_text("demo\n", encoding="utf-8")
            subprocess.run(["git", "add", "README.md"], cwd=root, text=True, capture_output=True, check=True)
            subprocess.run(
                ["git", "commit", "-m", "docs(repo): add readme"],
                cwd=root,
                text=True,
                capture_output=True,
                check=True,
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "agentplane.domain.repository.commit_message",
                    "--range",
                    "HEAD",
                ],
                cwd=root,
                env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[2])},
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(0, result.returncode, msg=result.stderr)

# ======================================================================
# From: test_cleanup.py
# ======================================================================

class CleanupTests(unittest.TestCase):
    def test_cleanup_plan_lists_whitelisted_wsl_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".playwright-cli").mkdir(parents=True)
            (root / "tmp").mkdir(parents=True)
            (root / "tests" / "__pycache__").mkdir(parents=True)
            (root / ".worktrees" / "demo" / "tmp").mkdir(parents=True)
            ((root / ".worktrees" / "demo" / "tmp" / "artifact.tar")).write_text("x", encoding="utf-8")

            result = build_cleanup_plan(root, "wsl")
            paths = {item["path"] for item in result["actions"]}

            self.assertIn(str(root / ".playwright-cli"), paths)
            self.assertIn(str(root / "tmp"), paths)
            self.assertIn(str(root / "tests" / "__pycache__"), paths)
            self.assertIn(str(root / ".worktrees" / "demo" / "tmp"), paths)

    def test_cleanup_apply_removes_whitelisted_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / ".playwright-cli"
            target.mkdir(parents=True)
            (target / "page.yml").write_text("snapshot", encoding="utf-8")

            result = apply_cleanup_plan(root, "wsl")

            self.assertFalse(target.exists(), msg=json.dumps(result, ensure_ascii=False))
            self.assertEqual(1, result["removed_count"])
            self.assertEqual(str(target), result["removed"][0]["path"])

    def test_cleanup_apply_skips_active_virtualenv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            active_python = root / ".venv" / "bin" / "python"
            active_python.parent.mkdir(parents=True)
            active_python.write_text("", encoding="utf-8")

            with patch("agentplane.cli.cleanup.sys.executable", str(active_python)):
                result = apply_cleanup_plan(root, "wsl")

            self.assertTrue((root / ".venv").exists(), msg=json.dumps(result, ensure_ascii=False))
            self.assertEqual(0, result["removed_count"])
            self.assertEqual(1, result["skipped_count"])
            self.assertEqual(str(root / ".venv"), result["skipped"][0]["path"])

# ======================================================================
# From: test_pyproject_config.py
# ======================================================================

REPO_ROOT = Path(__file__).resolve().parents[2]

class PyprojectConfigTests(unittest.TestCase):
    def test_project_declares_build_system_for_local_package(self) -> None:
        payload = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

        self.assertIn("build-system", payload)
        self.assertEqual("hatchling.build", payload["build-system"]["build-backend"])
        self.assertIn("tool", payload)
        self.assertEqual("agentplane-cli", payload["project"]["name"])
        self.assertEqual("agentplane.cli.app:main", payload["project"]["scripts"]["agentplane"])
        self.assertEqual(["agentplane"], payload["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"])
