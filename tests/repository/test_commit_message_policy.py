import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class CommitMessagePolicyTests(unittest.TestCase):
    def test_accepts_conventional_commit_subject(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "scripts/check_commit_message.py",
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
                "scripts/check_commit_message.py",
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
                    str(Path(__file__).resolve().parents[2] / "scripts" / "check_commit_message.py"),
                    "--range",
                    "HEAD",
                ],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(0, result.returncode, msg=result.stderr)


if __name__ == "__main__":
    unittest.main()
