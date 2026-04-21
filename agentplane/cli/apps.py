from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from agentplane.domain.targets import FORMAL_TARGETS
from agentplane.runtime.wsl_bridge import normalize_repo_root_for_current_host


SUPPORTED_APP_TARGETS = FORMAL_TARGETS
FORMAL_DELIVERY_ACTIONS = (
    "validate-contract",
    "build-artifact",
    "package-runtime",
    "ship-image",
    "deploy",
    "verify",
    "rollback",
    "inventory-refresh",
    "doc-sync",
    "onboard",
    "offboard",
)
DELIVERY_EXECUTION_MODE_ACTIONS = ("deploy", "verify", "rollback")
DELIVERY_WRITE_ACTIONS = ("inventory-refresh", "doc-sync")
DELIVERY_LIFECYCLE_ACTIONS = ("onboard", "offboard")


def _normalize_repo_root(path: Path | str) -> Path:
    return normalize_repo_root_for_current_host(path)


def _add_execute_flags(parser: argparse.ArgumentParser, *, required: bool) -> None:
    flags = parser.add_mutually_exclusive_group(required=required)
    flags.add_argument("--dry-run", action="store_true", help="只输出命令，不执行")
    flags.add_argument("--execute", action="store_true", help="执行命令而不是只生成计划")


def _add_write_flag(parser: argparse.ArgumentParser, *, required: bool) -> None:
    flags = parser.add_mutually_exclusive_group(required=required)
    flags.add_argument("--write", action="store_true", help="写回目标文件")


def _add_dry_run_or_write_flags(parser: argparse.ArgumentParser, *, required: bool) -> None:
    flags = parser.add_mutually_exclusive_group(required=required)
    flags.add_argument("--dry-run", action="store_true", help="只输出计划，不写入目标文件")
    flags.add_argument("--write", action="store_true", help="按计划写回目标文件")


