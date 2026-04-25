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

    def test_docs_sanity_reports_isolated_active_docs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("# Entry\n", encoding="utf-8")
            (root / "docs").mkdir()
            (root / "docs" / "orphan.md").write_text("# Orphan\n", encoding="utf-8")

            result = run_cli("repo", "docs-sanity", "--repo-root", str(root))

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

            result = run_cli("repo", "docs-sanity", "--repo-root", str(root))

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

            result = run_cli("repo", "docs-sanity", "--repo-root", str(root))

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

            result = run_cli("repo", "docs-sanity", "--repo-root", str(root))

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

            result = run_cli("repo", "docs-sanity", "--repo-root", str(root))

        payload = json.loads(result.stdout)
        # Missing conclusion is a warning, not an error
        self.assertTrue(payload["ok"])
        kinds = [i["kind"] for i in payload["issues"]]
        self.assertIn("missing-conclusion", kinds)

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
