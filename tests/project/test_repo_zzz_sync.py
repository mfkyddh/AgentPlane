from __future__ import annotations

import re
import subprocess
import tempfile
import unittest
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e


def _listed_help_commands(help_text: str) -> set[str]:
    return set(re.findall(r"(?m)^\s{2,}([a-z][a-z0-9-]*)\b(?:\s{2,}|\s*$)", help_text))


def _listed_targets(help_text: str) -> set[str]:
    targets: set[str] = set()
    for choice_group in re.findall(r"\{([^}]+)\}", help_text):
        for token in choice_group.split(","):
            candidate = token.strip()
            if candidate in {"wsl", "prod0-main", "prod0-main"}:
                targets.add(candidate)
    return targets


def _assert_help_commands(
    testcase: unittest.TestCase,
    help_text: str,
    *,
    expected: set[str] | None = None,
    absent: set[str] | None = None,
) -> set[str]:
    commands = _listed_help_commands(help_text)
    if expected is not None:
        testcase.assertTrue(expected.issubset(commands), msg=f"missing commands: {sorted(expected - commands)}")
    if absent is not None:
        testcase.assertTrue(absent.isdisjoint(commands), msg=f"unexpected commands: {sorted(absent & commands)}")
    return commands


def _write_fake_onepanel_router(source_root: Path, *, include_extra_route: bool = False) -> None:
    router_root = source_root / "agent" / "router"
    router_root.mkdir(parents=True, exist_ok=True)
    extra_route = '\n\t\tbaRouter.POST("/inspect", baseApi.Inspect)' if include_extra_route else ""
    (router_root / "ro_container.go").write_text(
        f"""package router

func (s *ContainerRouter) InitRouter(Router *gin.RouterGroup) {{
\tbaRouter := Router.Group("containers")
\tbaseApi := v2.ApiGroupApp.BaseApi
\t{{
\t\tbaRouter.POST("/search", baseApi.SearchContainer)
\t\tbaRouter.GET("/status", baseApi.LoadContainerStatus){extra_route}
\t}}
}}
""",
        encoding="utf-8",
    )
    (router_root / "ro_website.go").write_text(
        """package router

func (a *WebsiteRouter) InitRouter(Router *gin.RouterGroup) {
\twebsiteRouter := Router.Group("websites")
\tbaseApi := v2.ApiGroupApp.BaseApi
\t{
\t\twebsiteRouter.POST("", baseApi.CreateWebsite)
\t\twebsiteRouter.GET("/:id", baseApi.GetWebsite)
\t}
}
""",
        encoding="utf-8",
    )


# ======================================================================
# From: test_zzz_skills_sync.py
# ======================================================================


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
