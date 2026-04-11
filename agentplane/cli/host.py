from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from agentplane.cli.audit import audit_filesystem
from agentplane.cli.host_automation import (
    SUPPORTED_AUTOMATION_OPERATIONS,
    SUPPORTED_AUTOMATION_TARGETS,
    apply_host_automation,
    get_host_automation,
    plan_host_automation,
    search_host_automations,
    verify_host_automation,
)
from agentplane.cli.cleanup import SUPPORTED_CLEANUP_TARGETS, apply_cleanup_plan, build_cleanup_plan
from agentplane.cli.inventory import generate_inventory_snapshot
from agentplane.cli.local_host import add_local_host_parser, handle_local_host_command
from agentplane.cli.networks import SUPPORTED_NETWORK_TARGETS, audit_managed_bridge_networks, ensure_managed_bridge_networks
from agentplane.cli.remote import execute_remote_bash
from agentplane.cli.secrets import SUPPORTED_SECRET_TARGETS, init_data_services, materialize_legacy_host_layout
from agentplane.runtime.wsl_bridge import normalize_wsl_posix_path, windows_path_to_wsl_posix, wsl_unc_to_posix


SUPPORTED_HOST_TARGETS = SUPPORTED_SECRET_TARGETS
FORMAL_HOST_TARGETS = ("wsl", "prod0-main", "prod2-main")

HOST_ACTION_SCOPE_HELP = (
    "三正式目标通用动作: inventory / audit / remote bash / "
    "secrets init-data-services|sync-layout\n"
    "local: inspect / migrate plan|copy|verify\n"
    "target-specific: cleanup= wsl|prod0-main; automation= wsl|prod0-main|prod2-main; network= prod0-main|prod2-main"
)


def _target_help(*, scope: str, targets: tuple[str, ...]) -> str:
    return f"{scope}（可选: {', '.join(targets)}）"


