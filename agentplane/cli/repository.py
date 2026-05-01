from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from agentplane.domain.repository.doc_layer import run_doc_layer_check
from agentplane.domain.repository.docs_sanity import run_docs_sanity
from agentplane.domain.repository.onepanel_provider import (
    build_onepanel_route_fingerprint,
    compare_route_fingerprints,
    load_route_fingerprint,
    write_route_fingerprint,
)
from agentplane.domain.repository.privacy_scan import scan_repository_for_private_material
from agentplane.domain.repository.secret_scan import scan_repository_for_secrets
from agentplane.domain.repository.skills import (
    check_skill_surface,
    export_skill_surface,
    list_skill_entries,
    skill_sync_report,
    write_skill_export,
)
from agentplane.domain.repository.status import build_repo_status, write_status_html


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
    health.add_argument(
        "--onepanel-source-root", type=Path, help="可选：本地 1Panel 源码根目录，用于 provider 更新门禁"
    )
    health.add_argument("--onepanel-baseline", type=Path, help="可选：上一版 1Panel route fingerprint JSON")
    health.add_argument(
        "--fail-on-onepanel-drift", action="store_true", help="可选：存在 1Panel route drift 时健康检查失败"
    )

    status = repo_subparsers.add_parser("status", help="生成当前控制面状态摘要")
    status.add_argument("--repo-root", type=Path, default=Path.cwd())
    status.add_argument("--html", type=Path, help="写出静态 HTML 仪表盘")

    docs_sanity = repo_subparsers.add_parser("docs-sanity", help="检查 active 文档链接和正式入口引用")
    docs_sanity.add_argument("--repo-root", type=Path, default=Path.cwd())

    secret_scan = repo_subparsers.add_parser("secret-scan", help="扫描 Git 可见文件中的敏感信息")
    secret_scan.add_argument("--repo-root", type=Path, default=Path.cwd())
    secret_scan.add_argument("--allowlist", type=Path)

    privacy_scan = repo_subparsers.add_parser("privacy-scan", help="扫描 Git 可见文件中的私有环境信息")
    privacy_scan.add_argument("--repo-root", type=Path, default=Path.cwd())

    doc_layer = repo_subparsers.add_parser("doc-layer", help="检查文档是否在正确的四层目录并有层级标注")
    doc_layer.add_argument("--repo-root", type=Path, default=Path.cwd())

    release = repo_subparsers.add_parser("release-check", help="运行发布前检查")
    release.add_argument("--repo-root", type=Path, default=Path.cwd())

    provider = repo_subparsers.add_parser("provider", help="Provider 更新适配门禁")
    provider_subparsers = provider.add_subparsers(dest="repo_provider_action", required=True)
    onepanel = provider_subparsers.add_parser("onepanel", help="1Panel provider 更新检查")
    onepanel_subparsers = onepanel.add_subparsers(dest="repo_provider_onepanel_action", required=True)
    route_fingerprint = onepanel_subparsers.add_parser(
        "route-fingerprint",
        help="从本地 1Panel 源码生成 API route fingerprint",
    )
    route_fingerprint.add_argument("--repo-root", type=Path, default=Path.cwd())
    route_fingerprint.add_argument("--source-root", type=Path, required=True, help="本地 1Panel 源码根目录")
    route_fingerprint.add_argument("--baseline", type=Path, help="上一版 route fingerprint JSON")
    route_fingerprint.add_argument("--output", type=Path, help="写出当前 route fingerprint JSON")
    route_fingerprint.add_argument("--fail-on-drift", action="store_true", help="存在 route drift 时返回失败")

    skills = repo_subparsers.add_parser("skills", help="Skill 能力面治理")
    skills_subparsers = skills.add_subparsers(dest="repo_skills_action", required=True)
    skills_parent = argparse.ArgumentParser(add_help=False)
    skills_parent.add_argument("--repo-root", type=Path, default=Path.cwd())

    skills_subparsers.add_parser("check", parents=[skills_parent], help="检查 Skill catalog、frontmatter 和公开能力面")
    skills_subparsers.add_parser("list", parents=[skills_parent], help="列出公开 Skill 能力面")
    export = skills_subparsers.add_parser("export", parents=[skills_parent], help="导出公开 Skill 能力面 JSON")
    export.add_argument("--output", type=Path)
    skills_subparsers.add_parser(
        "sync", parents=[skills_parent], help="dry-run 报告 Skill catalog 与 tracked Skill 漂移"
    )


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


