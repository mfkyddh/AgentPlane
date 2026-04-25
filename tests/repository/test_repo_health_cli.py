import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "agentplane.cli", *args],
        cwd=cwd or REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


class RepoHealthCliTests(unittest.TestCase):
    def test_repo_health_check_can_run_lightweight_checks(self) -> None:
        result = run_cli(
            "repo",
            "health-check",
            "--repo-root",
            str(REPO_ROOT),
            "--skip-ruff",
            "--skip-tests",
        )

        self.assertEqual(0, result.returncode, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(["cli-help", "secret-scan", "docs-sanity"], [check["name"] for check in payload["checks"]])

    def test_docs_sanity_reports_retired_entrypoints(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            (root / "docs" / "bad.md").write_text("Use `agentplane host audit`.\n", encoding="utf-8")

            result = run_cli("repo", "docs-sanity", "--repo-root", str(root))

        self.assertEqual(1, result.returncode)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["ok"])
        self.assertEqual("retired-host-entrypoint", payload["issues"][0]["kind"])

    def test_secret_scan_reports_git_visible_secret_material(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init"], cwd=root, text=True, capture_output=True, check=True)
            token = "sk-" + "thisvalueislongenoughtolooksecret"
            (root / "app.env").write_text(f"OPENAI_API_KEY={token}\n", encoding="utf-8")

            result = run_cli("repo", "secret-scan", "--repo-root", str(root))

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

            result = run_cli("repo", "secret-scan", "--repo-root", str(root))

        self.assertEqual(0, result.returncode, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])

    def test_release_check_reports_dirty_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init"], cwd=root, text=True, capture_output=True, check=True)
            (root / "README.md").write_text("dirty\n", encoding="utf-8")

            result = run_cli(
                "repo",
                "release-check",
                "--repo-root",
                str(root),
            )

        self.assertEqual(1, result.returncode)
        payload = json.loads(result.stdout)
        git_check = next(check for check in payload["checks"] if check["name"] == "git-clean")
        self.assertFalse(git_check["ok"])


if __name__ == "__main__":
    unittest.main()
