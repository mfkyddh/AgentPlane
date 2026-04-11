import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agentplane.cli.cleanup import apply_cleanup_plan, build_cleanup_plan


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


if __name__ == "__main__":
    unittest.main()
