import subprocess
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "agentplane.cli", *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


class AppLifecycleCliContractsTests(unittest.TestCase):
    def test_onboard_help_exposes_single_formal_entry_contract(self) -> None:
        result = run_cli("app", "delivery", "onboard", "--help")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("single formal entry", result.stdout)
        self.assertIn("--dry-run", result.stdout)
        self.assertIn("--write", result.stdout)

    def test_offboard_help_exposes_single_formal_entry_contract(self) -> None:
        result = run_cli("app", "delivery", "offboard", "--help")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("single formal entry", result.stdout)
        self.assertIn("--dry-run", result.stdout)
        self.assertIn("--write", result.stdout)

    def test_onboard_requires_dry_run_or_write(self) -> None:
        result = run_cli("app", "delivery", "onboard", "--target", "wsl", "--app", "sub2api")
        self.assertEqual(result.returncode, 2)
        self.assertIn("--dry-run", result.stderr)
        self.assertIn("--write", result.stderr)

    def test_onboard_rejects_dry_run_plus_write(self) -> None:
        result = run_cli(
            "app",
            "delivery",
            "onboard",
            "--target",
            "wsl",
            "--app",
            "sub2api",
            "--dry-run",
            "--write",
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("--dry-run", result.stderr)
        self.assertIn("--write", result.stderr)

    def test_offboard_requires_dry_run_or_write(self) -> None:
        result = run_cli("app", "delivery", "offboard", "--target", "wsl", "--app", "sub2api")
        self.assertEqual(result.returncode, 2)
        self.assertIn("--dry-run", result.stderr)
        self.assertIn("--write", result.stderr)

    def test_offboard_rejects_dry_run_plus_write(self) -> None:
        result = run_cli(
            "app",
            "delivery",
            "offboard",
            "--target",
            "wsl",
            "--app",
            "sub2api",
            "--dry-run",
            "--write",
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("--dry-run", result.stderr)
        self.assertIn("--write", result.stderr)


if __name__ == "__main__":
    unittest.main()


