from __future__ import annotations

import argparse
import sys
from typing import Any

from agentplane.cli.project_checks import (
    _coverage_check,
    _dependency_audit_check,
    _docs_sanity_check,
    _git_clean_check,
    _package_build_check,
    _privacy_scan_check,
    _run_check,
    _secret_scan_check,
    _skills_check,
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