def add_host_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    if tuple(SUPPORTED_HOST_TARGETS) != FORMAL_HOST_TARGETS:
        raise ValueError(
            f"host formal targets drift: expected {FORMAL_HOST_TARGETS}, got {tuple(SUPPORTED_HOST_TARGETS)}"
        )

    host_parser = subparsers.add_parser(
        "host",
        help="主机基线与主机级治理",
        description="统一 host 治理入口（Phase 3 formal targets: wsl / prod0-main / prod2-main）",
        epilog=HOST_ACTION_SCOPE_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    host_subparsers = host_parser.add_subparsers(dest="host_action", required=True)
    add_local_host_parser(host_subparsers)

    inventory_parser = host_subparsers.add_parser("inventory", help="生成主机结构化清单")
    inventory_parser.add_argument(
        "target",
        choices=SUPPORTED_HOST_TARGETS,
        help=_target_help(scope="三正式目标通用", targets=FORMAL_HOST_TARGETS),
    )
    inventory_parser.add_argument("--repo-root", default=".", help="仓库根目录")
    inventory_parser.add_argument("--write", action="store_true", help="写回 inventory 文件")

    audit_parser = host_subparsers.add_parser("audit", help="执行主机基线审计")
    audit_parser.add_argument(
        "target",
        choices=SUPPORTED_HOST_TARGETS,
        help=_target_help(scope="三正式目标通用", targets=FORMAL_HOST_TARGETS),
    )
    audit_parser.add_argument("--repo-root", default=".", help="仓库根目录")

    cleanup_parser = host_subparsers.add_parser("cleanup", help="执行主机级清理流程")
    cleanup_subparsers = cleanup_parser.add_subparsers(dest="host_cleanup_action", required=True)
    cleanup_plan_parser = cleanup_subparsers.add_parser("plan", help="生成主机级清理计划")
    cleanup_plan_parser.add_argument(
        "target",
        choices=SUPPORTED_CLEANUP_TARGETS,
        help=_target_help(scope="target-specific: cleanup", targets=SUPPORTED_CLEANUP_TARGETS),
    )
    cleanup_plan_parser.add_argument("--repo-root", default=".", help="仓库根目录")
    cleanup_apply_parser = cleanup_subparsers.add_parser("apply", help="执行白名单清理")
    cleanup_apply_parser.add_argument(
        "target",
        choices=SUPPORTED_CLEANUP_TARGETS,
        help=_target_help(scope="target-specific: cleanup", targets=SUPPORTED_CLEANUP_TARGETS),
    )
    cleanup_apply_parser.add_argument("--repo-root", default=".", help="仓库根目录")

    automation_parser = host_subparsers.add_parser("automation", help="主机自动化任务与 1Panel 调度器收口")
    automation_subparsers = automation_parser.add_subparsers(dest="host_automation_action", required=True)
    automation_search_parser = automation_subparsers.add_parser("search", help="列出受管自动化任务")
    automation_search_parser.add_argument(
        "target",
        choices=SUPPORTED_AUTOMATION_TARGETS,
        help=_target_help(scope="target-specific: automation", targets=SUPPORTED_AUTOMATION_TARGETS),
    )
    automation_search_parser.add_argument("--repo-root", default=".", help="仓库根目录")
    automation_get_parser = automation_subparsers.add_parser("get", help="读取自动化任务声明")
    automation_get_parser.add_argument(
        "target",
        choices=SUPPORTED_AUTOMATION_TARGETS,
        help=_target_help(scope="target-specific: automation", targets=SUPPORTED_AUTOMATION_TARGETS),
    )
    automation_get_parser.add_argument("--name", required=True, help="自动化任务名称")
    automation_get_parser.add_argument("--repo-root", default=".", help="仓库根目录")
    automation_verify_parser = automation_subparsers.add_parser("verify", help="核验自动化任务与 1Panel cronjob 是否一致")
    automation_verify_parser.add_argument(
        "target",
        choices=SUPPORTED_AUTOMATION_TARGETS,
        help=_target_help(scope="target-specific: automation", targets=SUPPORTED_AUTOMATION_TARGETS),
    )
    automation_verify_parser.add_argument("--name", required=True, help="自动化任务名称")
    automation_verify_parser.add_argument("--repo-root", default=".", help="仓库根目录")
    automation_verify_parser.add_argument("--env-file", help="覆盖 1Panel API env 文件")
    for action in ("plan", "apply"):
        parser = automation_subparsers.add_parser(action, help=f"{action} 自动化任务")
        parser.add_argument(
            "target",
            choices=SUPPORTED_AUTOMATION_TARGETS,
            help=_target_help(scope="target-specific: automation", targets=SUPPORTED_AUTOMATION_TARGETS),
        )
        parser.add_argument("--name", required=True, help="自动化任务名称")
        parser.add_argument("--operation", required=True, choices=SUPPORTED_AUTOMATION_OPERATIONS, help="自动化操作")
        parser.add_argument("--repo-root", default=".", help="仓库根目录")
        parser.add_argument("--env-file", help="覆盖 1Panel API env 文件")
        if action == "apply":
            parser.add_argument("--execute", action="store_true", help="执行计划")

    network_parser = host_subparsers.add_parser("network", help="治理受管 Docker bridge 网络")
    network_subparsers = network_parser.add_subparsers(dest="host_network_action", required=True)
    network_audit_parser = network_subparsers.add_parser("audit", help="审计受管 bridge 网络")
    network_audit_parser.add_argument(
        "target",
        choices=SUPPORTED_NETWORK_TARGETS,
        help=_target_help(scope="target-specific: network", targets=SUPPORTED_NETWORK_TARGETS),
    )
    network_audit_parser.add_argument("--repo-root", default=".", help="仓库根目录")
    network_ensure_parser = network_subparsers.add_parser("ensure", help="修复受管 bridge 网络漂移")
    network_ensure_parser.add_argument(
        "target",
        choices=SUPPORTED_NETWORK_TARGETS,
        help=_target_help(scope="target-specific: network", targets=SUPPORTED_NETWORK_TARGETS),
    )
    network_ensure_parser.add_argument("--repo-root", default=".", help="仓库根目录")

    remote_parser = host_subparsers.add_parser("remote", help="主机远端执行入口")
    remote_subparsers = remote_parser.add_subparsers(dest="host_remote_action", required=True)
    bash_parser = remote_subparsers.add_parser("bash", help="通过 ssh -T 执行远端 bash")
    bash_parser.add_argument(
        "target",
        choices=SUPPORTED_HOST_TARGETS,
        help=_target_help(scope="三正式目标通用 (SSH alias)", targets=FORMAL_HOST_TARGETS),
    )
    bash_parser.add_argument("--repo-root", default=".", help="仓库根目录")
    bash_parser.add_argument("--script-file", help="Linux 脚本文件路径")
    bash_parser.add_argument("--dry-run", action="store_true", help="只输出结构化执行计划")
    bash_parser.add_argument("remote_args", nargs="*", help="透传给远端 bash -s -- 的参数")

    secrets_parser = host_subparsers.add_parser("secrets", help="主机级 secrets 正式入口")
    secrets_subparsers = secrets_parser.add_subparsers(dest="host_secrets_action", required=True)
    secrets_init_parser = secrets_subparsers.add_parser("init-data-services", help="初始化 PostgreSQL/Redis/MinIO 管理员凭据")
    secrets_init_parser.add_argument(
        "target",
        choices=SUPPORTED_HOST_TARGETS,
        help=_target_help(scope="三正式目标通用", targets=FORMAL_HOST_TARGETS),
    )
    secrets_init_parser.add_argument("--repo-root", default=".", help="仓库根目录")
    secrets_init_parser.add_argument("--force", action="store_true", help="覆盖已存在的目标 secrets 文件")
    secrets_sync_parser = secrets_subparsers.add_parser("sync-layout", help="从 host-first secrets 真源投影旧布局")
    secrets_sync_parser.add_argument(
        "target",
        choices=SUPPORTED_HOST_TARGETS,
        help=_target_help(scope="三正式目标通用", targets=FORMAL_HOST_TARGETS),
    )
    secrets_sync_parser.add_argument("--repo-root", default=".", help="仓库根目录")
    secrets_sync_parser.add_argument("--write", action="store_true", help="写入投影路径")


def _wrap(*, action: str, target: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "command": "host",
        "action": action,
        "target": target,
        "payload": payload,
    }


def _without_public_envelope(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in payload.items()
        if key not in {"command", "action", "target", "env", "repo_root", "inventory_file"}
    }


def _normalize_repo_root(path: Path | str) -> Path:
    posix_path = windows_path_to_wsl_posix(path)
    if posix_path:
        return Path(posix_path).resolve()
    candidate = wsl_unc_to_posix(path)
    if candidate is not None:
        return candidate.resolve()
    rendered = normalize_wsl_posix_path(path)
    if rendered:
        maybe_posix = Path(rendered)
        if maybe_posix.is_absolute():
            return maybe_posix.resolve()
    return Path(path).expanduser().resolve()


def handle_host_command(args: argparse.Namespace) -> dict[str, Any]:
    if args.host_action == "local":
        action, payload = handle_local_host_command(args)
        return _wrap(action=action, target="local", payload=payload)

    repo_root = _normalize_repo_root(getattr(args, "repo_root", "."))

    if args.host_action == "inventory":
        result = generate_inventory_snapshot(repo_root, args.target, write=bool(args.write))
        return _wrap(
            action="inventory",
            target=args.target,
            payload={
                "snapshot": result["payload"],
                "inventory_file": result["inventory_file"],
                "backend_type": result.get("backend_type"),
            },
        )

    if args.host_action == "audit":
        result = audit_filesystem(repo_root, args.target)
        return _wrap(
            action="audit",
            target=args.target,
            payload={
                "ok": result["ok"],
                "violations": result["violations"],
                "path_check_mode": result.get("path_check_mode"),
            },
        )

    if args.host_action == "cleanup" and args.host_cleanup_action == "plan":
        result = build_cleanup_plan(repo_root, args.target)
        return _wrap(
            action="cleanup.plan",
            target=args.target,
            payload=_without_public_envelope(result),
        )

    if args.host_action == "cleanup" and args.host_cleanup_action == "apply":
        result = apply_cleanup_plan(repo_root, args.target)
        return _wrap(
            action="cleanup.apply",
            target=args.target,
            payload=_without_public_envelope(result),
        )

    if args.host_action == "automation" and args.host_automation_action == "search":
        return _wrap(
            action="automation.search",
            target=args.target,
            payload=search_host_automations(repo_root, args.target),
        )

    if args.host_action == "automation" and args.host_automation_action == "get":
        return _wrap(
            action="automation.get",
            target=args.target,
            payload=get_host_automation(repo_root, args.target, args.name),
        )

    if args.host_action == "automation" and args.host_automation_action == "verify":
        return _wrap(
            action="automation.verify",
            target=args.target,
            payload=verify_host_automation(repo_root, args.target, args.name, env_file=getattr(args, "env_file", None)),
        )

    if args.host_action == "automation" and args.host_automation_action == "plan":
        return _wrap(
            action="automation.plan",
            target=args.target,
            payload=plan_host_automation(
                repo_root,
                args.target,
                args.name,
                args.operation,
                env_file=getattr(args, "env_file", None),
            ),
        )

    if args.host_action == "automation" and args.host_automation_action == "apply":
        return _wrap(
            action="automation.apply",
            target=args.target,
            payload=apply_host_automation(
                repo_root,
                args.target,
                args.name,
                args.operation,
                execute=bool(args.execute),
                env_file=getattr(args, "env_file", None),
            ),
        )

    if args.host_action == "network" and args.host_network_action == "audit":
        return {
            "command": "host",
            "action": "network.audit",
            "target": args.target,
            "payload": audit_managed_bridge_networks(repo_root, args.target),
        }

    if args.host_action == "network" and args.host_network_action == "ensure":
        return {
            "command": "host",
            "action": "network.ensure",
            "target": args.target,
            "payload": ensure_managed_bridge_networks(repo_root, args.target),
        }

    if args.host_action == "remote" and args.host_remote_action == "bash":
        result = execute_remote_bash(
            repo_root=repo_root,
            target=args.target,
            remote_args=list(args.remote_args),
            script_file=args.script_file,
            dry_run=bool(args.dry_run),
        )
        return _wrap(
            action="remote.bash",
            target=args.target,
            payload=_without_public_envelope(result),
        )

    if args.host_action == "secrets" and args.host_secrets_action == "init-data-services":
        result = init_data_services(repo_root, args.target, force=bool(args.force))
        return _wrap(
            action="secrets.init-data-services",
            target=args.target,
            payload=_without_public_envelope(result),
        )

    if args.host_action == "secrets" and args.host_secrets_action == "sync-layout":
        result = materialize_legacy_host_layout(repo_root, args.target, write=bool(args.write))
        return _wrap(
            action="secrets.sync-layout",
            target=args.target,
            payload=_without_public_envelope(result),
        )

    raise ValueError(f"Unsupported host action: {args.host_action}")
