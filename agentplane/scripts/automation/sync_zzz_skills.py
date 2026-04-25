from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

IGNORED_NAMES = {".DS_Store", "Thumbs.db", "__pycache__"}
DEFAULT_ALLOWED_ROOT_FILES = ("README.md", ".gitignore")


def _run_git(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


def _git_output(args: list[str], *, cwd: Path) -> str:
    result = _run_git(args, cwd=cwd)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or f"git {' '.join(args)} failed")
    return result.stdout.strip()


def _failing_precheck(reason: str, *, skills: list[str] | None = None) -> dict[str, Any]:
    return {
        "status": "failed_precheck",
        "reason": reason,
        "skills": skills or [],
    }


def _ignored_copy(path: str, names: list[str]) -> set[str]:
    ignored: set[str] = set()
    for name in names:
        if name in IGNORED_NAMES:
            ignored.add(name)
    return ignored


def _listed_skill_dirs(source_root: Path) -> list[Path]:
    return sorted(path for path in source_root.iterdir() if path.is_dir() and path.name.startswith("zzz-"))


def _root_unknown_entries(target_repo: Path, allowed_root_files: tuple[str, ...]) -> list[str]:
    unknown: list[str] = []
    allowed = set(allowed_root_files)
    for item in sorted(target_repo.iterdir(), key=lambda path: path.name):
        if item.name == ".git":
            continue
        if item.is_dir() and item.name.startswith("zzz-"):
            continue
        if item.is_file() and item.name in allowed:
            continue
        unknown.append(item.name)
    return unknown


def _mirror_skills(source_skills: list[Path], target_repo: Path) -> tuple[list[str], list[str], list[str]]:
    copied: list[str] = []
    removed: list[str] = []
    all_skills = [path.name for path in source_skills]

    existing = sorted(path for path in target_repo.iterdir() if path.is_dir() and path.name.startswith("zzz-"))
    source_names = {path.name for path in source_skills}
    for path in existing:
        if path.name not in source_names:
            shutil.rmtree(path)
            removed.append(path.name)

    for skill_dir in source_skills:
        destination = target_repo / skill_dir.name
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(skill_dir, destination, ignore=_ignored_copy)
        copied.append(skill_dir.name)

    return all_skills, copied, removed


def _ensure_origin_not_ahead(target_repo: Path, branch: str) -> str | None:
    remote_name = f"origin/{branch}"
    fetched = _run_git(["fetch", "origin", branch], cwd=target_repo)
    if fetched.returncode != 0:
        return fetched.stderr.strip() or fetched.stdout.strip() or f"failed to fetch {remote_name}"

    local_head = _git_output(["rev-parse", branch], cwd=target_repo)
    remote_head = _git_output(["rev-parse", remote_name], cwd=target_repo)
    if local_head != remote_head:
        return f"local {branch} is not aligned with {remote_name}"
    return None


def run_sync(
    *,
    source_root: Path,
    target_repo: Path,
    branch: str = "main",
    allowed_root_files: tuple[str, ...] = DEFAULT_ALLOWED_ROOT_FILES,
) -> dict[str, Any]:
    resolved_source = source_root.resolve()
    resolved_target = target_repo.resolve()

    if not resolved_source.is_dir():
        return _failing_precheck(f"source root does not exist: {resolved_source}")
    if not (resolved_target / ".git").exists():
        return _failing_precheck(f"target repo is not a git repository: {resolved_target}")

    skills = [path.name for path in _listed_skill_dirs(resolved_source)]

    current_branch = _run_git(["branch", "--show-current"], cwd=resolved_target)
    branch_name = current_branch.stdout.strip() if current_branch.returncode == 0 else ""
    if branch_name != branch:
        return _failing_precheck(f"target repo must be on branch {branch}, got {branch_name or 'unknown'}", skills=skills)

    status = _run_git(["status", "--short"], cwd=resolved_target)
    if status.returncode != 0:
        return _failing_precheck(status.stderr.strip() or "failed to read git status", skills=skills)
    if status.stdout.strip():
        return _failing_precheck(f"target repo has dirty worktree: {status.stdout.strip()}", skills=skills)

    unknown_entries = _root_unknown_entries(resolved_target, allowed_root_files)
    if unknown_entries:
        return _failing_precheck(
            "target repo contains unsupported root entries: " + ", ".join(unknown_entries),
            skills=skills,
        )

    remote_drift = _ensure_origin_not_ahead(resolved_target, branch)
    if remote_drift is not None:
        return _failing_precheck(remote_drift, skills=skills)

    try:
        listed, copied, removed = _mirror_skills(_listed_skill_dirs(resolved_source), resolved_target)
    except Exception as exc:  # pragma: no cover - defensive wrapper
        return {
            "status": "failed_runtime",
            "reason": str(exc),
            "skills": skills,
        }

    final_status = _run_git(["status", "--short"], cwd=resolved_target)
    if final_status.returncode != 0:
        return {
            "status": "failed_runtime",
            "reason": final_status.stderr.strip() or "failed to inspect git status after sync",
            "skills": listed,
        }
    if not final_status.stdout.strip():
        return {
            "status": "ok_no_changes",
            "skills": listed,
            "copied": copied,
            "removed": removed,
        }

    for command in (
        ["add", "-A"],
        ["commit", "-m", "chore: sync zzz skills"],
        ["push", "origin", branch],
    ):
        result = _run_git(command, cwd=resolved_target)
        if result.returncode != 0:
            return {
                "status": "failed_runtime",
                "reason": result.stderr.strip() or result.stdout.strip() or f"git {' '.join(command)} failed",
                "skills": listed,
                "copied": copied,
                "removed": removed,
            }

    return {
        "status": "ok_pushed",
        "skills": listed,
        "copied": copied,
        "removed": removed,
    }
