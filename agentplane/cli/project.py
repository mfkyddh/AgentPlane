from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from agentplane.domain.app.projection.runtime_env import (
    apply_runtime_env_projection,
    plan_runtime_env_projection,
    verify_runtime_env_projection,
)
from agentplane.domain.project.doc_layer import run_doc_layer_check
from agentplane.domain.project.docs_sanity import run_docs_sanity
from agentplane.domain.project.onepanel_provider import (
    build_onepanel_route_fingerprint,
    compare_route_fingerprints,
    load_route_fingerprint,
    write_route_fingerprint,
)
from agentplane.domain.project.privacy_scan import scan_repository_for_private_material
from agentplane.domain.project.release import (
    bump_version,
    create_release_commit_and_tag,
    determine_bump_type,
    generate_changelog_entry,
    get_commits_since_tag,
    get_current_version,
    update_changelog,
    update_pyproject_version,
)
from agentplane.domain.project.secret_scan import scan_repository_for_secrets
from agentplane.domain.project.skills import (
    check_skill_surface,
    export_skill_surface,
    list_skill_entries,
    skill_sync_report,
    write_skill_export,
)
from agentplane.domain.project.status import build_repo_status, write_status_html
from agentplane.domain.project.topology import build_topology
from agentplane.domain.targets import SUPPORTED_RUNTIME_ENV_TARGETS
from agentplane.providers.onepanel_fixtures import (
    apply_fixture,
    cleanup_fixture,
    plan_fixture,
    resolve_fixture_spec,
    run_onepanel_verification_suite,
)
from agentplane.providers.onepanel_ledgers import refresh_onepanel_ledgers
from agentplane.providers.onepanel_objects import onepanel_target_executor, supported_onepanel_targets
from agentplane.runtime.redaction import redact_sensitive_value
from agentplane.runtime.wsl_bridge import normalize_repo_root_for_current_host


