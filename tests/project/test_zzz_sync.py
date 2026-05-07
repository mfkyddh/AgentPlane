from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


def git(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *command],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


def init_git_repo(path: Path) -> None:
    result = git(["init", "--initial-branch=main"], cwd=path)
    if result.returncode != 0:
        git(["init"], cwd=path)
        git(["checkout", "-b", "main"], cwd=path)
    git(["config", "user.email", "test@example.com"], cwd=path)
    git(["config", "user.name", "Test"], cwd=path)
    git(["commit", "--allow-empty", "-m", "chore: init"], cwd=path)


def init_target_repo(path: Path, remote_path: Path) -> None:
    git(["init", "--bare", str(remote_path)], cwd=path)
    init_git_repo(path)
    git(["remote", "add", "origin", str(remote_path)], cwd=path)
    git(["push", "origin", "main"], cwd=path)


class ZzzSkillsSyncTests(unittest.TestCase):
    def test_sync_reports_no_changes_when_target_matches_source(self) -> None:
        from agentplane.scripts.automation.sync_zzz_skills import run_sync

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_root = root / "source"
            target_repo = root / "target"
            remote_repo = root / "remote.git"
            source_root.mkdir(parents=True)
            target_repo.mkdir(parents=True)
            init_target_repo(target_repo, remote_repo)

            skill_dir = source_root / "zzz-alpha"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text("alpha\n", encoding="utf-8")
            mirrored = target_repo / "zzz-alpha"
            mirrored.mkdir()
            (mirrored / "SKILL.md").write_text("alpha\n", encoding="utf-8")
            git(["add", "zzz-alpha/SKILL.md"], cwd=target_repo)
            git(["commit", "-m", "chore: seed"], cwd=target_repo)
            git(["push", "origin", "main"], cwd=target_repo)

            payload = run_sync(source_root=source_root, target_repo=target_repo)

            self.assertEqual("ok_no_changes", payload["status"], msg=f"reason: {payload.get('reason', 'n/a')}")
            self.assertEqual(["zzz-alpha"], payload["skills"])

    def test_sync_removes_stale_zzz_directories(self) -> None:
        from agentplane.scripts.automation.sync_zzz_skills import run_sync

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_root = root / "source"
            target_repo = root / "target"
            remote_repo = root / "remote.git"
            source_root.mkdir(parents=True)
            target_repo.mkdir(parents=True)
            init_target_repo(target_repo, remote_repo)

            skill_dir = source_root / "zzz-alpha"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text("alpha\n", encoding="utf-8")
            stale_dir = target_repo / "zzz-stale"
            stale_dir.mkdir()
            (stale_dir / "SKILL.md").write_text("stale\n", encoding="utf-8")
            git(["add", "zzz-stale/SKILL.md"], cwd=target_repo)
            git(["commit", "-m", "chore: add stale"], cwd=target_repo)
            git(["push", "origin", "main"], cwd=target_repo)

            payload = run_sync(source_root=source_root, target_repo=target_repo)

            self.assertEqual("ok_pushed", payload["status"], msg=f"reason: {payload.get('reason', 'n/a')}")
            self.assertFalse(stale_dir.exists())
            self.assertTrue((target_repo / "zzz-alpha" / "SKILL.md").exists())

    def test_sync_rejects_dirty_git_worktree(self) -> None:
        from agentplane.scripts.automation.sync_zzz_skills import run_sync

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_root = root / "source"
            target_repo = root / "target"
            remote_repo = root / "remote.git"
            source_root.mkdir(parents=True)
            target_repo.mkdir(parents=True)
            init_target_repo(target_repo, remote_repo)

            skill_dir = source_root / "zzz-alpha"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text("alpha\n", encoding="utf-8")
            (target_repo / "README.md").write_text("dirty\n", encoding="utf-8")

            payload = run_sync(source_root=source_root, target_repo=target_repo)

            self.assertEqual("failed_precheck", payload["status"])
            self.assertIn("dirty", payload["reason"])

    def test_sync_rejects_unknown_root_files_outside_allowlist(self) -> None:
        from agentplane.scripts.automation.sync_zzz_skills import run_sync

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_root = root / "source"
            target_repo = root / "target"
            remote_repo = root / "remote.git"
            source_root.mkdir(parents=True)
            target_repo.mkdir(parents=True)
            init_target_repo(target_repo, remote_repo)

            skill_dir = source_root / "zzz-alpha"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text("alpha\n", encoding="utf-8")
            (target_repo / "EXTRA.md").write_text("unexpected\n", encoding="utf-8")
            git(["add", "EXTRA.md"], cwd=target_repo)
            git(["commit", "-m", "chore: add extra"], cwd=target_repo)
            git(["push", "origin", "main"], cwd=target_repo)

            payload = run_sync(source_root=source_root, target_repo=target_repo)

            self.assertEqual("failed_precheck", payload["status"])
            self.assertIn("EXTRA.md", payload["reason"])
