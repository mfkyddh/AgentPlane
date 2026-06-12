from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from agentplane.cli.project_checks import _run_check, _run_sequence_check, run_health_check
from agentplane.cli.project_commands import (
    run_bump_version,
    run_doc_layer_command,
    run_docs_sanity_command,
    run_privacy_scan,
    run_provider_command,
    run_release_check,
    run_secret_scan,
    run_skills_command,
    run_status_command,
    run_topology_command,
)
from agentplane.cli.project_projection import (
    _PROJECTION_SURFACE_CONTRACTS,
    _handle_projection,
    _wrap_projection,
)
from agentplane.domain.targets import SUPPORTED_RUNTIME_ENV_TARGETS
from agentplane.providers.onepanel_objects import supported_onepanel_targets

__all__ = [
    "_PROJECTION_SURFACE_CONTRACTS",
    "_handle_projection",
    "_run_check",
    "_run_sequence_check",
    "_wrap_projection",
    "add_project_parser",
    "handle_project_command",
    "run_bump_version",
    "run_doc_layer_command",
    "run_docs_sanity_command",
    "run_health_check",
    "run_privacy_scan",
    "run_provider_command",
    "run_release_check",
    "run_secret_scan",
    "run_skills_command",
    "run_status_command",
    "run_topology_command",
]


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