def add_project_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    project_parser = subparsers.add_parser("project", help="项目治理与健康检查")
    project_subparsers = project_parser.add_subparsers(dest="project_action", required=True)

    health = project_subparsers.add_parser("health-check", help="运行仓库默认健康检查")
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

    status = project_subparsers.add_parser("status", help="生成当前控制面状态摘要")
    status.add_argument("--repo-root", type=Path, default=Path.cwd())
    status.add_argument("--html", type=Path, help="写出静态 HTML 仪表盘")

    docs_sanity = project_subparsers.add_parser("docs-sanity", help="检查 active 文档链接和正式入口引用")
    docs_sanity.add_argument("--repo-root", type=Path, default=Path.cwd())

    secret_scan = project_subparsers.add_parser("secret-scan", help="扫描 Git 可见文件中的敏感信息")
    secret_scan.add_argument("--repo-root", type=Path, default=Path.cwd())
    secret_scan.add_argument("--allowlist", type=Path)

    privacy_scan = project_subparsers.add_parser("privacy-scan", help="扫描 Git 可见文件中的私有环境信息")
    privacy_scan.add_argument("--repo-root", type=Path, default=Path.cwd())

    doc_layer = project_subparsers.add_parser("doc-layer", help="检查文档是否在正确的四层目录并有层级标注")
    doc_layer.add_argument("--repo-root", type=Path, default=Path.cwd())

    release = project_subparsers.add_parser("release-check", help="运行发布前检查")
    release.add_argument("--repo-root", type=Path, default=Path.cwd())

    bump = project_subparsers.add_parser("bump-version", help="根据 conventional commits 自动确定并更新版本")
    bump.add_argument("--repo-root", type=Path, default=Path.cwd())
    bump.add_argument("--dry-run", action="store_true", help="仅展示计划，不执行变更")
    bump.add_argument("--bump-type", choices=("patch", "minor", "major"), help="覆盖自动检测的 bump 类型")

    provider = project_subparsers.add_parser("provider", help="Provider 更新适配门禁")
    provider_subparsers = provider.add_subparsers(dest="project_provider_action", required=True)
    onepanel = provider_subparsers.add_parser("onepanel", help="1Panel provider 更新检查")
    onepanel_subparsers = onepanel.add_subparsers(dest="project_provider_onepanel_action", required=True)
    route_fingerprint = onepanel_subparsers.add_parser(
        "route-fingerprint",
        help="从本地 1Panel 源码生成 API route fingerprint",
    )
    route_fingerprint.add_argument("--repo-root", type=Path, default=Path.cwd())
    route_fingerprint.add_argument("--source-root", type=Path, required=True, help="本地 1Panel 源码根目录")
    route_fingerprint.add_argument("--baseline", type=Path, help="上一版 route fingerprint JSON")
    route_fingerprint.add_argument("--output", type=Path, help="写出当前 route fingerprint JSON")
    route_fingerprint.add_argument("--fail-on-drift", action="store_true", help="存在 route drift 时返回失败")

    topology = project_subparsers.add_parser("topology", help="显示资源拓扑关系")
    topology.add_argument("--repo-root", type=Path, default=Path.cwd())
    topology.add_argument("--json", action="store_true", dest="json_output", help="输出 JSON 格式")

    skills = project_subparsers.add_parser("skills", help="Skill 能力面治理")
    skills_subparsers = skills.add_subparsers(dest="project_skills_action", required=True)
    skills_parent = argparse.ArgumentParser(add_help=False)
    skills_parent.add_argument("--repo-root", type=Path, default=Path.cwd())

    skills_subparsers.add_parser("check", parents=[skills_parent], help="检查 Skill catalog、frontmatter 和公开能力面")
    skills_subparsers.add_parser("list", parents=[skills_parent], help="列出公开 Skill 能力面")
    export = skills_subparsers.add_parser("export", parents=[skills_parent], help="导出公开 Skill 能力面 JSON")
    export.add_argument("--output", type=Path)
    skills_subparsers.add_parser(
        "sync", parents=[skills_parent], help="dry-run 报告 Skill catalog 与 tracked Skill 漂移"
    )

    # --- projection surface (merged from cli/projection.py) ---
    projection = project_subparsers.add_parser("projection", help="投影与验证任务")
    projection_subparsers = projection.add_subparsers(dest="project_projection_surface", required=True)

    runtime_env = projection_subparsers.add_parser("runtime-env", help="Runtime env projection tasks")
    runtime_env_subparsers = runtime_env.add_subparsers(dest="project_projection_action", required=True)
    for action in ("plan", "apply", "verify"):
        parser = runtime_env_subparsers.add_parser(action, help=f"{action} runtime env projection")
        parser.add_argument("--target", required=True, choices=SUPPORTED_RUNTIME_ENV_TARGETS, help="Target environment")
        parser.add_argument("--app", required=True, help="Application id")
        parser.add_argument("--repo-root", default=".", help="Repository root")
        parser.add_argument("--reveal-secrets", action="store_true", help="Include unredacted env content in output")

    verification = projection_subparsers.add_parser("verification", help="Verification observation surface")
    verification_subparsers = verification.add_subparsers(dest="project_projection_verification_action", required=True)
    run = verification_subparsers.add_parser("run", help="Run verification suite")
    run.add_argument("--target", required=True, choices=supported_onepanel_targets(), help="Target environment")
    run.add_argument(
        "--profile",
        required=True,
        choices=("wsl-fixture", "prod2-readonly", "prod0-readonly"),
        help="Verification profile",
    )
    run.add_argument("--repo-root", default=".", help="Repository root")
    run.add_argument("--write-report", action="store_true", help="Write verification report")
    run.add_argument("--website-alias", default="", help="Website alias selector")
    run.add_argument("--container-name", default="", help="Container selector")
    run.add_argument("--project-name", default="", help="Compose project selector")
    run.add_argument("--cronjob-id", type=int, default=None, help="Cronjob id selector")
    run.add_argument("--cronjob-name", default="", help="Cronjob name selector")
    run.add_argument("--app-name", default="", help="Installed app selector")
    run.add_argument(
        "--firewall-tab", default="port", choices=("port", "address", "forward"), help="Firewall tab selector"
    )

    fixture = projection_subparsers.add_parser("fixture", help="Fixture task surface")
    fixture_subparsers = fixture.add_subparsers(dest="project_projection_fixture_action", required=True)
    for action in ("plan", "apply", "cleanup"):
        parser = fixture_subparsers.add_parser(action, help=f"{action} fixture profile")
        parser.add_argument("--target", required=True, choices=supported_onepanel_targets(), help="Target environment")
        parser.add_argument("--profile", required=True, choices=("wsl-fixture",), help="Fixture profile")
        parser.add_argument("--repo-root", default=".", help="Repository root")
        parser.add_argument("--website-alias", default="", help="Website alias override")
        parser.add_argument("--container-name", default="", help="Container name override")
        parser.add_argument("--project-name", default="", help="Compose project override")
        parser.add_argument("--cronjob-name", default="", help="Cronjob name override")
        parser.add_argument("--firewall-tab", default="", help="Firewall tab override")
        if action in {"apply", "cleanup"}:
            parser.add_argument("--execute", action="store_true", help="Execute write operation")

    ledger = projection_subparsers.add_parser("ledger", help="Projection-only ledger task surface")
    ledger_subparsers = ledger.add_subparsers(dest="project_projection_ledger_action", required=True)
    refresh = ledger_subparsers.add_parser("refresh", help="Refresh tracked ledgers")
    refresh.add_argument("--target", required=True, choices=supported_onepanel_targets(), help="Target environment")
    refresh.add_argument("--repo-root", default=".", help="Repository root")
    refresh.add_argument("--write", action="store_true", help="Write tracked artifacts")


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
        "command": "project",
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
        "command": "project",
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
        "command": "project",
        "action": "secret-scan",
        "repo_root": str(repo_root),
        "ok": not issues,
        "issues": [issue.to_dict() for issue in issues],
    }


