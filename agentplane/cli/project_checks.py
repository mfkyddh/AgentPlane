from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from agentplane.domain.project.docs_sanity import run_docs_sanity
from agentplane.domain.project.onepanel_provider import (
    build_onepanel_route_fingerprint,
    compare_route_fingerprints,
    load_route_fingerprint,
)
from agentplane.domain.project.privacy_scan import scan_repository_for_private_material
from agentplane.domain.project.secret_scan import scan_repository_for_secrets
from agentplane.domain.project.skills import check_skill_surface


def _run_check(name: str, argv: list[str], *, repo_root: Path, timeout: int = 300) -> dict[str, Any]:
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        result = subprocess.run(
            argv,
            cwd=repo_root,
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {
            "name": name,
            "ok": False,
            "returncode": -1,
            "command": argv,
            "stdout_tail": ["timeout"],
            "stderr_tail": [f"timed out after {timeout}s"],
        }
    return {
        "name": name,
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "command": argv,
        "stdout_tail": result.stdout.splitlines()[-20:],
        "stderr_tail": result.stderr.splitlines()[-20:],
    }


def _run_sequence_check(name: str, commands: list[list[str]], *, repo_root: Path, timeout: int = 300) -> dict[str, Any]:
    steps: list[dict[str, Any]] = []
    ok = True
    for argv in commands:
        step = _run_check(name, argv, repo_root=repo_root, timeout=timeout)
        steps.append(step)
        if not step["ok"]:
            ok = False
            break
    return {
        "name": name,
        "ok": ok,
        "steps": steps,
    }


def _package_build_check(repo_root: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="agentplane-build-") as tmpdir:
        return _run_check(
            "package-build",
            [sys.executable, "-m", "build", "--outdir", tmpdir],
            repo_root=repo_root,
        )


def _coverage_check(repo_root: Path) -> dict[str, Any]:
    coverage_dir = repo_root / "tmp" / "coverage"
    coverage_dir.mkdir(parents=True, exist_ok=True)
    data_file = coverage_dir / ".coverage.fast"
    return _run_sequence_check(
        "coverage-fast",
        [
            [
                sys.executable,
                "-m",
                "coverage",
                "run",
                "--data-file",
                str(data_file),
                "-m",
                "pytest",
                "-m",
                "unit or integration",
                "-q",
            ],
            [
                sys.executable,
                "-m",
                "coverage",
                "report",
                "--data-file",
                str(data_file),
                "--fail-under=1",
            ],
        ],
        repo_root=repo_root,
    )


def _dependency_audit_check(repo_root: Path) -> dict[str, Any]:
    return _run_check(
        "dependency-audit",
        [sys.executable, "-m", "pip_audit", "--skip-editable", "--progress-spinner", "off"],
        repo_root=repo_root,
    )


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


def _skills_check(repo_root: Path) -> dict[str, Any]:
    issues = check_skill_surface(repo_root)
    return {
        "name": "skills-check",
        "ok": not issues,
        "issues": [issue.to_dict() for issue in issues],
    }


def _onepanel_route_fingerprint_check(
    *,
    source_root: Path,
    baseline: Path | None = None,
    fail_on_drift: bool = False,
) -> dict[str, Any]:
    try:
        payload = build_onepanel_route_fingerprint(source_root)
        drift = None
        ok = True
        resolved_baseline = baseline.resolve() if baseline is not None else None
        if resolved_baseline is not None:
            drift = compare_route_fingerprints(payload, load_route_fingerprint(resolved_baseline))
            if fail_on_drift and drift["changed"]:
                ok = False
        return {
            "name": "onepanel-route-fingerprint",
            "ok": ok,
            "source_root": payload["source_root"],
            "baseline": str(resolved_baseline) if resolved_baseline is not None else None,
            "fingerprint": payload["fingerprint"],
            "route_count": payload["route_count"],
            "group_count": payload["group_count"],
            "git": payload["git"],
            "impact_summary": payload["impact_summary"],
            "drift": drift,
        }
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        return {
            "name": "onepanel-route-fingerprint",
            "ok": False,
            "source_root": str(source_root),
            "baseline": str(baseline) if baseline is not None else None,
            "error": {
                "type": type(exc).__name__,
                "message": str(exc),
            },
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
    if args.onepanel_baseline and not args.onepanel_source_root:
        raise ValueError("--onepanel-baseline requires --onepanel-source-root")
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

    if args.onepanel_source_root is not None:
        checks.append(
            _onepanel_route_fingerprint_check(
                source_root=args.onepanel_source_root,
                baseline=args.onepanel_baseline,
                fail_on_drift=args.fail_on_onepanel_drift,
            )
        )

    checks.append(_skills_check(repo_root))

    return {
        "command": "project",
        "action": "health-check",
        "repo_root": str(repo_root),
        "ok": all(check.get("ok") is True for check in checks),
        "checks": checks,
    }
