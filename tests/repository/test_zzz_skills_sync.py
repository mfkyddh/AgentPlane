import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


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
        raise AssertionError(result.stderr)
    for key, value in (("user.name", "Test User"), ("user.email", "test@example.com")):
        configured = git(["config", key, value], cwd=path)
        if configured.returncode != 0:
            raise AssertionError(configured.stderr)


def init_target_repo(path: Path, remote_path: Path) -> None:
    remote_created = git(["init", "--bare", str(remote_path)], cwd=path.parent)
    if remote_created.returncode != 0:
        raise AssertionError(remote_created.stderr)

    init_git_repo(path)
    added = git(["remote", "add", "origin", str(remote_path)], cwd=path)
    if added.returncode != 0:
        raise AssertionError(added.stderr)
    (path / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
    committed = git(["add", ".gitignore"], cwd=path)
    if committed.returncode != 0:
        raise AssertionError(committed.stderr)
    committed = git(["commit", "-m", "chore: init"], cwd=path)
    if committed.returncode != 0:
        raise AssertionError(committed.stderr)
    pushed = git(["push", "-u", "origin", "main"], cwd=path)
    if pushed.returncode != 0:
        raise AssertionError(pushed.stderr)


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

            self.assertEqual("ok_no_changes", payload["status"])
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

            self.assertEqual("ok_pushed", payload["status"])
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


if __name__ == "__main__":
    unittest.main()

