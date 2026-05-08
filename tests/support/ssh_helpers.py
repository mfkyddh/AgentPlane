"""SSH-related test helpers for infra remote/local tests."""

from __future__ import annotations

import os
from pathlib import Path

from tests.support.paths import REPO_ROOT


def common_repo_root(repo_root: Path) -> Path:
    """Resolve the real git repo root, handling worktrees."""
    git_entry = repo_root / ".git"
    if git_entry.is_dir():
        return repo_root
    if git_entry.is_file():
        content = git_entry.read_text(encoding="utf-8").strip()
        if content.startswith("gitdir:"):
            git_dir = Path(content.split(":", 1)[1].strip())
            if not git_dir.is_absolute():
                git_dir = (repo_root / git_dir).resolve()
            if len(git_dir.parts) >= 3 and git_dir.parent.name == "worktrees" and git_dir.parent.parent.name == ".git":
                return git_dir.parents[2]
    return repo_root


MAIN_REPO_ROOT = common_repo_root(REPO_ROOT)


def expected_ssh_stdin_argv(config_path: Path, remote_command: str) -> list[str]:
    """Build the expected SSH argv for stdin-based remote execution."""
    if os.name == "nt":
        drive = config_path.drive.rstrip(":").lower()
        tail = (
            config_path.as_posix().split(":", 1)[1].lstrip("/")
            if config_path.drive
            else config_path.as_posix().lstrip("/")
        )
        rendered_config = f"/mnt/{drive}/{tail}" if drive else config_path.as_posix()
        return ["wsl.exe", "-e", "ssh", "-T", "-F", rendered_config, "root@prod0-main", remote_command]
    return ["ssh", "-T", "-F", str(config_path), "root@prod0-main", remote_command]
