from __future__ import annotations

import argparse
from typing import Any

from agentplane.runtime.wsl_bridge import inspect_local_host, plan_local_copy, plan_local_migration, verify_local_migration


def add_local_host_parser(host_subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    local_parser = host_subparsers.add_parser("local", help="本机 Windows 主控制面与迁移入口")
    local_subparsers = local_parser.add_subparsers(dest="host_local_action", required=True)

    inspect_parser = local_subparsers.add_parser("inspect", help="检查本机 host profile、workspace bindings 与 Linux backend")
    inspect_parser.add_argument("--repo-root", default=".", help="当前仓库根目录或 Windows 主控制面根目录")
    inspect_parser.add_argument("--windows-root", help="覆盖 Windows 主控制面根目录")
    inspect_parser.add_argument("--legacy-control-root", help="覆盖旧 Linux 控制面根目录")

    migrate_parser = local_subparsers.add_parser("migrate", help="规划、复制或校验 Windows 主控制面迁移")
    migrate_subparsers = migrate_parser.add_subparsers(dest="host_local_migrate_action", required=True)
    for action in ("plan", "copy", "verify"):
        parser = migrate_subparsers.add_parser(action, help=f"{action} Windows 主控制面迁移")
        parser.add_argument("--repo-root", default=".", help="当前仓库根目录")
        parser.add_argument("--windows-root", help="目标 Windows 主控制面根目录")
        parser.add_argument("--legacy-control-root", help="覆盖旧 Linux 控制面根目录")
        if action == "copy":
            parser.add_argument("--execute", action="store_true", help="实际执行复制")


def handle_local_host_command(args: argparse.Namespace) -> tuple[str, dict[str, Any]]:
    repo_root = getattr(args, "repo_root", ".")
    windows_root = getattr(args, "windows_root", None)
    legacy_control_root = getattr(args, "legacy_control_root", None)

    if args.host_local_action == "inspect":
        return (
            "local.inspect",
            inspect_local_host(
                repo_root,
                windows_root=windows_root,
                legacy_control_root=legacy_control_root,
            ),
        )

    if args.host_local_action == "migrate" and args.host_local_migrate_action == "plan":
        return (
            "local.migrate.plan",
            plan_local_migration(
                repo_root,
                windows_root=windows_root,
                legacy_control_root=legacy_control_root,
            ),
        )

    if args.host_local_action == "migrate" and args.host_local_migrate_action == "copy":
        return (
            "local.migrate.copy",
            plan_local_copy(
                repo_root,
                windows_root=windows_root,
                legacy_control_root=legacy_control_root,
                execute=bool(args.execute),
            ),
        )

    if args.host_local_action == "migrate" and args.host_local_migrate_action == "verify":
        return (
            "local.migrate.verify",
            verify_local_migration(
                repo_root,
                windows_root=windows_root,
                legacy_control_root=legacy_control_root,
            ),
        )

    raise ValueError(f"Unsupported local host action: {args.host_local_action}")
