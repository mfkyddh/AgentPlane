from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Any

WSL_TEMP_PATTERNS = (
    ".playwright-cli",
    "tmp",
    ".venv",
    ".pytest_cache",
    "tests/__pycache__",
    ".worktrees/*/.venv",
    ".worktrees/*/.pytest_cache",
    ".worktrees/*/tmp",
    ".worktrees/*/tests/__pycache__",
    ".worktrees/*/tmp/*.tar",
)
SUPPORTED_CLEANUP_TARGETS = ("wsl", "prod0-main")


def _within_repo_root(path: Path, repo_root: Path) -> bool:
    try:
        path.resolve().relative_to(repo_root.resolve())
        return True
    except ValueError:
        return False


def _path_kind(path: Path) -> str:
    if path.is_dir():
        return "dir"
    if path.is_file():
        return "file"
    return "missing"


def _dedupe_nested_paths(paths: list[Path]) -> list[Path]:
    deduped: list[Path] = []
    for path in sorted(paths, key=lambda item: (len(item.parts), str(item))):
        if any(parent == path or parent in path.parents for parent in deduped):
            continue
        deduped.append(path)
    return deduped


def _active_virtualenv_roots(repo_root: Path) -> set[Path]:
    roots: set[Path] = set()
    executable = Path(sys.executable)
    if executable.exists():
        for parent in executable.parents:
            if parent.name == ".venv" and _within_repo_root(parent, repo_root):
                roots.add(parent)
                break
    virtual_env = os.environ.get("VIRTUAL_ENV")
    if virtual_env:
        path = Path(virtual_env)
        if path.exists() and path.name == ".venv" and _within_repo_root(path, repo_root):
            roots.add(path)
    return roots


def _wsl_temp_cleanup_actions(repo_root: Path) -> list[dict[str, str]]:
    matches: list[Path] = []
    for pattern in WSL_TEMP_PATTERNS:
        matches.extend(path for path in repo_root.glob(pattern) if path.exists())

    actions: list[dict[str, str]] = []
    for path in _dedupe_nested_paths(matches):
        if not _within_repo_root(path, repo_root):
            continue
        actions.append(
            {
                "type": "remove_temp_path",
                "path": str(path),
                "kind": _path_kind(path),
                "reason": "删除仓库白名单内的本地临时产物与缓存。",
            }
        )
    return actions


def build_cleanup_plan(repo_root: Path, target_env: str) -> dict[str, Any]:
    resolved_root = repo_root.resolve()
    actions: list[dict[str, str]] = []

    if target_env == "wsl":
        actions.extend(_wsl_temp_cleanup_actions(resolved_root))
        compose_root = resolved_root / "infra" / "compose"
        if compose_root.is_dir():
            for service_dir in sorted(path for path in compose_root.iterdir() if path.is_dir()):
                legacy_compose = service_dir / "docker-compose.yml"
                legacy_env = service_dir / ".env"
                if legacy_compose.exists():
                    actions.append(
                        {
                            "type": "remove_legacy_compose",
                            "path": str(legacy_compose),
                            "reason": "使用 docker-compose.wsl.yml / docker-compose.prod0.yml 作为规范入口。",
                        }
                    )
                if legacy_env.exists():
                    actions.append(
                        {
                            "type": "remove_legacy_env",
                            "path": str(legacy_env),
                            "reason": "替换为环境专用 env 文件。",
                        }
                    )
    elif target_env == "prod0-main":
        actions.extend(
            [
                {
                    "type": "normalize_sub2api_paths",
                    "path": "/data/sub2api",
                    "reason": "将 sub2api 的数据与配置目录收口到 /data/sub2api。",
                },
            ]
        )
    else:
        raise ValueError(f"Unsupported cleanup env: {target_env}")

    return {
        "command": "cleanup plan",
        "env": target_env,
        "repo_root": str(resolved_root),
        "actions": actions,
        "action_count": len(actions),
    }


def _remove_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
        return
    path.unlink()


def apply_cleanup_plan(repo_root: Path, target_env: str) -> dict[str, Any]:
    resolved_root = repo_root.resolve()
    plan = build_cleanup_plan(resolved_root, target_env)
    removed: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    missing: list[dict[str, str]] = []

    for action in plan["actions"]:
        path = Path(action["path"])
        if action["type"] != "remove_temp_path":
            skipped.append(
                {
                    "path": action["path"],
                    "type": action["type"],
                    "reason": "当前 cleanup apply 只执行白名单临时路径清理。",
                }
            )
            continue
        if not path.exists():
            missing.append(
                {
                    "path": action["path"],
                    "type": action["type"],
                }
            )
            continue
        if not _within_repo_root(path, resolved_root):
            skipped.append(
                {
                    "path": action["path"],
                    "type": action["type"],
                    "reason": "路径越出仓库根，拒绝删除。",
                }
            )
            continue
        if path in _active_virtualenv_roots(resolved_root):
            skipped.append(
                {
                    "path": action["path"],
                    "type": action["type"],
                    "reason": "当前正在使用的虚拟环境不会被 cleanup apply 删除。",
                }
            )
            continue
        _remove_path(path)
        removed.append(
            {
                "path": action["path"],
                "type": action["type"],
            }
        )

    return {
        "command": "cleanup apply",
        "env": target_env,
        "repo_root": str(resolved_root),
        "planned_count": plan["action_count"],
        "removed": removed,
        "removed_count": len(removed),
        "skipped": skipped,
        "skipped_count": len(skipped),
        "missing": missing,
        "missing_count": len(missing),
    }
