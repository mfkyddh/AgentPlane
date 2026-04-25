from __future__ import annotations

import json
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from subprocess import CompletedProcess
from typing import Any, Callable

RunCommand = Callable[[list[str]], CompletedProcess[str]]


def detect_upstream_version(app_root: Path, run_command: RunCommand) -> str:
    candidates = (
        app_root / "backend" / "cmd" / "server" / "VERSION",
        app_root / "VERSION",
    )
    for candidate in candidates:
        if candidate.is_file():
            version = candidate.read_text(encoding="utf-8").strip()
            if version:
                return version

    package_json = app_root / "package.json"
    if package_json.is_file():
        payload = json.loads(package_json.read_text(encoding="utf-8"))
        version = payload.get("version")
        if isinstance(version, str) and version.strip():
            return version.strip()

    pyproject = app_root / "pyproject.toml"
    if pyproject.is_file():
        try:
            payload = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as exc:
            raise ValueError(f"无法解析 {pyproject}") from exc
        project = payload.get("project")
        if isinstance(project, dict):
            version = project.get("version")
            if isinstance(version, str) and version.strip():
                return version.strip()

    result = run_command(["git", "describe", "--tags", "--abbrev=0"])
    version = result.stdout.strip()
    if result.returncode == 0 and version:
        return version

    raise ValueError(f"无法从 {app_root} 推导 upstream version")


def detect_git_short_sha(app_root: Path, run_command: RunCommand) -> str:
    result = run_command(["git", "rev-parse", "--short", "HEAD"])
    sha = result.stdout.strip()
    if result.returncode != 0 or not sha:
        raise ValueError(f"无法从 {app_root} 读取 git short sha")
    return sha


def next_fork_sequence(repo_root: Path, *, app_id: str, upstream_version: str, build_date: str) -> int:
    ledger_root = repo_root / "tmp" / "operation-ledger"
    max_sequence = 0
    if not ledger_root.is_dir():
        return 1
    for ledger_file in sorted(ledger_root.glob("*.jsonl")):
        for raw_line in ledger_file.read_text(encoding="utf-8").splitlines():
            if not raw_line.strip():
                continue
            try:
                entry = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            if not isinstance(entry, dict):
                continue
            if entry.get("command") != "app" or entry.get("action") != "build-artifact":
                continue
            if entry.get("dry_run") is True or entry.get("result") == "planned":
                continue
            if entry.get("app_id") != app_id:
                continue
            if entry.get("upstream_version") != upstream_version or entry.get("fork_version_date") != build_date:
                continue
            sequence = entry.get("fork_sequence")
            if isinstance(sequence, int):
                max_sequence = max(max_sequence, sequence)
    return max_sequence + 1


def recommended_versions(
    contract: dict[str, Any],
    *,
    repo_root: Path,
    run_in_app_root: Callable[[list[str], Path], CompletedProcess[str]],
) -> dict[str, Any]:
    app_root = Path(contract["_meta"]["app_root"])
    app_id = str(contract["app_id"])

    def run_command(command: list[str]) -> CompletedProcess[str]:
        return run_in_app_root(command, app_root)

    upstream_version = detect_upstream_version(app_root, run_command)
    git_sha = detect_git_short_sha(app_root, run_command)
    build_date = datetime.now(UTC).strftime("%Y%m%d")
    fork_sequence = next_fork_sequence(
        repo_root,
        app_id=app_id,
        upstream_version=upstream_version,
        build_date=build_date,
    )
    fork_version = f"zzz.{build_date}.v{fork_sequence}.g{git_sha}"
    return {
        "upstream_version": upstream_version,
        "build_date": build_date,
        "fork_sequence": fork_sequence,
        "git_sha": git_sha,
        "fork_version": fork_version,
        "delivery_version": f"{upstream_version}+{fork_version}",
        "image_tag": f"{upstream_version}-{fork_version}",
    }