def _run_sequence_check(name: str, commands: list[list[str]], *, repo_root: Path) -> dict[str, Any]:
    steps: list[dict[str, Any]] = []
    ok = True
    for argv in commands:
        step = _run_check(name, argv, repo_root=repo_root)
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
        "command": "repo",
        "action": "health-check",
        "repo_root": str(repo_root),
        "ok": all(check.get("ok") is True for check in checks),
        "checks": checks,
    }


def run_status_command(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = args.repo_root.resolve()
    payload = build_repo_status(repo_root)
    html_output = args.html.resolve() if args.html else None
    if html_output is not None:
        write_status_html(payload, html_output)
    payload["dashboard"] = {
        "html": str(html_output) if html_output is not None else None,
    }
    return payload


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


def run_doc_layer_command(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = args.repo_root.resolve()
    issues = run_doc_layer_check(repo_root)
    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]
    return {
        "command": "repo",
        "action": "doc-layer",
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
        _coverage_check(repo_root),
        _package_build_check(repo_root),
        _dependency_audit_check(repo_root),
        _run_check("cli-help", [sys.executable, "-m", "agentplane.cli", "--help"], repo_root=repo_root),
        _secret_scan_check(repo_root),
        _privacy_scan_check(repo_root),
        _docs_sanity_check(repo_root),
        _skills_check(repo_root),
        _git_clean_check(repo_root),
    ]
    return {
        "command": "repo",
        "action": "release-check",
        "repo_root": str(repo_root),
        "ok": all(check.get("ok") is True for check in checks),
        "checks": checks,
    }


def run_provider_command(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = args.repo_root.resolve()
    if args.repo_provider_action == "onepanel" and args.repo_provider_onepanel_action == "route-fingerprint":
        payload = build_onepanel_route_fingerprint(args.source_root)
        output = args.output.resolve() if args.output else None
        if output is not None:
            write_route_fingerprint(payload, output)

        drift = None
        ok = True
        baseline = args.baseline.resolve() if args.baseline else None
        if baseline is not None:
            drift = compare_route_fingerprints(payload, load_route_fingerprint(baseline))
            if args.fail_on_drift and drift["changed"]:
                ok = False

        return {
            "command": "repo",
            "action": "provider.onepanel.route-fingerprint",
            "repo_root": str(repo_root),
            "ok": ok,
            "output": str(output) if output is not None else None,
            "baseline": str(baseline) if baseline is not None else None,
            "drift": drift,
            "payload": payload,
        }
    raise ValueError(f"unsupported repo provider action: {args.repo_provider_action}")


def run_skills_command(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = args.repo_root.resolve()
    if args.repo_skills_action == "check":
        issues = check_skill_surface(repo_root)
        return {
            "command": "repo",
            "action": "skills.check",
            "repo_root": str(repo_root),
            "ok": not issues,
            "issues": [issue.to_dict() for issue in issues],
        }
    if args.repo_skills_action == "list":
        return {
            "command": "repo",
            "action": "skills.list",
            "repo_root": str(repo_root),
            "ok": True,
            "skills": list_skill_entries(repo_root),
        }
    if args.repo_skills_action == "export":
        payload = export_skill_surface(repo_root)
        output = args.output.resolve() if args.output else None
        if output is not None:
            write_skill_export(repo_root, output)
        return {
            "command": "repo",
            "action": "skills.export",
            "repo_root": str(repo_root),
            "ok": True,
            "output": str(output) if output is not None else None,
            "payload": payload,
        }
    if args.repo_skills_action == "sync":
        report = skill_sync_report(repo_root)
        return {
            "command": "repo",
            "action": "skills.sync",
            "repo_root": str(repo_root),
            **report,
        }
    raise ValueError(f"unsupported repo skills action: {args.repo_skills_action}")


def handle_repository_command(args: argparse.Namespace) -> dict[str, Any]:
    if args.repo_action == "health-check":
        return run_health_check(args)
    if args.repo_action == "status":
        return run_status_command(args)
    if args.repo_action == "docs-sanity":
        return run_docs_sanity_command(args)
    if args.repo_action == "doc-layer":
        return run_doc_layer_command(args)
    if args.repo_action == "secret-scan":
        return run_secret_scan(args)
    if args.repo_action == "privacy-scan":
        return run_privacy_scan(args)
    if args.repo_action == "release-check":
        return run_release_check(args)
    if args.repo_action == "provider":
        return run_provider_command(args)
    if args.repo_action == "skills":
        return run_skills_command(args)
    raise ValueError(f"unsupported repo action: {args.repo_action}")