def run_privacy_scan(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = args.repo_root.resolve()
    issues = scan_repository_for_private_material(repo_root)
    return {
        "command": "project",
        "action": "privacy-scan",
        "repo_root": str(repo_root),
        "ok": not issues,
        "issues": [issue.to_dict() for issue in issues],
    }


def run_release_check(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = args.repo_root.resolve()
    checks = [
        _run_check("ruff", [sys.executable, "-m", "ruff", "check", "."], repo_root=repo_root),
        _run_check("pytest", [sys.executable, "-m", "agentplane.cli", "test", "fast", "--tb=short"], repo_root=repo_root),
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
        "command": "project",
        "action": "release-check",
        "repo_root": str(repo_root),
        "ok": all(check.get("ok") is True for check in checks),
        "checks": checks,
    }


def run_provider_command(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = args.repo_root.resolve()
    if args.project_provider_action == "onepanel" and args.project_provider_onepanel_action == "route-fingerprint":
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
            "command": "project",
            "action": "provider.onepanel.route-fingerprint",
            "repo_root": str(repo_root),
            "ok": ok,
            "output": str(output) if output is not None else None,
            "baseline": str(baseline) if baseline is not None else None,
            "drift": drift,
            "payload": payload,
        }
    raise ValueError(f"unsupported repo provider action: {args.project_provider_action}")


def run_topology_command(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = args.repo_root.resolve()
    payload = build_topology(repo_root)
    if getattr(args, "json_output", False):
        return payload
    # Human-readable output
    targets = payload.get("targets", [])
    if not targets:
        print("No targets found.")
        return payload
    for t in targets:
        print(f"\n[{t['target']}] {t['hostname']} ({t['ip'] or 'local'}) — {t['status']}")
        for app in t.get("apps", []):
            deps = ", ".join(d.get("kind", "") for d in app.get("dependencies", []))
            dep_str = f" -> [{deps}]" if deps else ""
            print(f"  ├─ App: {app['app']} ({app.get('control_plane', '-')}){dep_str}")
        for svc in t.get("services", []):
            print(f"  └─ Service: {svc['name']} ({svc.get('kind', '-')})")
    return payload


def run_bump_version(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = args.repo_root.resolve()
    current = get_current_version(repo_root)
    commits = get_commits_since_tag(repo_root)
    bump_type = determine_bump_type(commits, override=args.bump_type)
    new_version = bump_version(current, bump_type)
    changelog_entry = generate_changelog_entry(new_version, commits)
    dry_run = args.dry_run

    result: dict[str, Any] = {
        "command": "project",
        "action": "bump-version",
        "repo_root": str(repo_root),
        "current_version": current,
        "new_version": new_version,
        "bump_type": bump_type,
        "commit_count": len(commits),
        "dry_run": dry_run,
    }

    if dry_run:
        result["changelog_entry"] = changelog_entry
        result["commits"] = commits
        return result

    update_pyproject_version(repo_root, new_version)
    update_changelog(repo_root, changelog_entry)
    create_release_commit_and_tag(repo_root, new_version)
    result["ok"] = True
    return result


def run_skills_command(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = args.repo_root.resolve()
    if args.project_skills_action == "check":
        issues = check_skill_surface(repo_root)
        return {
            "command": "project",
            "action": "skills.check",
            "repo_root": str(repo_root),
            "ok": not issues,
            "issues": [issue.to_dict() for issue in issues],
        }
    if args.project_skills_action == "list":
        return {
            "command": "project",
            "action": "skills.list",
            "repo_root": str(repo_root),
            "ok": True,
            "skills": list_skill_entries(repo_root),
        }
    if args.project_skills_action == "export":
        payload = export_skill_surface(repo_root)
        output = args.output.resolve() if args.output else None
        if output is not None:
            write_skill_export(repo_root, output)
        return {
            "command": "project",
            "action": "skills.export",
            "repo_root": str(repo_root),
            "ok": True,
            "output": str(output) if output is not None else None,
            "payload": payload,
        }
    if args.project_skills_action == "sync":
        report = skill_sync_report(repo_root)
        return {
            "command": "project",
            "action": "skills.sync",
            "repo_root": str(repo_root),
            **report,
        }
    raise ValueError(f"unsupported project skills action: {args.project_skills_action}")


_PROJECTION_SURFACE_CONTRACTS = {
    "runtime-env": "projection",
    "verification": "observation",
    "fixture": "projection",
    "ledger": "projection",
}


def _wrap_projection(surface: str, action: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "command": "project",
        "surface_contract": _PROJECTION_SURFACE_CONTRACTS[surface],
        "action": action,
        **payload,
    }


def _handle_projection(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = normalize_repo_root_for_current_host(args.repo_root)
    surface = args.project_projection_surface

    if surface == "runtime-env" and args.project_projection_action == "plan":
        return _wrap_projection("runtime-env", "runtime-env.plan",
            plan_runtime_env_projection(repo_root, args.target, args.app, reveal_secrets=args.reveal_secrets))
    if surface == "runtime-env" and args.project_projection_action == "apply":
        return _wrap_projection("runtime-env", "runtime-env.apply",
            apply_runtime_env_projection(repo_root, args.target, args.app, reveal_secrets=args.reveal_secrets))
    if surface == "runtime-env" and args.project_projection_action == "verify":
        return _wrap_projection("runtime-env", "runtime-env.verify",
            verify_runtime_env_projection(repo_root, args.target, args.app, reveal_secrets=args.reveal_secrets))
    if surface == "verification" and args.project_projection_verification_action == "run":
        payload = run_onepanel_verification_suite(
            onepanel_target_executor(args.target),
            profile=args.profile, env=args.target, repo_root=repo_root,
            write_report=bool(args.write_report), website_alias=args.website_alias,
            container_name=args.container_name, project_name=args.project_name,
            cronjob_id=args.cronjob_id, cronjob_name=args.cronjob_name,
            app_name=args.app_name, firewall_tab=args.firewall_tab,
        )
        return _wrap_projection("verification", "verification.run", redact_sensitive_value(payload))
    if surface == "fixture":
        fixture_action = args.project_projection_fixture_action
        if fixture_action in {"apply", "cleanup"} and not bool(args.execute):
            raise ValueError(f"project projection fixture {fixture_action} requires --execute")
        spec = resolve_fixture_spec(
            args.profile, env=args.target, website_alias=args.website_alias,
            container_name=args.container_name, project_name=args.project_name,
            cronjob_name=args.cronjob_name, firewall_tab=args.firewall_tab,
        )
        executor = onepanel_target_executor(args.target)
        if fixture_action == "plan":
            payload = plan_fixture(executor, spec)
        elif fixture_action == "apply":
            payload = apply_fixture(executor, spec, execute=True)
        else:
            payload = cleanup_fixture(executor, spec, execute=True)
        return _wrap_projection("fixture", f"fixture.{fixture_action}", payload)
    if surface == "ledger" and args.project_projection_ledger_action == "refresh":
        return _wrap_projection("ledger", "ledger.refresh",
            refresh_onepanel_ledgers(repo_root, args.target, write=bool(args.write)))

    action = (getattr(args, "project_projection_action", None)
        or getattr(args, "project_projection_verification_action", None)
        or getattr(args, "project_projection_fixture_action", None)
        or getattr(args, "project_projection_ledger_action", None)
        or "unknown")
    raise ValueError(f"Unsupported projection action: {surface}.{action}")


def handle_project_command(args: argparse.Namespace) -> dict[str, Any]:
    if args.project_action == "health-check":
        return run_health_check(args)
    if args.project_action == "status":
        return run_status_command(args)
    if args.project_action == "docs-sanity":
        return run_docs_sanity_command(args)
    if args.project_action == "doc-layer":
        return run_doc_layer_command(args)
    if args.project_action == "secret-scan":
        return run_secret_scan(args)
    if args.project_action == "privacy-scan":
        return run_privacy_scan(args)
    if args.project_action == "release-check":
        return run_release_check(args)
    if args.project_action == "bump-version":
        return run_bump_version(args)
    if args.project_action == "provider":
        return run_provider_command(args)
    if args.project_action == "skills":
        return run_skills_command(args)
    if args.project_action == "topology":
        return run_topology_command(args)
    if args.project_action == "projection":
        return _handle_projection(args)
    raise ValueError(f"unsupported project action: {args.project_action}")
