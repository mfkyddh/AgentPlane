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
}
FORBIDDEN_TRACKED_TOP_LEVELS = {"scripts", "ops", "tools"}
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

        self.assertIn("infra bootstrap doctor", text)

    def test_readme_describes_template_truth_and_runtime_model(self) -> None:
        text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("AgentPlane", text)
        self.assertIn("agentplane", text)

    def test_entry_indexes_link_template_contracts(self) -> None:
        # Core contract links live in docs/architecture/README.md (thin README delegates there)
        architecture_index_text = (REPO_ROOT / "docs" / "archive" / "architecture" / "README.md").read_text(encoding="utf-8")

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
        text = (REPO_ROOT / "docs" / "archive" / "reference" / "app-repository-standard.md").read_text(encoding="utf-8")

        self.assertIn("应用仓库只负责代码、构建资产、合同与非敏感模板", text)
        self.assertIn("控制面模板仓库负责 bootstrap、正式执行、验证、回写与对外 runbook", text)
        self.assertIn("默认采用 host-entry-first, backend-aware", text)
        self.assertIn("不要再维护第二控制面", text)
        self.assertIn("`deploy/agentplane/contract.yaml`", text)
        self.assertNotIn("WSL-first", text)

    def test_domain_onboarding_and_execution_flow_use_template_placeholders(self) -> None:
        onboarding_text = (REPO_ROOT / "docs" / "archive" / "runbooks" / "control-plane-domain-onboarding.md").read_text(
            encoding="utf-8"
        )
        flow_text = (REPO_ROOT / "docs" / "archive" / "runbooks" / "control-plane-agent-execution-flow.md").read_text(
            encoding="utf-8"
        )

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
        control_plane = (REPO_ROOT / "docs" / "archive" / "architecture" / "control-plane.md").read_text(encoding="utf-8")
        collaboration = (REPO_ROOT / "docs" / "archive" / "architecture" / "agentplane-app-collaboration.md").read_text(
            encoding="utf-8"
        )
        governance = (REPO_ROOT / "docs" / "archive" / "architecture" / "linux-governance.md").read_text(encoding="utf-8")

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
                            "repo_root": "<app-repo-root>",
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
                "agentplane.domain.project.commit_message",
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
                "agentplane.domain.project.commit_message",
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
            subprocess.run(
                ["git", "config", "user.name", "Codex"], cwd=root, text=True, capture_output=True, check=True
            )
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
                    "agentplane.domain.project.commit_message",
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
            (root / ".worktrees" / "demo" / "tmp" / "artifact.tar").write_text("x", encoding="utf-8")

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

            with patch("agentplane.domain.infra.cleanup.sys.executable", str(active_python)):
                result = apply_cleanup_plan(root, "wsl")

            self.assertTrue((root / ".venv").exists(), msg=json.dumps(result, ensure_ascii=False))
            self.assertEqual(0, result["removed_count"])
            self.assertEqual(1, result["skipped_count"])
            self.assertEqual(str(root / ".venv"), result["skipped"][0]["path"])
