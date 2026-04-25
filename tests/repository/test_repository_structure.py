import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

ALLOWED_TRACKED_TOP_LEVELS = {
    ".agents",
    ".codex",
    ".editorconfig",
    ".gitattributes",
    ".githooks",
    ".github",
    ".gitignore",
    ".secret-scan-allowlist",
    "AGENTS.md",
    "CODE_OF_CONDUCT.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "README.md",
    "SECURITY.md",
    "SUPPORT.md",
    "agentplane",
    "docs",
    "infra",
    "inventory",
    "plugins",
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
                with self.subTest(path=path.relative_to(REPO_ROOT), marker=marker):
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


if __name__ == "__main__":
    unittest.main()
