from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from agentplane.domain.repository.docs_sanity import run_docs_sanity
from agentplane.domain.repository.privacy_scan import scan_repository_for_private_material
from agentplane.domain.repository.secret_scan import scan_repository_for_secrets


def add_repository_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    repo_parser = subparsers.add_parser("repo", help="仓库自身治理与健康检查")
    repo_subparsers = repo_parser.add_subparsers(dest="repo_action", required=True)

    health = repo_subparsers.add_parser("health-check", help="运行仓库默认健康检查")
    health.add_argument("--repo-root", type=Path, default=Path.cwd())
    health.add_argument("--skip-ruff", action="store_true")
    health.add_argument("--skip-tests", action="store_true")
    health.add_argument("--skip-secrets", action="store_true")
    health.add_argument("--skip-cli-help", action="store_true")
    health.add_argument("--skip-docs", action="store_true")

    docs_sanity = repo_subparsers.add_parser("docs-sanity", help="检查 active 文档链接和正式入口引用")
    docs_sanity.add_argument("--repo-root", type=Path, default=Path.cwd())

    secret_scan = repo_subparsers.add_parser("secret-scan", help="扫描 Git 可见文件中的敏感信息")
    secret_scan.add_argument("--repo-root", type=Path, default=Path.cwd())
    secret_scan.add_argument("--allowlist", type=Path)

    privacy_scan = repo_subparsers.add_parser("privacy-scan", help="扫描 Git 可见文件中的私有环境信息")
    privacy_scan.add_argument("--repo-root", type=Path, default=Path.cwd())

    release = repo_subparsers.add_parser("release-check", help="运行发布前检查")
    release.add_argument("--repo-root", type=Path, default=Path.cwd())


def _run_check(name: str, argv: list[str], *, repo_root: Path) -> dict[str, Any]:
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    result = subprocess.run(
        argv,
        cwd=repo_root,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    return {
        "name": name,
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "command": argv,
        "stdout_tail": result.stdout.splitlines()[-20:],
        "stderr_tail": result.stderr.splitlines()[-20:],
    }


def _secret_scan_check(repo_root: Path) -> dict[str, Any]:
    issues = scan_repository_for_secrets(repo_root)
    return {
        "name": "secret-scan",
        "ok": not issues,
        "issues": [issue.to_dict() for issue in issues],
    }


def _privacy_scan_check(repo_root: Path) -> dict[str, Any]:
    issues = scan_repository_for_private_material(repo_root)
    return {
        "name": "privacy-scan",
        "ok": not issues,
        "issues": [issue.to_dict() for issue in issues],
    }


def _docs_sanity_check(repo_root: Path) -> dict[str, Any]:
    issues = run_docs_sanity(repo_root)
    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]
    return {
        "name": "docs-sanity",
        "ok": not errors,
        "issues": [issue.to_dict() for issue in issues],
        "warnings_count": len(warnings),
        "errors_count": len(errors),
    }


def _git_clean_check(repo_root: Path) -> dict[str, Any]:
    result = subprocess.run(
        ["git", "status", "--short"],
        cwd=repo_root,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    lines = result.stdout.splitlines()
    return {
        "name": "git-clean",
        "ok": result.returncode == 0 and not lines,
        "returncode": result.returncode,
        "dirty_files": lines,
        "stderr_tail": result.stderr.splitlines()[-20:],
    }


def run_health_check(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = args.repo_root.resolve()
    checks: list[dict[str, Any]] = []

    if not args.skip_ruff:
        checks.append(_run_check("ruff", [sys.executable, "-m", "ruff", "check", "."], repo_root=repo_root))

    if not args.skip_tests:
        checks.append(_run_check("pytest", [sys.executable, "-m", "pytest"], repo_root=repo_root))

    if not args.skip_cli_help:
        checks.append(_run_check("cli-help", [sys.executable, "-m", "agentplane.cli", "--help"], repo_root=repo_root))

    if not args.skip_secrets:
        checks.append(_secret_scan_check(repo_root))
        checks.append(_privacy_scan_check(repo_root))

    if not args.skip_docs:
        checks.append(_docs_sanity_check(repo_root))

    return {
        "command": "repo",
        "action": "health-check",
        "repo_root": str(repo_root),
        "ok": all(check.get("ok") is True for check in checks),
        "checks": checks,
    }


def run_docs_sanity_command(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = args.repo_root.resolve()
    issues = run_docs_sanity(repo_root)
    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]
    return {
        "command": "repo",
        "action": "docs-sanity",
        "repo_root": str(repo_root),
        "ok": not errors,
        "issues": [issue.to_dict() for issue in issues],
        "warnings_count": len(warnings),
        "errors_count": len(errors),
    }


def run_secret_scan(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = args.repo_root.resolve()
    allowlist = args.allowlist.resolve() if args.allowlist else None
    issues = scan_repository_for_secrets(repo_root, allowlist_path=allowlist)
    return {
        "command": "repo",
        "action": "secret-scan",
        "repo_root": str(repo_root),
        "ok": not issues,
        "issues": [issue.to_dict() for issue in issues],
    }


def run_privacy_scan(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = args.repo_root.resolve()
    issues = scan_repository_for_private_material(repo_root)
    return {
        "command": "repo",
        "action": "privacy-scan",
        "repo_root": str(repo_root),
        "ok": not issues,
        "issues": [issue.to_dict() for issue in issues],
    }


def run_release_check(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = args.repo_root.resolve()
    checks = [
        _run_check("ruff", [sys.executable, "-m", "ruff", "check", "."], repo_root=repo_root),
        _run_check("pytest", [sys.executable, "-m", "pytest"], repo_root=repo_root),
        _run_check("cli-help", [sys.executable, "-m", "agentplane.cli", "--help"], repo_root=repo_root),
        _secret_scan_check(repo_root),
        _privacy_scan_check(repo_root),
        _docs_sanity_check(repo_root),
        _git_clean_check(repo_root),
    ]
    return {
        "command": "repo",
        "action": "release-check",
        "repo_root": str(repo_root),
        "ok": all(check.get("ok") is True for check in checks),
        "checks": checks,
    }


def handle_repository_command(args: argparse.Namespace) -> dict[str, Any]:
    if args.repo_action == "health-check":
        return run_health_check(args)
    if args.repo_action == "docs-sanity":
        return run_docs_sanity_command(args)
    if args.repo_action == "secret-scan":
        return run_secret_scan(args)
    if args.repo_action == "privacy-scan":
        return run_privacy_scan(args)
    if args.repo_action == "release-check":
        return run_release_check(args)
    raise ValueError(f"unsupported repo action: {args.repo_action}")