def _add_app_repo_root_override(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--app-repo-root", help="显式指定应用仓库根目录；优先于 catalog.repo_root")


def add_app_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    app_parser = subparsers.add_parser("app", help="应用层项目交付与 AgentPlane 协作")
    app_subparsers = app_parser.add_subparsers(dest="app_surface", required=True)

    object_parser = app_subparsers.add_parser("object", help="受管应用对象")
    object_subparsers = object_parser.add_subparsers(dest="app_object_action", required=True)

    object_search = object_subparsers.add_parser("search", help="列出受管应用对象")
    object_search.add_argument("--target", required=True, choices=SUPPORTED_APP_TARGETS, help="目标环境")
    object_search.add_argument("--app", help="仅列出指定 app；配合 --app-repo-root 可查看 worktree 合同")
    object_search.add_argument("--repo-root", default=".", help="AgentPlane 仓库根目录")
    _add_app_repo_root_override(object_search)

    for action in ("get", "verify"):
        parser = object_subparsers.add_parser(action, help=f"{action} app object")
        parser.add_argument("--target", required=True, choices=SUPPORTED_APP_TARGETS, help="目标环境")
        parser.add_argument("--app", required=True, help="catalog 中登记的 app")
        parser.add_argument("--repo-root", default=".", help="AgentPlane 仓库根目录")
        _add_app_repo_root_override(parser)

    object_refresh = object_subparsers.add_parser("refresh-ledger", help="刷新应用对象台账")
    object_refresh.add_argument("--target", required=True, choices=SUPPORTED_APP_TARGETS, help="目标环境")
    object_refresh.add_argument("--repo-root", default=".", help="AgentPlane 仓库根目录")
    object_refresh.add_argument("--write", action="store_true", help="写回台账文件")

    resource_parser = app_subparsers.add_parser("resource", help="应用关联资源对象")
    resource_subparsers = resource_parser.add_subparsers(dest="app_resource_action", required=True)

    resource_search = resource_subparsers.add_parser("search", help="列出应用关联资源对象")
    resource_search.add_argument("--target", required=True, choices=SUPPORTED_APP_TARGETS, help="目标环境")
    resource_search.add_argument("--repo-root", default=".", help="AgentPlane 仓库根目录")

    for action in ("get", "verify"):
        parser = resource_subparsers.add_parser(action, help=f"{action} app resource")
        parser.add_argument("--target", required=True, choices=SUPPORTED_APP_TARGETS, help="目标环境")
        parser.add_argument("--app", required=True, help="catalog 中登记的 app")
        parser.add_argument("--repo-root", default=".", help="AgentPlane 仓库根目录")

    resource_refresh = resource_subparsers.add_parser("refresh-ledger", help="刷新应用关联资源台账")
    resource_refresh.add_argument("--target", required=True, choices=SUPPORTED_APP_TARGETS, help="目标环境")
    resource_refresh.add_argument("--repo-root", default=".", help="AgentPlane 仓库根目录")
    resource_refresh.add_argument("--write", action="store_true", help="写回台账文件")

    delivery_parser = app_subparsers.add_parser(
        "delivery",
        help="应用正式交付流程",
        description="应用正式交付流程（single formal entry）。项目生命周期只通过 onboard/offboard 进入控制面。",
    )
    delivery_subparsers = delivery_parser.add_subparsers(dest="app_delivery_action", required=True)

    validate = delivery_subparsers.add_parser("validate-contract", help="校验应用交付合同")
    validate.add_argument("--target", required=True, choices=SUPPORTED_APP_TARGETS, help="目标环境")
    validate.add_argument("--app", required=True, help="catalog 中登记的 app")
    validate.add_argument("--repo-root", default=".", help="AgentPlane 仓库根目录")
    _add_app_repo_root_override(validate)

    render = delivery_subparsers.add_parser("render-runtime", help="渲染目标环境运行时 Compose")
    render.add_argument("--target", required=True, choices=SUPPORTED_APP_TARGETS, help="目标环境")
    render.add_argument("--app", required=True, help="catalog 中登记的 app")
    render.add_argument("--repo-root", default=".", help="AgentPlane 仓库根目录")
    render.add_argument("--image-ref", help="要写入 Compose 的镜像引用")
    _add_app_repo_root_override(render)

    inventory_refresh = delivery_subparsers.add_parser("inventory-refresh", help="按合同刷新 inventory")
    inventory_refresh.add_argument("--target", required=True, choices=SUPPORTED_APP_TARGETS, help="目标环境")
    inventory_refresh.add_argument("--app", required=True, help="catalog 中登记的 app")
    inventory_refresh.add_argument("--repo-root", default=".", help="AgentPlane 仓库根目录")
    _add_app_repo_root_override(inventory_refresh)
    _add_write_flag(inventory_refresh, required=True)

    doc_sync = delivery_subparsers.add_parser("doc-sync", help="按 inventory 渲染 AgentPlane 与应用摘要文档")
    doc_sync.add_argument("--target", required=True, choices=SUPPORTED_APP_TARGETS, help="目标环境")
    doc_sync.add_argument("--app", required=True, help="catalog 中登记的 app")
    doc_sync.add_argument("--repo-root", default=".", help="AgentPlane 仓库根目录")
    _add_app_repo_root_override(doc_sync)
    _add_write_flag(doc_sync, required=True)

    build_artifact = delivery_subparsers.add_parser("build-artifact", help="按合同构建 runtime artifact")
    build_artifact.add_argument("--target", required=True, choices=SUPPORTED_APP_TARGETS, help="目标环境")
    build_artifact.add_argument("--app", required=True, help="catalog 中登记的 app")
    build_artifact.add_argument("--repo-root", default=".", help="AgentPlane 仓库根目录")
    _add_app_repo_root_override(build_artifact)
    build_artifact.add_argument("--image-tag", help="镜像 tag")
    build_artifact.add_argument("--auto-version", action="store_true", help="按二开版本规则自动生成镜像 tag")
    build_artifact.add_argument("--dry-run", action="store_true", help="只输出命令，不执行")

    package_runtime = delivery_subparsers.add_parser("package-runtime", help="按合同把 artifact 装箱为镜像")
    package_runtime.add_argument("--target", required=True, choices=SUPPORTED_APP_TARGETS, help="目标环境")
    package_runtime.add_argument("--app", required=True, help="catalog 中登记的 app")
    package_runtime.add_argument("--repo-root", default=".", help="AgentPlane 仓库根目录")
    _add_app_repo_root_override(package_runtime)
    package_runtime.add_argument("--image-tag", help="镜像 tag")
    package_runtime.add_argument("--auto-version", action="store_true", help="按二开版本规则自动生成镜像 tag")
    package_runtime.add_argument("--dry-run", action="store_true", help="只输出命令，不执行")

    ship_image = delivery_subparsers.add_parser("ship-image", help="把镜像送到目标环境")
    ship_image.add_argument("--target", required=True, choices=SUPPORTED_APP_TARGETS, help="目标环境")
    ship_image.add_argument("--app", required=True, help="catalog 中登记的 app")
    ship_image.add_argument("--repo-root", default=".", help="AgentPlane 仓库根目录")
    _add_app_repo_root_override(ship_image)
    ship_image.add_argument("--image-ref", required=True, help="镜像引用")
    ship_image.add_argument("--archive-dir", default="tmp", help="本地镜像归档目录")
    ship_image.add_argument("--dry-run", action="store_true", help="只输出命令，不执行")

    deploy = delivery_subparsers.add_parser("deploy", help="按合同执行部署")
    deploy.add_argument("--target", required=True, choices=SUPPORTED_APP_TARGETS, help="目标环境")
    deploy.add_argument("--app", required=True, help="catalog 中登记的 app")
    deploy.add_argument("--repo-root", default=".", help="AgentPlane 仓库根目录")
    _add_app_repo_root_override(deploy)
    deploy.add_argument("--image-ref", help="镜像引用")
    _add_execute_flags(deploy, required=True)

    verify = delivery_subparsers.add_parser("verify", help="按合同校验部署结果")
    verify.add_argument("--target", required=True, choices=SUPPORTED_APP_TARGETS, help="目标环境")
    verify.add_argument("--app", required=True, help="catalog 中登记的 app")
    verify.add_argument("--repo-root", default=".", help="AgentPlane 仓库根目录")
    _add_app_repo_root_override(verify)
    _add_execute_flags(verify, required=True)

    rollback = delivery_subparsers.add_parser("rollback", help="按合同回滚到上一控制面")
    rollback.add_argument("--target", required=True, choices=SUPPORTED_APP_TARGETS, help="目标环境")
    rollback.add_argument("--app", required=True, help="catalog 中登记的 app")
    rollback.add_argument("--repo-root", default=".", help="AgentPlane 仓库根目录")
    _add_app_repo_root_override(rollback)
    _add_execute_flags(rollback, required=True)

    onboard = delivery_subparsers.add_parser(
        "onboard",
        help="项目生命周期 onboard（single formal entry）",
        description="项目生命周期 onboard（single formal entry）。本动作只定义正式契约与参数边界；语义由 domain handler 决定。",
    )
    onboard.add_argument("--target", required=True, choices=SUPPORTED_APP_TARGETS, help="目标环境")
    onboard.add_argument("--app", required=True, help="catalog 中登记的 app")
    onboard.add_argument("--repo-root", default=".", help="AgentPlane 仓库根目录")
    onboard.add_argument("--app-repo-root", help="应用仓库根目录；app 尚未登记到 catalog 时提供")
    onboard.add_argument("--repo-name", help="catalog repo_name；默认取 app-repo-root 目录名")
    onboard.add_argument("--contract-path", help="合同文件路径；可相对 app-repo-root，默认 deploy/agentplane/contract.yaml")
    _add_dry_run_or_write_flags(onboard, required=True)

    offboard = delivery_subparsers.add_parser(
        "offboard",
        help="项目生命周期 offboard（single formal entry）",
        description="项目生命周期 offboard（single formal entry）。本动作只定义正式契约与参数边界；语义由 domain handler 决定。",
    )
    offboard.add_argument("--target", required=True, choices=SUPPORTED_APP_TARGETS, help="目标环境")
    offboard.add_argument("--app", required=True, help="catalog 中登记的 app")
    offboard.add_argument("--repo-root", default=".", help="AgentPlane 仓库根目录")
    _add_dry_run_or_write_flags(offboard, required=True)


def _ensure_formal_delivery_action_contract(args: argparse.Namespace) -> None:
    action = str(getattr(args, "app_delivery_action", ""))
    if action not in FORMAL_DELIVERY_ACTIONS:
        return
    if action in DELIVERY_EXECUTION_MODE_ACTIONS:
        dry_run = bool(getattr(args, "dry_run", False))
        execute = bool(getattr(args, "execute", False))
        if dry_run == execute:
            raise ValueError(f"{action} 必须显式二选一：--dry-run 或 --execute")
    if action in DELIVERY_WRITE_ACTIONS and not bool(getattr(args, "write", False)):
        raise ValueError(f"{action} 必须显式传 --write")
    if action in DELIVERY_LIFECYCLE_ACTIONS:
        dry_run = bool(getattr(args, "dry_run", False))
        write = bool(getattr(args, "write", False))
        if dry_run == write:
            raise ValueError(f"{action} 必须显式二选一：--dry-run 或 --write")


def handle_app_command(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = _normalize_repo_root(getattr(args, "repo_root", "."))
    if args.app_surface == "object":
        from agentplane.domain.app.object_handlers import get_app, refresh_app_ledger, search_apps, verify_app_object

        if args.app_object_action == "search":
            if getattr(args, "app_repo_root", None) and not getattr(args, "app", None):
                raise ValueError("object search 使用 --app-repo-root 时必须同时指定 --app")
            return {
                "command": "app",
                "action": "object.search",
                "target": args.target,
                "payload": search_apps(
                    repo_root,
                    args.target,
                    app=getattr(args, "app", None),
                    app_repo_root=getattr(args, "app_repo_root", None),
                ),
            }
        if args.app_object_action == "get":
            return {
                "command": "app",
                "action": "object.get",
                "target": args.target,
                "payload": get_app(repo_root, args.target, args.app, app_repo_root=getattr(args, "app_repo_root", None)),
            }
        if args.app_object_action == "verify":
            return {
                "command": "app",
                "action": "object.verify",
                "target": args.target,
                "payload": verify_app_object(repo_root, args.target, args.app, app_repo_root=getattr(args, "app_repo_root", None)),
            }
        if args.app_object_action == "refresh-ledger":
            return {"command": "app", "action": "object.refresh-ledger", "target": args.target, "payload": refresh_app_ledger(repo_root, args.target, write=bool(args.write))}
        raise ValueError(f"Unsupported app object action: {args.app_object_action}")

    if args.app_surface == "resource":
        from agentplane.domain.app.resource_handlers import (
            get_app_resource,
            refresh_app_resource_ledger,
            search_app_resources,
            verify_app_resource,
        )

        if args.app_resource_action == "search":
            return {"command": "app", "action": "resource.search", "target": args.target, "payload": search_app_resources(repo_root, args.target)}
        if args.app_resource_action == "get":
            return {"command": "app", "action": "resource.get", "target": args.target, "payload": get_app_resource(repo_root, args.target, args.app)}
        if args.app_resource_action == "verify":
            return {"command": "app", "action": "resource.verify", "target": args.target, "payload": verify_app_resource(repo_root, args.target, args.app)}
        if args.app_resource_action == "refresh-ledger":
            return {
                "command": "app",
                "action": "resource.refresh-ledger",
                "target": args.target,
                "payload": refresh_app_resource_ledger(repo_root, args.target, write=bool(args.write)),
            }
        raise ValueError(f"Unsupported app resource action: {args.app_resource_action}")

    if args.app_surface == "delivery":
        _ensure_formal_delivery_action_contract(args)
        from agentplane.domain.app.delivery_service import AppDeliveryService

        delivery_service = AppDeliveryService(repo_root)

        if args.app_delivery_action == "validate-contract":
            return delivery_service.validate_contract(
                target=args.target,
                app=args.app,
                app_repo_root=getattr(args, "app_repo_root", None),
            )
        if args.app_delivery_action == "render-runtime":
            return delivery_service.render_runtime(
                target=args.target,
                app=args.app,
                image_ref=args.image_ref,
                app_repo_root=getattr(args, "app_repo_root", None),
            )
        if args.app_delivery_action == "inventory-refresh":
            return delivery_service.inventory_refresh(
                target=args.target,
                app=args.app,
                write=bool(args.write),
                app_repo_root=getattr(args, "app_repo_root", None),
            )
        if args.app_delivery_action == "doc-sync":
            return delivery_service.doc_sync(
                target=args.target,
                app=args.app,
                write=bool(args.write),
                app_repo_root=getattr(args, "app_repo_root", None),
            )
        if args.app_delivery_action == "build-artifact":
            return delivery_service.build_artifact(
                target=args.target,
                app=args.app,
                image_tag=args.image_tag,
                auto_version=args.auto_version,
                dry_run=args.dry_run,
                app_repo_root=getattr(args, "app_repo_root", None),
            )
        if args.app_delivery_action == "package-runtime":
            return delivery_service.package_runtime(
                target=args.target,
                app=args.app,
                image_tag=args.image_tag,
                auto_version=args.auto_version,
                dry_run=args.dry_run,
                app_repo_root=getattr(args, "app_repo_root", None),
            )
        if args.app_delivery_action == "ship-image":
            return delivery_service.ship_image(
                target=args.target,
                app=args.app,
                image_ref=args.image_ref,
                archive_dir=Path(args.archive_dir),
                dry_run=args.dry_run,
                app_repo_root=getattr(args, "app_repo_root", None),
            )
        if args.app_delivery_action == "deploy":
            return delivery_service.deploy(
                target=args.target,
                app=args.app,
                image_ref=args.image_ref,
                dry_run=args.dry_run,
                execute=bool(getattr(args, "execute", False)),
                app_repo_root=getattr(args, "app_repo_root", None),
            )
        if args.app_delivery_action == "verify":
            return delivery_service.verify(
                target=args.target,
                app=args.app,
                dry_run=args.dry_run,
                execute=bool(getattr(args, "execute", False)),
                app_repo_root=getattr(args, "app_repo_root", None),
            )
        if args.app_delivery_action == "rollback":
            return delivery_service.rollback(
                target=args.target,
                app=args.app,
                dry_run=args.dry_run,
                execute=bool(getattr(args, "execute", False)),
                app_repo_root=getattr(args, "app_repo_root", None),
            )
        if args.app_delivery_action == "onboard":
            return delivery_service.onboard(
                target=args.target,
                app=args.app,
                dry_run=bool(getattr(args, "dry_run", False)),
                write=bool(getattr(args, "write", False)),
                app_repo_root=getattr(args, "app_repo_root", None),
                repo_name=getattr(args, "repo_name", None),
                contract_path=getattr(args, "contract_path", None),
            )
        if args.app_delivery_action == "offboard":
            return delivery_service.offboard(
                target=args.target,
                app=args.app,
                dry_run=bool(getattr(args, "dry_run", False)),
                write=bool(getattr(args, "write", False)),
            )
        raise ValueError(f"Unsupported app delivery action: {args.app_delivery_action}")

    raise ValueError(f"Unsupported app surface: {args.app_surface}")
