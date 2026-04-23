from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from agentplane.domain.ingress.handlers import (
    apply_ingress_operation,
    build_ingress_follow_through,
    get_ingress,
    plan_ingress_operation,
    refresh_ingress_ledger,
    search_ingresses,
    verify_ingress,
)
from agentplane.domain.ingress.registry import SUPPORTED_INGRESS_TARGETS
from agentplane.providers.onepanel_ingress import (
    ensure_public_ingress,
    plan_public_ingress,
    verify_public_ingress,
)
from agentplane.runtime.wsl_bridge import normalize_repo_root_for_current_host


def add_ingress_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    ingress_parser = subparsers.add_parser("ingress", help="公网入口对象（HTTP 与非 HTTP）")
    ingress_subparsers = ingress_parser.add_subparsers(dest="ingress_action", required=True)

    search = ingress_subparsers.add_parser("search", help="列出受管入口对象")
    search.add_argument("--target", required=True, choices=SUPPORTED_INGRESS_TARGETS, help="目标环境")
    search.add_argument("--repo-root", default=".", help="仓库根目录")

    for action in ("get", "verify"):
        parser = ingress_subparsers.add_parser(action, help=f"{action} ingress object")
        parser.add_argument("--target", required=True, choices=SUPPORTED_INGRESS_TARGETS, help="目标环境")
        parser.add_argument("--alias", required=True, help="入口别名")
        parser.add_argument("--repo-root", default=".", help="仓库根目录")

    for action in ("plan", "apply"):
        parser = ingress_subparsers.add_parser(action, help=f"{action} ingress operation")
        parser.add_argument("--target", required=True, choices=SUPPORTED_INGRESS_TARGETS, help="目标环境")
        parser.add_argument("--alias", required=True, help="入口别名")
        parser.add_argument("--operation", required=True, choices=("reconcile",), help="入口操作")
        parser.add_argument("--repo-root", default=".", help="仓库根目录")
        if action == "apply":
            parser.add_argument("--execute", action="store_true", help="执行写操作")

    refresh = ingress_subparsers.add_parser("refresh-ledger", help="刷新入口对象台帐")
    refresh.add_argument("--target", required=True, choices=SUPPORTED_INGRESS_TARGETS, help="目标环境")
    refresh.add_argument("--repo-root", default=".", help="仓库根目录")
    refresh.add_argument("--write", action="store_true", help="写回台帐文件")

    publish = ingress_subparsers.add_parser("publish", help="公网入口发布任务面")
    publish_subparsers = publish.add_subparsers(dest="ingress_publish_action", required=True)
    for action in ("plan", "apply", "verify"):
        parser = publish_subparsers.add_parser(action, help=f"{action} public ingress publish")
        parser.add_argument("--target", required=True, choices=SUPPORTED_INGRESS_TARGETS, help="目标环境")
        parser.add_argument("--config-file", required=True, help="入口自动化配置文件")
        parser.add_argument("--cloudflare-env-file", required=True, help="Cloudflare shell env 文件")
        parser.add_argument("--repo-root", default=".", help="仓库根目录")
        if action == "apply":
            parser.add_argument("--execute", action="store_true", help="执行写操作")


def _wrap(action: str, target: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {"command": "ingress", "action": action, "target": target, "payload": payload}


def _normalize_repo_root(path: Path | str) -> Path:
    return normalize_repo_root_for_current_host(path)


def _resolve_publish_path(repo_root: Path, raw_path: str) -> Path:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return candidate.resolve()
    return (repo_root / candidate).resolve()


def handle_ingress_command(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = _normalize_repo_root(getattr(args, "repo_root", "."))
    if args.ingress_action == "search":
        return _wrap("search", args.target, search_ingresses(repo_root, args.target))
    if args.ingress_action == "get":
        return _wrap("get", args.target, get_ingress(repo_root, args.target, args.alias))
    if args.ingress_action == "verify":
        return _wrap("verify", args.target, verify_ingress(repo_root, args.target, args.alias))
    if args.ingress_action == "plan":
        return _wrap("plan", args.target, plan_ingress_operation(repo_root, args.target, args.alias, args.operation))
    if args.ingress_action == "apply":
        return _wrap("apply", args.target, apply_ingress_operation(repo_root, args.target, args.alias, args.operation, execute=bool(args.execute)))
    if args.ingress_action == "publish":
        config_file = _resolve_publish_path(repo_root, args.config_file)
        cloudflare_env_file = _resolve_publish_path(repo_root, args.cloudflare_env_file)
        follow_through = build_ingress_follow_through(args.target, source_surface="ingress.publish")
        if args.ingress_publish_action == "plan":
            payload = dict(plan_public_ingress(args.target, config_file, cloudflare_env_file))
            payload["follow_through"] = follow_through
            return _wrap("publish.plan", args.target, payload)
        if args.ingress_publish_action == "apply":
            if not bool(args.execute):
                raise ValueError("ingress publish apply requires --execute")
            result = ensure_public_ingress(args.target, config_file, cloudflare_env_file)
            verified = verify_public_ingress(args.target, config_file, cloudflare_env_file)
            return _wrap(
                "publish.apply",
                args.target,
                {
                    "ok": bool(verified["payload"].get("ok", True)),
                    "result": result["payload"],
                    "verified": verified["payload"],
                    "follow_through": follow_through,
                },
            )
        if args.ingress_publish_action == "verify":
            result = verify_public_ingress(args.target, config_file, cloudflare_env_file)
            payload = dict(result["payload"])
            payload["follow_through"] = follow_through
            return _wrap("publish.verify", args.target, payload)
    if args.ingress_action == "refresh-ledger":
        return _wrap("refresh-ledger", args.target, refresh_ingress_ledger(repo_root, args.target, write=bool(args.write)))
    raise ValueError(f"Unsupported ingress action: {args.ingress_action}")
