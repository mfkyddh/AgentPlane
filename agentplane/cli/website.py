from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from agentplane.domain.website.handlers import (
    apply_website_operation,
    build_website_follow_through,
    get_website,
    plan_website_operation,
    refresh_website_ledger,
    search_websites,
    verify_website,
)
from agentplane.domain.website.registry import SUPPORTED_WEBSITE_TARGETS
from agentplane.scripts.onepanel.public_ingress import ensure_public_ingress, plan_public_ingress, verify_public_ingress


def add_website_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    website_parser = subparsers.add_parser("website", help="正式公网入口对象")
    website_subparsers = website_parser.add_subparsers(dest="website_action", required=True)

    search = website_subparsers.add_parser("search", help="列出受管网站对象")
    search.add_argument("--target", required=True, choices=SUPPORTED_WEBSITE_TARGETS, help="目标环境")
    search.add_argument("--repo-root", default=".", help="仓库根目录")

    for action in ("get", "verify"):
        parser = website_subparsers.add_parser(action, help=f"{action} website object")
        parser.add_argument("--target", required=True, choices=SUPPORTED_WEBSITE_TARGETS, help="目标环境")
        parser.add_argument("--alias", required=True, help="网站别名")
        parser.add_argument("--repo-root", default=".", help="仓库根目录")

    for action in ("plan", "apply"):
        parser = website_subparsers.add_parser(action, help=f"{action} website operation")
        parser.add_argument("--target", required=True, choices=SUPPORTED_WEBSITE_TARGETS, help="目标环境")
        parser.add_argument("--alias", required=True, help="网站别名")
        parser.add_argument("--operation", required=True, choices=("reconcile",), help="网站操作")
        parser.add_argument("--repo-root", default=".", help="仓库根目录")
        if action == "apply":
            parser.add_argument("--execute", action="store_true", help="执行写操作")

    refresh = website_subparsers.add_parser("refresh-ledger", help="刷新网站对象台帐")
    refresh.add_argument("--target", required=True, choices=SUPPORTED_WEBSITE_TARGETS, help="目标环境")
    refresh.add_argument("--repo-root", default=".", help="仓库根目录")
    refresh.add_argument("--write", action="store_true", help="写回台帐文件")

    publish = website_subparsers.add_parser("publish", help="公网入口发布任务面")
    publish_subparsers = publish.add_subparsers(dest="website_publish_action", required=True)
    for action in ("plan", "apply", "verify"):
        parser = publish_subparsers.add_parser(action, help=f"{action} public ingress publish")
        parser.add_argument("--target", required=True, choices=SUPPORTED_WEBSITE_TARGETS, help="目标环境")
        parser.add_argument("--config-file", required=True, help="入口自动化配置文件")
        parser.add_argument("--cloudflare-env-file", required=True, help="Cloudflare shell env 文件")
        parser.add_argument("--repo-root", default=".", help="仓库根目录")
        if action == "apply":
            parser.add_argument("--execute", action="store_true", help="执行写操作")


def _wrap(action: str, target: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {"command": "website", "action": action, "target": target, "payload": payload}


def _resolve_publish_path(repo_root: Path, raw_path: str) -> Path:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return candidate.resolve()
    return (repo_root / candidate).resolve()


def handle_website_command(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = Path(getattr(args, "repo_root", ".")).resolve()
    if args.website_action == "search":
        return _wrap("search", args.target, search_websites(repo_root, args.target))
    if args.website_action == "get":
        return _wrap("get", args.target, get_website(repo_root, args.target, args.alias))
    if args.website_action == "verify":
        return _wrap("verify", args.target, verify_website(repo_root, args.target, args.alias))
    if args.website_action == "plan":
        return _wrap("plan", args.target, plan_website_operation(repo_root, args.target, args.alias, args.operation))
    if args.website_action == "apply":
        return _wrap("apply", args.target, apply_website_operation(repo_root, args.target, args.alias, args.operation, execute=bool(args.execute)))
    if args.website_action == "publish":
        config_file = _resolve_publish_path(repo_root, args.config_file)
        cloudflare_env_file = _resolve_publish_path(repo_root, args.cloudflare_env_file)
        follow_through = build_website_follow_through(args.target, source_surface="website.publish")
        if args.website_publish_action == "plan":
            payload = dict(plan_public_ingress(args.target, config_file, cloudflare_env_file))
            payload["follow_through"] = follow_through
            return _wrap("publish.plan", args.target, payload)
        if args.website_publish_action == "apply":
            if not bool(args.execute):
                raise ValueError("website publish apply requires --execute")
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
        if args.website_publish_action == "verify":
            result = verify_public_ingress(args.target, config_file, cloudflare_env_file)
            payload = dict(result["payload"])
            payload["follow_through"] = follow_through
            return _wrap("publish.verify", args.target, payload)
    if args.website_action == "refresh-ledger":
        return _wrap("refresh-ledger", args.target, refresh_website_ledger(repo_root, args.target, write=bool(args.write)))
    raise ValueError(f"Unsupported website action: {args.website_action}")
