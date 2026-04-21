from __future__ import annotations

import argparse
from typing import Any

from agentplane.runtime.wsl_bridge import inspect_local_host


def add_local_host_parser(host_subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    local_parser = host_subparsers.add_parser("local", help="本机控制面与 backend 绑定检查")
    local_subparsers = local_parser.add_subparsers(dest="host_local_action", required=True)

    inspect_parser = local_subparsers.add_parser("inspect", help="检查本机 host profile、workspace bindings 与 Linux backend")
    inspect_parser.add_argument("--repo-root", default=".", help="当前仓库根目录或 Windows 主控制面根目录")
    inspect_parser.add_argument("--windows-root", help="覆盖 Windows 主控制面根目录")
    inspect_parser.add_argument("--legacy-control-root", help="覆盖旧 Linux 控制面根目录")


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

    raise ValueError(f"Unsupported local host action: {args.host_local_action}")
