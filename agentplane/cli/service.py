from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from agentplane.domain.service.handlers import apply_service_operation, get_service, materialize_service, plan_service_operation, search_services, verify_service
from agentplane.domain.service.materialize import SUPPORTED_SERVICE_ARTIFACTS
from agentplane.domain.service.public_endpoint import apply_service_public_endpoint, plan_service_public_endpoint, verify_service_public_endpoint
from agentplane.domain.service.registry import SUPPORTED_SERVICE_TARGETS
from agentplane.runtime.wsl_bridge import normalize_repo_root_for_current_host


def add_service_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    service_parser = subparsers.add_parser("service", help="正式受管运行服务对象")
    service_subparsers = service_parser.add_subparsers(dest="service_action", required=True)

    search = service_subparsers.add_parser("search", help="列出受管服务对象")
    search.add_argument("--target", required=True, choices=SUPPORTED_SERVICE_TARGETS, help="目标环境")
    search.add_argument("--repo-root", default=".", help="仓库根目录")

    for action in ("get", "verify"):
        parser = service_subparsers.add_parser(action, help=f"{action} service object")
        parser.add_argument("--target", required=True, choices=SUPPORTED_SERVICE_TARGETS, help="目标环境")
        parser.add_argument("--name", required=True, help="服务名")
        parser.add_argument("--repo-root", default=".", help="仓库根目录")

    for action in ("plan", "apply"):
        parser = service_subparsers.add_parser(action, help=f"{action} service operation")
        parser.add_argument("--target", required=True, choices=SUPPORTED_SERVICE_TARGETS, help="目标环境")
        parser.add_argument("--name", required=True, help="服务名")
        parser.add_argument("--operation", required=True, help="服务操作")
        parser.add_argument("--repo-root", default=".", help="仓库根目录")
        if action == "apply":
            parser.add_argument("--execute", action="store_true", help="执行写操作")

    materialize = service_subparsers.add_parser("materialize", help="渲染附着在 service 上的交付产物")
    materialize.add_argument("--target", required=True, choices=SUPPORTED_SERVICE_TARGETS, help="目标环境")
    materialize.add_argument("--name", required=True, help="服务名")
    materialize.add_argument("--artifact", required=True, choices=SUPPORTED_SERVICE_ARTIFACTS, help="产物类型")
    materialize.add_argument("--source", required=True, help="输入模板或源 profile")
    materialize.add_argument("--merge-template", help="可选 merge 模板")
    materialize.add_argument("--output", required=True, help="输出文件")
    materialize.add_argument("--password", required=True, help="客户端接入密钥")
    materialize.add_argument("--node-name", default="", help="覆盖节点名")
    materialize.add_argument("--server", default="", help="覆盖服务域名")
    materialize.add_argument("--port", type=int, help="覆盖服务端口")
    materialize.add_argument("--sni", default="", help="覆盖 TLS SNI")
    materialize.add_argument("--repo-root", default=".", help="仓库根目录")

    public_endpoint = service_subparsers.add_parser("public-endpoint", help="管理附着在 service 上的公网协议端点")
    public_endpoint_subparsers = public_endpoint.add_subparsers(dest="service_public_endpoint_action", required=True)
    for action in ("verify", "plan", "apply"):
        parser = public_endpoint_subparsers.add_parser(action, help=f"{action} service public endpoint")
        parser.add_argument("--target", required=True, choices=SUPPORTED_SERVICE_TARGETS, help="目标环境")
        parser.add_argument("--name", required=True, help="服务名")
        parser.add_argument("--cloudflare-env-file", required=True, help="Cloudflare API token env 文件")
        parser.add_argument("--repo-root", default=".", help="仓库根目录")
        if action == "apply":
            parser.add_argument("--execute", action="store_true", help="执行写操作")


def _wrap(action: str, target: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {"command": "service", "action": action, "target": target, "payload": payload}


def _normalize_repo_root(path: Path | str) -> Path:
    return normalize_repo_root_for_current_host(path)


def handle_service_command(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = _normalize_repo_root(getattr(args, "repo_root", "."))
    if args.service_action == "search":
        return _wrap("search", args.target, search_services(repo_root, args.target))
    if args.service_action == "get":
        return _wrap("get", args.target, get_service(repo_root, args.target, args.name))
    if args.service_action == "verify":
        return _wrap("verify", args.target, verify_service(repo_root, args.target, args.name))
    if args.service_action == "plan":
        return _wrap("plan", args.target, plan_service_operation(repo_root, args.target, args.name, args.operation))
    if args.service_action == "apply":
        return _wrap("apply", args.target, apply_service_operation(repo_root, args.target, args.name, args.operation, execute=bool(args.execute)))
    if args.service_action == "materialize":
        return _wrap(
            "materialize",
            args.target,
            materialize_service(
                repo_root,
                args.target,
                args.name,
                args.artifact,
                source=Path(args.source),
                merge_template=Path(args.merge_template) if args.merge_template else None,
                output=Path(args.output),
                password=args.password,
                node_name=args.node_name,
                server=args.server,
                port=args.port,
                sni=args.sni,
            ),
        )
    if args.service_action == "public-endpoint":
        cloudflare_env_file = Path(args.cloudflare_env_file)
        if args.service_public_endpoint_action == "verify":
            return _wrap(
                "public-endpoint.verify",
                args.target,
                verify_service_public_endpoint(
                    repo_root,
                    args.target,
                    args.name,
                    cloudflare_env_file=cloudflare_env_file,
                ),
            )
        if args.service_public_endpoint_action == "plan":
            return _wrap(
                "public-endpoint.plan",
                args.target,
                plan_service_public_endpoint(
                    repo_root,
                    args.target,
                    args.name,
                    cloudflare_env_file=cloudflare_env_file,
                ),
            )
        if args.service_public_endpoint_action == "apply":
            return _wrap(
                "public-endpoint.apply",
                args.target,
                apply_service_public_endpoint(
                    repo_root,
                    args.target,
                    args.name,
                    cloudflare_env_file=cloudflare_env_file,
                    execute=bool(args.execute),
                ),
            )
    raise ValueError(f"Unsupported service action: {args.service_action}")
