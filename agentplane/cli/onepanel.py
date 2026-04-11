from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from agentplane.cli.operations import append_operation_ledger, next_operation_id
from agentplane.scripts.onepanel.env_targets import get_target, supported_targets
from agentplane.scripts.onepanel.executor import TargetExecutor
from agentplane.scripts.onepanel.fixture_manager import apply_fixture, cleanup_fixture, plan_fixture, resolve_fixture_spec, resolve_suite_targets
from agentplane.scripts.onepanel.ledger import refresh_ledgers
from agentplane.scripts.onepanel.object_api import (
    get_app_catalog,
    get_app_catalog_detail,
    get_compose_project,
    get_container,
    get_installed_app,
    get_panel_summary,
    load_firewall_base,
    get_task_count,
    get_website,
    load_cronjob,
    plan_app_install,
    plan_cronjob_operation,
    plan_installed_app_operation,
    plan_installed_app_params_update,
    plan_panel_setting_update,
    plan_compose_project_operation,
    plan_container_operation,
    plan_firewall_operation,
    plan_website_create,
    search_firewall_rules,
    search_compose_projects,
    search_containers,
    search_cronjobs,
    search_installed_apps,
    search_tasks,
    search_websites,
)
from agentplane.scripts.onepanel.public_ingress import command_ensure_public_ingress
from agentplane.scripts.onepanel.verification import run_verification_suite


def add_onepanel_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    onepanel_parser = subparsers.add_parser("onepanel", help="1Panel 受管操作")
    onepanel_parser.add_argument("--env", default="wsl", choices=supported_targets(), help="目标环境")
    onepanel_parser.add_argument("--env-file", help="覆盖选定环境的 1Panel API env 文件")
    onepanel_parser.add_argument("--json", action="store_true", help="输出结构化 JSON")
    onepanel_subparsers = onepanel_parser.add_subparsers(dest="onepanel_scope")

    _add_panel_parser(onepanel_subparsers)
    _add_firewall_parser(onepanel_subparsers)
    _add_cronjob_parser(onepanel_subparsers)
    _add_task_parser(onepanel_subparsers)


def _add_object_lookup_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--id", type=int, help="对象 ID")
    parser.add_argument("--name", default="", help="对象名称")
    parser.add_argument("--alias", default="", help="对象别名")


def _add_refresh_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser], *, handler: Any, help_text: str) -> None:
    refresh = subparsers.add_parser("refresh-ledger", help=help_text)
    refresh.add_argument("--repo-root", default=".", help="仓库根目录")
    refresh.add_argument("--write", action="store_true", help="写入 ledgers")
    refresh.set_defaults(onepanel_handler=handler)


def _add_execute_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--execute", action="store_true", help="执行写操作")


def _add_panel_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("panel", help="1Panel 面板对象")
    panel_subparsers = parser.add_subparsers(dest="onepanel_panel_action", required=True)
    for action in ("search", "get", "verify"):
        sub = panel_subparsers.add_parser(action, help=f"{action} panel")
        sub.add_argument("--key", default="", help="设置项 key")
        sub.set_defaults(onepanel_handler=_handle_panel_action)
    for action in ("plan", "apply"):
        sub = panel_subparsers.add_parser(action, help=f"{action} panel setting update")
        sub.add_argument("--key", required=True, help="设置项 key")
        sub.add_argument("--value", required=True, help="设置项值")
        _add_execute_args(sub)
        sub.set_defaults(onepanel_handler=_handle_panel_action)
    _add_refresh_parser(panel_subparsers, handler=_handle_panel_action, help_text="刷新对象台帐")


def _add_website_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("website", help="1Panel 网站对象")
    website_subparsers = parser.add_subparsers(dest="onepanel_website_action", required=True)
    search = website_subparsers.add_parser("search", help="搜索网站对象")
    search.add_argument("--name", default="", help="搜索名称")
    search.add_argument("--group-id", type=int, default=0, help="网站分组 ID")
    search.set_defaults(onepanel_handler=_handle_website_action)
    get = website_subparsers.add_parser("get", help="读取网站对象")
    _add_object_lookup_args(get)
    get.set_defaults(onepanel_handler=_handle_website_action)
    for action in ("plan", "apply"):
        sub = website_subparsers.add_parser(action, help=f"{action} proxy 网站")
        sub.add_argument("--alias", required=True, help="网站别名")
        sub.add_argument("--domain", required=True, help="主域名")
        sub.add_argument("--proxy", required=True, help="反代目标")
        sub.add_argument("--group-id", type=int, default=1, help="网站分组 ID")
        sub.add_argument("--website-type", default="proxy", help="网站类型")
        sub.add_argument("--remark", default="", help="备注")
        sub.add_argument("--ipv6", default="true", help="是否开启 IPv6")
        _add_execute_args(sub)
        sub.set_defaults(onepanel_handler=_handle_website_action)
    verify = website_subparsers.add_parser("verify", help="校验网站对象")
    _add_object_lookup_args(verify)
    verify.add_argument("--expected-proxy", default="", help="期望 proxy")
    verify.set_defaults(onepanel_handler=_handle_website_action)
    _add_refresh_parser(website_subparsers, handler=_handle_website_action, help_text="刷新对象台帐")


def _add_container_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("container", help="1Panel 容器对象")
    container_subparsers = parser.add_subparsers(dest="onepanel_container_action", required=True)
    search = container_subparsers.add_parser("search", help="搜索容器")
    search.add_argument("--name", default="", help="容器名称")
    search.add_argument("--state", default="", help="状态过滤")
    search.set_defaults(onepanel_handler=_handle_container_action)
    get = container_subparsers.add_parser("get", help="读取容器")
    get.add_argument("--name", required=True, help="容器名称")
    get.set_defaults(onepanel_handler=_handle_container_action)
    verify = container_subparsers.add_parser("verify", help="校验容器")
    verify.add_argument("--name", required=True, help="容器名称")
    verify.add_argument("--expected-state", default="", help="期望状态")
    verify.set_defaults(onepanel_handler=_handle_container_action)
    for action in ("plan", "apply"):
        sub = container_subparsers.add_parser(action, help=f"{action} container operation")
        sub.add_argument("--name", required=True, help="容器名称")
        sub.add_argument("--operate", required=True, choices=("start", "stop", "restart", "kill", "pause", "unpause"), help="容器操作")
        _add_execute_args(sub)
        sub.set_defaults(onepanel_handler=_handle_container_action)
    _add_refresh_parser(container_subparsers, handler=_handle_container_action, help_text="刷新对象台帐")


def _add_firewall_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("firewall", help="防火墙对象")
    firewall_subparsers = parser.add_subparsers(dest="onepanel_firewall_action", required=True)
    search = firewall_subparsers.add_parser("search", help="搜索 firewall rules")
    search.add_argument("--type", default="port", choices=("port", "address", "forward"), help="规则类型")
    search.add_argument("--info", default="", help="搜索关键字")
    search.add_argument("--status", default="", help="状态过滤")
    search.add_argument("--strategy", default="", help="策略过滤")
    search.set_defaults(onepanel_handler=_handle_firewall_action)
    get = firewall_subparsers.add_parser("get", help="读取 firewall base")
    get.add_argument("--tab", default="port", choices=("port", "address", "forward"), help="firewall tab")
    get.set_defaults(onepanel_handler=_handle_firewall_action)
    verify = firewall_subparsers.add_parser("verify", help="校验 firewall")
    verify.add_argument("--tab", default="port", choices=("port", "address", "forward"), help="firewall tab")
    verify.add_argument("--expected-active", default="", help="期望是否激活 true/false")
    verify.add_argument("--expected-name", default="", help="期望防火墙名称")
    verify.set_defaults(onepanel_handler=_handle_firewall_action)
    for action in ("plan", "apply"):
        sub = firewall_subparsers.add_parser(action, help=f"{action} firewall operation")
        sub.add_argument(
            "--operation",
            required=True,
            choices=("start", "stop", "restart", "disableBanPing", "enableBanPing"),
            help="防火墙操作",
        )
        sub.add_argument("--with-docker-restart", action="store_true", help="是否联动重启 Docker")
        _add_execute_args(sub)
        sub.set_defaults(onepanel_handler=_handle_firewall_action)
    _add_refresh_parser(firewall_subparsers, handler=_handle_firewall_action, help_text="刷新对象台帐")


def _add_cronjob_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("cronjob", help="1Panel 计划任务对象")
    cron_subparsers = parser.add_subparsers(dest="onepanel_cronjob_action", required=True)
    search = cron_subparsers.add_parser("search", help="搜索计划任务")
    search.add_argument("--info", default="", help="搜索关键字")
    search.set_defaults(onepanel_handler=_handle_cronjob_action)
    get = cron_subparsers.add_parser("get", help="读取计划任务")
    get.add_argument("--id", required=True, type=int, help="计划任务 ID")
    get.set_defaults(onepanel_handler=_handle_cronjob_action)
    for action in ("plan", "apply"):
        sub = cron_subparsers.add_parser(action, help=f"{action} cronjob mutation")
        sub.add_argument("--mode", required=True, choices=("create", "update", "handle", "status"), help="操作模式")
        sub.add_argument("--body-json", required=True, help="请求体 JSON")
        _add_execute_args(sub)
        sub.set_defaults(onepanel_handler=_handle_cronjob_action)
    verify = cron_subparsers.add_parser("verify", help="校验计划任务")
    verify.add_argument("--id", required=True, type=int, help="计划任务 ID")
    verify.add_argument("--expected-status", default="", help="期望状态")
    verify.set_defaults(onepanel_handler=_handle_cronjob_action)
    _add_refresh_parser(cron_subparsers, handler=_handle_cronjob_action, help_text="刷新对象台帐")


def _add_app_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("app", help="1Panel 应用对象")
    app_subparsers = parser.add_subparsers(dest="onepanel_app_action", required=True)
    search = app_subparsers.add_parser("search", help="搜索已安装应用")
    search.add_argument("--name", default="", help="应用名称")
    search.add_argument("--type", default="", help="应用类型")
    search.set_defaults(onepanel_handler=_handle_app_action)
    catalog = app_subparsers.add_parser("catalog-get", help="读取应用商店条目")
    catalog.add_argument("--app", required=True, help="应用 key")
    catalog.add_argument("--version", default="", help="可选版本")
    catalog.set_defaults(onepanel_handler=_handle_app_action)
    get = app_subparsers.add_parser("get", help="读取应用详情")
    get.add_argument("--id", type=int, help="install ID")
    get.add_argument("--name", default="", help="应用名称")
    get.set_defaults(onepanel_handler=_handle_app_action)
    verify = app_subparsers.add_parser("verify", help="校验应用详情")
    verify.add_argument("--id", type=int, help="install ID")
    verify.add_argument("--name", default="", help="应用名称")
    verify.add_argument("--expected-status", default="", help="期望状态")
    verify.set_defaults(onepanel_handler=_handle_app_action)
    for action in ("plan", "apply"):
        sub = app_subparsers.add_parser(action, help=f"{action} installed app operation")
        sub.add_argument("--id", type=int, help="install ID")
        sub.add_argument("--name", default="", help="应用名称")
        sub.add_argument("--operate", required=True, choices=("start", "stop", "restart"), help="应用操作")
        _add_execute_args(sub)
        sub.set_defaults(onepanel_handler=_handle_app_action)
    for action in ("params-plan", "params-apply"):
        sub = app_subparsers.add_parser(action, help=f"{action} installed app params update")
        sub.add_argument("--id", type=int, help="install ID")
        sub.add_argument("--name", default="", help="应用名称")
        sub.add_argument("--params-json", required=True, help="请求体 params JSON object")
        _add_execute_args(sub)
        sub.set_defaults(onepanel_handler=_handle_app_action)
    install = app_subparsers.add_parser("install", help="从应用商店安装应用")
    install.add_argument("--app", required=True, help="应用 key")
    install.add_argument("--version", required=True, help="应用版本")
    install.add_argument("--name", default="", help="安装名称，默认与 app key 一致")
    install.add_argument("--container", default="", help="显式容器名")
    install.add_argument("--param", action="append", default=[], help="重复传 KEY=VALUE 安装参数")
    install.add_argument("--pull-image", action="store_true", help="安装时主动拉取镜像")
    install.add_argument("--specify-ip", default="", help="可选宿主机绑定 IP")
    install.add_argument(
        "--restart-policy",
        default="always",
        choices=("always", "unless-stopped", "no", "on-failure"),
        help="容器重启策略",
    )
    install.add_argument("--wait", action="store_true", help="等待安装对象进入 Running")
    _add_execute_args(install)
    install.set_defaults(onepanel_handler=_handle_app_action)
    _add_refresh_parser(app_subparsers, handler=_handle_app_action, help_text="刷新对象台帐")


def _add_project_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("project", help="仓库托管的 1Panel compose 项目")
    project_subparsers = parser.add_subparsers(dest="onepanel_project_action", required=True)
    search = project_subparsers.add_parser("search", help="搜索 1Panel compose 项目")
    search.add_argument("--info", default="", help="搜索关键字")
    search.set_defaults(onepanel_handler=_handle_project_action)
    get = project_subparsers.add_parser("get", help="读取 compose 项目")
    get.add_argument("--name", required=True, help="项目名称")
    get.set_defaults(onepanel_handler=_handle_project_action)
    verify = project_subparsers.add_parser("verify", help="校验 compose 项目")
    verify.add_argument("--name", required=True, help="项目名称")
    verify.add_argument("--expected-status", default="", help="期望状态")
    verify.add_argument("--expected-running-count", type=int, default=None, help="期望 runningCount")
    verify.set_defaults(onepanel_handler=_handle_project_action)
    for action in ("plan", "apply"):
        sub = project_subparsers.add_parser(action, help=f"{action} compose 项目操作")
        sub.add_argument("--name", required=True, help="项目名称")
        sub.add_argument("--operate", required=True, choices=("up", "down", "restart", "stop"), help="项目操作")
        sub.add_argument("--with-file", action="store_true", help="是否携带 compose 文件删除")
        sub.add_argument("--force", action="store_true", help="是否强制执行")
        _add_execute_args(sub)
        sub.set_defaults(onepanel_handler=_handle_project_action)
    _add_refresh_parser(project_subparsers, handler=_handle_project_action, help_text="刷新对象台帐")


def _add_task_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("task", help="1Panel 任务中心对象")
    task_subparsers = parser.add_subparsers(dest="onepanel_task_action", required=True)
    search = task_subparsers.add_parser("search", help="搜索任务")
    search.add_argument("--type", default="", help="任务类型")
    search.add_argument("--status", default="", help="任务状态")
    search.set_defaults(onepanel_handler=_handle_task_action)
    get = task_subparsers.add_parser("get", help="读取任务概况")
    get.set_defaults(onepanel_handler=_handle_task_action)
    verify = task_subparsers.add_parser("verify", help="校验执行中的任务数量")
    verify.add_argument("--expected-count", type=int, default=None, help="期望 executing 数量")
    verify.set_defaults(onepanel_handler=_handle_task_action)
    _add_refresh_parser(task_subparsers, handler=_handle_task_action, help_text="刷新对象台帐")


def _add_ledger_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("ledger", help="对象台帐")
    ledger_subparsers = parser.add_subparsers(dest="onepanel_ledger_action", required=True)
    refresh = ledger_subparsers.add_parser("refresh", help="刷新对象台帐")
    refresh.add_argument("--repo-root", default=".", help="仓库根目录")
    refresh.add_argument("--write", action="store_true", help="写入 ledgers")
    refresh.set_defaults(onepanel_handler=_handle_ledger_action)


def _add_suite_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("suite", help="标准 onepanel 验证套件")
    suite_subparsers = parser.add_subparsers(dest="onepanel_suite_action", required=True)
    run = suite_subparsers.add_parser("run", help="执行验证套件")
    run.add_argument("--repo-root", default=".", help="仓库根目录")
    run.add_argument("--profile", required=True, choices=("wsl-fixture", "prod2-readonly", "prod0-readonly"), help="验证档位")
    run.add_argument("--website-alias", default="", help="网站别名")
    run.add_argument("--container-name", default="", help="容器名称")
    run.add_argument("--project-name", default="", help="compose 项目名称")
    run.add_argument("--cronjob-id", type=int, default=None, help="计划任务 ID")
    run.add_argument("--cronjob-name", default="", help="计划任务名称")
    run.add_argument("--app-name", default="", help="应用名称")
    run.add_argument("--firewall-tab", default="port", choices=("port", "address", "forward"), help="防火墙 tab")
    run.add_argument("--write-report", action="store_true", help="写入验证报告")
    run.set_defaults(onepanel_handler=_handle_suite_action)


def _add_fixture_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("fixture", help="WSL fixture 编排")
    fixture_subparsers = parser.add_subparsers(dest="onepanel_fixture_action", required=True)
    for action in ("plan", "apply", "cleanup"):
        sub = fixture_subparsers.add_parser(action, help=f"{action} fixture profile")
        sub.add_argument("--profile", required=True, choices=("wsl-fixture",), help="fixture 档位")
        sub.add_argument("--repo-root", default=".", help="仓库根目录")
        if action in {"apply", "cleanup"}:
            _add_execute_args(sub)
        sub.set_defaults(onepanel_handler=_handle_fixture_action)


def _add_ingress_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    ingress_parser = subparsers.add_parser("ingress", help="Cloudflare + 1Panel 公网入口自动化")
    ingress_subparsers = ingress_parser.add_subparsers(dest="onepanel_ingress_action", required=True)
    ensure = ingress_subparsers.add_parser("ensure-cloudflare-dns01", help="幂等确保 Cloudflare DNS 与 1Panel DNS-01 公网入口")
    ensure.add_argument("--config-file", required=True, help="入口自动化配置 env 文件")
    ensure.add_argument("--cloudflare-env-file", required=True, help="Cloudflare shell env 文件")
    ensure.set_defaults(onepanel_handler=_handle_ingress_ensure)


def _executor_for(args: argparse.Namespace) -> TargetExecutor:
    return TargetExecutor(get_target(args.env, getattr(args, "env_file", None)))


def _refresh_ledger_payload(args: argparse.Namespace) -> dict[str, Any]:
    return refresh_ledgers(Path(getattr(args, "repo_root", ".")).resolve(), args.env, write=bool(getattr(args, "write", False)))


def _bool_arg(raw: str) -> bool:
    return str(raw).strip().lower() not in {"0", "false", "no", "off"}


def _find_website_id(executor: TargetExecutor, *, website_id: int | None, name: str, alias: str) -> int:
    if website_id:
        return int(website_id)
    query = alias or name
    payload = search_websites(executor, name=query)
    items = payload.get("items")
    if not isinstance(items, list):
        raise RuntimeError("website search returned no items")
    for item in items:
        if not isinstance(item, dict):
            continue
        if alias and item.get("alias") == alias:
            return int(item["id"])
        if name and item.get("primaryDomain") == name:
            return int(item["id"])
        if name and item.get("alias") == name:
            return int(item["id"])
    if items and isinstance(items[0], dict) and "id" in items[0]:
        return int(items[0]["id"])
    raise RuntimeError("website not found")


def _find_installed_app_id(executor: TargetExecutor, *, install_id: int | None, name: str, app_type: str = "") -> int:
    if install_id:
        return int(install_id)
    if not name:
        raise RuntimeError("app id or name is required")
    payload = search_installed_apps(executor, name=name, app_type=app_type)
    items = payload.get("items")
    if not isinstance(items, list):
        raise RuntimeError("installed app search returned no items")
    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get("name") == name or item.get("appKey") == name:
            return int(item["id"])
    if items and isinstance(items[0], dict) and "id" in items[0]:
        return int(items[0]["id"])
    raise RuntimeError("installed app not found")


def _wait_for_installed_app_running(executor: TargetExecutor, *, install_id: int, timeout_seconds: int = 240) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        detail = get_installed_app(executor, install_id=install_id)
        status = str(detail.get("status", ""))
        if status == "Running":
            return detail
        if status in {"InstallErr", "UpErr", "Error"}:
            raise RuntimeError(json.dumps(detail, ensure_ascii=False))
        time.sleep(2)
    raise TimeoutError(f"Timed out waiting for install {install_id} to reach Running")


def _wrap(args: argparse.Namespace, *, scope: str, action: str, payload: dict[str, Any] | Any) -> dict[str, Any]:
    return {"command": "onepanel", "env": args.env, "scope": scope, "action": action, "payload": payload}


def _repo_root_for(args: argparse.Namespace) -> Path:
    return Path(getattr(args, "repo_root", ".")).resolve()


def _selector_values(args: argparse.Namespace, payload: dict[str, Any]) -> list[str]:
    selectors: list[str] = []
    for key in ("id", "name", "alias", "info", "key", "type", "status", "domain"):
        value = getattr(args, key, None)
        if value in (None, "", 0):
            continue
        selectors.append(str(value))
    body = payload.get("payload")
    if isinstance(body, dict):
        plan = body.get("plan")
        if isinstance(plan, dict):
            for key in ("object", "mode"):
                value = plan.get(key)
                if value not in (None, ""):
                    selectors.append(str(value))
    deduped: list[str] = []
    seen: set[str] = set()
    for item in selectors:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def _operation_result(action: str, payload: dict[str, Any], *, execute: bool) -> str:
    body = payload.get("payload")
    if action in {"plan", "params-plan"}:
        return "planned"
    if action in {"apply", "install", "params-apply"}:
        return "executed" if execute else "planned"
    if action in {"refresh", "refresh-ledger"}:
        return "refreshed"
    if action == "verify":
        if isinstance(body, dict) and body.get("ok") is False:
            return "verify-failed"
        return "verified"
    return "queried"


def _record_operation(args: argparse.Namespace, payload: dict[str, Any]) -> dict[str, Any]:
    scope = str(payload.get("scope", "") or "root")
    action = str(payload.get("action", "") or "call")
    op_id = next_operation_id(f"onepanel-{scope}")
    execute = bool(getattr(args, "execute", False))
    ledger = append_operation_ledger(
        _repo_root_for(args),
        command="onepanel",
        action=action,
        target=args.env,
        op_id=op_id,
        dry_run=not execute if action in {"apply", "install", "params-apply"} else action in {"plan", "params-plan"},
        result=_operation_result(action, payload, execute=execute),
        details={
            "scope": scope,
            "selectors": _selector_values(args, payload),
        },
    )
    enriched = dict(payload)
    enriched["operation"] = {
        "op_id": op_id,
        "ledger_file": ledger["ledger_file"],
        "result": ledger["entry"]["result"],
    }
    return enriched


def _render_list_preview(items: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    if not items:
        return ["items: 0"]
    lines.append(f"items: {len(items)}")
    for item in items[:3]:
        label = (
            item.get("alias")
            or item.get("name")
            or item.get("service_key")
            or item.get("app_id")
            or item.get("container_name")
            or item.get("id")
            or "item"
        )
        lines.append(f"- {label}")
    return lines


def render_onepanel_text(payload: dict[str, Any]) -> str:
    env = payload.get("env", "unknown")
    scope = payload.get("scope", "root")
    action = payload.get("action", "call")
    lines = [f"onepanel {env} {scope} {action}"]
    body = payload.get("payload")
    if scope == "root":
        hint = payload.get("hint")
        if isinstance(hint, str) and hint:
            lines.append(hint)
        return "\n".join(lines) + "\n"
    if isinstance(body, dict):
        if "counts" in body and isinstance(body["counts"], dict):
            for name, count in body["counts"].items():
                lines.append(f"{name}: {count}")
        elif isinstance(body.get("items"), list):
            lines.extend(_render_list_preview([item for item in body["items"] if isinstance(item, dict)]))
        elif "ok" in body:
            lines.append(f"ok: {'yes' if body.get('ok') else 'no'}")
        elif "plan" in body and isinstance(body["plan"], dict):
            lines.append(f"plan: {body['plan'].get('object', 'object')} / {body['plan'].get('mode', 'mode')}")
        else:
            lines.append("keys: " + ", ".join(sorted(body.keys())[:6]))
    elif body is not None:
        lines.append(str(body))
    operation = payload.get("operation")
    if isinstance(operation, dict) and operation.get("op_id"):
        lines.append(f"op_id: {operation['op_id']}")
    return "\n".join(lines) + "\n"


def classify_onepanel_error(exc: Exception) -> str:
    message = str(exc).lower()
    if isinstance(exc, json.JSONDecodeError):
        return "onepanel.invalid_json"
    if "not found" in message:
        return "onepanel.object_not_found"
    if "must decode to an object" in message:
        return "onepanel.invalid_request"
    if "api command failed" in message or "shell command failed" in message:
        return "onepanel.api_failed"
    if isinstance(exc, ValueError):
        return "onepanel.invalid_request"
    return "onepanel.command_failed"


def onepanel_error_payload(args: argparse.Namespace, exc: Exception) -> dict[str, Any]:
    return {
        "command": "onepanel",
        "env": getattr(args, "env", "unknown"),
        "scope": getattr(args, "onepanel_scope", "root") or "root",
        "action": "error",
        "error": {
            "code": classify_onepanel_error(exc),
            "message": str(exc),
        },
    }


def _handle_panel_action(args: argparse.Namespace) -> dict[str, Any]:
    action = args.onepanel_panel_action
    if action == "refresh-ledger":
        return _wrap(args, scope="panel", action=action, payload=_refresh_ledger_payload(args))
    if action in {"search", "get"}:
        payload = get_panel_summary(_executor_for(args))
        if args.key:
            payload = {args.key: payload.get(args.key)}
        return _wrap(args, scope="panel", action=action, payload=payload)
    if action == "verify":
        summary = get_panel_summary(_executor_for(args))
        ok = True if not args.key else args.key in summary and summary.get(args.key) not in (None, "")
        return _wrap(args, scope="panel", action=action, payload={"ok": ok, "summary": summary})
    plan = plan_panel_setting_update(key=args.key, value=args.value)
    payload: dict[str, Any] = {"plan": {"object": plan.object_name, "mode": plan.mode, "path": plan.path, "body": plan.body}}
    if action == "apply" and args.execute:
        payload["result"] = _executor_for(args).api_request("POST", plan.path, plan.body)
        payload["verified"] = {"ok": True}
    return _wrap(args, scope="panel", action=action, payload=payload)


def _handle_website_action(args: argparse.Namespace) -> dict[str, Any]:
    action = args.onepanel_website_action
    if action == "refresh-ledger":
        return _wrap(args, scope="website", action=action, payload=_refresh_ledger_payload(args))
    executor = _executor_for(args)
    if action == "search":
        return _wrap(args, scope="website", action=action, payload=search_websites(executor, name=args.name, website_group_id=args.group_id))
    if action == "get":
        website_id = _find_website_id(executor, website_id=args.id, name=args.name, alias=args.alias)
        return _wrap(args, scope="website", action=action, payload=get_website(executor, website_id=website_id))
    if action == "verify":
        website_id = _find_website_id(executor, website_id=args.id, name=args.name, alias=args.alias)
        detail = get_website(executor, website_id=website_id)
        ok = True if not args.expected_proxy else detail["website"].get("proxy") == args.expected_proxy
        return _wrap(args, scope="website", action=action, payload={"ok": ok, **detail})
    plan = plan_website_create(
        alias=args.alias,
        domain=args.domain,
        proxy=args.proxy,
        website_group_id=args.group_id,
        website_type=args.website_type,
        remark=args.remark,
        ipv6=_bool_arg(args.ipv6),
    )
    payload: dict[str, Any] = {"plan": {"object": plan.object_name, "mode": plan.mode, "path": plan.path, "body": plan.body}}
    if action == "apply" and args.execute:
        payload["result"] = executor.api_request("POST", plan.path, plan.body)
        payload["verified"] = {"ok": True}
    return _wrap(args, scope="website", action=action, payload=payload)


def _handle_container_action(args: argparse.Namespace) -> dict[str, Any]:
    action = args.onepanel_container_action
    if action == "refresh-ledger":
        return _wrap(args, scope="container", action=action, payload=_refresh_ledger_payload(args))
    executor = _executor_for(args)
    if action == "search":
        payload = search_containers(executor, name=args.name, state=args.state)
        return _wrap(args, scope="container", action=action, payload=payload)
    if action in {"get", "verify"}:
        detail = get_container(executor, name=args.name)
        if action == "get":
            payload = detail
        else:
            ok = True if not getattr(args, "expected_state", "") else str(detail.get("state", "")).lower() == str(args.expected_state).lower()
            payload = {"ok": ok, "container": detail}
        return _wrap(args, scope="container", action=action, payload=payload)
    plan = plan_container_operation(names=[args.name], operation=args.operate)
    payload: dict[str, Any] = {"plan": {"object": plan.object_name, "mode": plan.mode, "path": plan.path, "body": plan.body}}
    if action == "apply" and args.execute:
        payload["result"] = executor.api_request("POST", plan.path, plan.body)
        payload["verified"] = {"ok": True, "container": get_container(executor, name=args.name)}
    return _wrap(args, scope="container", action=action, payload=payload)


def _handle_firewall_action(args: argparse.Namespace) -> dict[str, Any]:
    action = args.onepanel_firewall_action
    if action == "refresh-ledger":
        return _wrap(args, scope="firewall", action=action, payload=_refresh_ledger_payload(args))
    executor = _executor_for(args)
    if action == "search":
        payload = search_firewall_rules(
            executor,
            rule_type=args.type,
            info=args.info,
            status=args.status,
            strategy=args.strategy,
        )
        return _wrap(args, scope="firewall", action=action, payload=payload)
    if action == "get":
        return _wrap(args, scope="firewall", action=action, payload=load_firewall_base(executor, name=args.tab))
    if action == "verify":
        base = load_firewall_base(executor, name=args.tab)
        ok = True
        if getattr(args, "expected_active", ""):
            ok = ok and bool(base.get("isActive")) == _bool_arg(args.expected_active)
        if getattr(args, "expected_name", ""):
            ok = ok and str(base.get("name", "")) == str(args.expected_name)
        return _wrap(args, scope="firewall", action=action, payload={"ok": ok, "firewall": base})
    plan = plan_firewall_operation(operation=args.operation, with_docker_restart=bool(args.with_docker_restart))
    payload: dict[str, Any] = {"plan": {"object": plan.object_name, "mode": plan.mode, "path": plan.path, "body": plan.body}}
    if action == "apply" and args.execute:
        payload["result"] = executor.api_request("POST", plan.path, plan.body)
        payload["verified"] = {"ok": True, "firewall": load_firewall_base(executor, name="port")}
    return _wrap(args, scope="firewall", action=action, payload=payload)


def _handle_cronjob_action(args: argparse.Namespace) -> dict[str, Any]:
    action = args.onepanel_cronjob_action
    if action == "refresh-ledger":
        return _wrap(args, scope="cronjob", action=action, payload=_refresh_ledger_payload(args))
    executor = _executor_for(args)
    if action == "search":
        return _wrap(args, scope="cronjob", action=action, payload=search_cronjobs(executor, info=args.info))
    if action == "get":
        return _wrap(args, scope="cronjob", action=action, payload=load_cronjob(executor, cronjob_id=args.id))
    if action == "verify":
        detail = load_cronjob(executor, cronjob_id=args.id)
        ok = True if not args.expected_status else str(detail.get("status", "")) == args.expected_status
        return _wrap(args, scope="cronjob", action=action, payload={"ok": ok, "cronjob": detail})
    body = json.loads(args.body_json)
    if not isinstance(body, dict):
        raise ValueError("--body-json must decode to an object")
    plan = plan_cronjob_operation(mode=args.mode, body=body)
    payload: dict[str, Any] = {"plan": {"object": plan.object_name, "mode": plan.mode, "path": plan.path, "body": plan.body}}
    if action == "apply" and args.execute:
        payload["result"] = executor.api_request("POST", plan.path, plan.body)
        payload["verified"] = {"ok": True}
    return _wrap(args, scope="cronjob", action=action, payload=payload)


def _handle_app_action(args: argparse.Namespace) -> dict[str, Any]:
    action = args.onepanel_app_action
    if action == "refresh-ledger":
        return _wrap(args, scope="app", action=action, payload=_refresh_ledger_payload(args))
    executor = _executor_for(args)
    if action == "search":
        payload = search_installed_apps(executor, name=args.name, app_type=args.type)
        return _wrap(args, scope="app", action=action, payload=payload)
    if action == "catalog-get":
        payload = {"app": get_app_catalog(executor, app_key=args.app)}
        if args.version:
            payload["detail"] = get_app_catalog_detail(
                executor,
                app_id=int(payload["app"]["id"]),
                version=args.version,
                app_type=str(payload["app"]["type"]),
            )
        return _wrap(args, scope="app", action=action, payload=payload)
    if action == "install":
        app_meta = get_app_catalog(executor, app_key=args.app)
        app_detail = get_app_catalog_detail(
            executor,
            app_id=int(app_meta["id"]),
            version=args.version,
            app_type=str(app_meta["type"]),
        )
        plan = plan_app_install(
            app_key=args.app,
            app_type=str(app_meta["type"]),
            detail=app_detail,
            name=args.name,
            container_name=args.container,
            raw_params=args.param,
            pull_image=bool(args.pull_image),
            specify_ip=args.specify_ip or "",
            restart_policy=args.restart_policy,
        )
        payload = {"plan": {"object": plan.object_name, "mode": plan.mode, "path": plan.path, "body": plan.body}}
        if args.execute:
            result = executor.api_request("POST", plan.path, plan.body)
            payload["result"] = result
            install_id = result.get("id") if isinstance(result, dict) else None
            if install_id is not None:
                detail = (
                    _wait_for_installed_app_running(executor, install_id=int(install_id))
                    if getattr(args, "wait", False)
                    else get_installed_app(executor, install_id=int(install_id))
                    )
                payload["verified"] = {"ok": bool(detail.get("id")), "app": detail}
        return _wrap(args, scope="app", action=action, payload=payload)
    install_id = _find_installed_app_id(executor, install_id=getattr(args, "id", None), name=getattr(args, "name", ""), app_type=getattr(args, "type", ""))
    if action == "get":
        payload = get_installed_app(executor, install_id=install_id)
        return _wrap(args, scope="app", action=action, payload=payload)
    if action == "verify":
        detail = get_installed_app(executor, install_id=install_id)
        ok = True if not getattr(args, "expected_status", "") else str(detail.get("status", "")) == str(args.expected_status)
        return _wrap(args, scope="app", action=action, payload={"ok": ok, "app": detail})
    if action in {"params-plan", "params-apply"}:
        params = json.loads(args.params_json)
        if not isinstance(params, dict):
            raise ValueError("--params-json must decode to an object")
        plan = plan_installed_app_params_update(install_id=install_id, params=params)
        payload = {"plan": {"object": plan.object_name, "mode": plan.mode, "path": plan.path, "body": plan.body}}
        if action == "params-apply" and args.execute:
            payload["result"] = executor.api_request("POST", plan.path, plan.body)
            detail = get_installed_app(executor, install_id=install_id)
            payload["verified"] = {"ok": bool(detail.get("id")), "app": detail}
        return _wrap(args, scope="app", action=action, payload=payload)
    plan = plan_installed_app_operation(install_id=install_id, operate=args.operate)
    payload: dict[str, Any] = {"plan": {"object": plan.object_name, "mode": plan.mode, "path": plan.path, "body": plan.body}}
    if action == "apply" and args.execute:
        payload["result"] = executor.api_request("POST", plan.path, plan.body)
        detail = get_installed_app(executor, install_id=install_id)
        payload["verified"] = {"ok": True, "app": detail}
    return _wrap(args, scope="app", action=action, payload=payload)


def _handle_project_action(args: argparse.Namespace) -> dict[str, Any]:
    action = args.onepanel_project_action
    if action == "refresh-ledger":
        return _wrap(args, scope="project", action=action, payload=_refresh_ledger_payload(args))
    executor = _executor_for(args)
    if action == "search":
        payload = search_compose_projects(executor, info=args.info)
        return _wrap(args, scope="project", action=action, payload=payload)
    detail = get_compose_project(executor, name=args.name)
    if action == "get":
        return _wrap(args, scope="project", action=action, payload=detail)
    if action == "verify":
        ok = True
        expected_status = getattr(args, "expected_status", "")
        expected_running_count = getattr(args, "expected_running_count", None)
        if expected_status:
            ok = ok and str(detail.get("status", "")) == str(expected_status)
        if expected_running_count is not None:
            ok = ok and int(detail.get("runningCount", 0)) == expected_running_count
        return _wrap(args, scope="project", action=action, payload={"ok": ok, "project": detail})
    plan = plan_compose_project_operation(name=args.name, operation=args.operate, with_file=bool(args.with_file), force=bool(args.force))
    payload: dict[str, Any] = {"plan": {"object": plan.object_name, "mode": plan.mode, "path": plan.path, "body": plan.body}}
    if action == "apply" and args.execute:
        payload["result"] = executor.api_request("POST", plan.path, plan.body)
        payload["verified"] = {"ok": True, "project": get_compose_project(executor, name=args.name)}
    return _wrap(args, scope="project", action=action, payload=payload)


def _handle_task_action(args: argparse.Namespace) -> dict[str, Any]:
    action = args.onepanel_task_action
    if action == "refresh-ledger":
        return _wrap(args, scope="task", action=action, payload=_refresh_ledger_payload(args))
    executor = _executor_for(args)
    if action == "search":
        payload = search_tasks(executor, task_type=args.type, status=args.status)
    else:
        count = get_task_count(executor)
        if action == "verify" and args.expected_count is not None:
            payload = {"ok": int(count.get("executing", 0)) == args.expected_count, "task_center": count}
        else:
            payload = count
    return _wrap(args, scope="task", action=action, payload=payload)


def _handle_ledger_action(args: argparse.Namespace) -> dict[str, Any]:
    return _wrap(args, scope="ledger", action="refresh", payload=_refresh_ledger_payload(args))


def _handle_suite_action(args: argparse.Namespace) -> dict[str, Any]:
    selectors = resolve_suite_targets(
        profile=args.profile,
        env=args.env,
        website_alias=args.website_alias,
        container_name=args.container_name,
        project_name=args.project_name,
        cronjob_id=args.cronjob_id,
        cronjob_name=args.cronjob_name,
        app_name=args.app_name,
        firewall_tab=args.firewall_tab,
    )
    payload = run_verification_suite(
        _executor_for(args),
        profile=args.profile,
        env=args.env,
        repo_root=Path(args.repo_root).resolve(),
        write_report=bool(args.write_report),
        website_alias=selectors["website_alias"],
        container_name=selectors["container_name"],
        project_name=selectors["project_name"],
        cronjob_id=selectors["cronjob_id"],
        cronjob_name=selectors["cronjob_name"],
        app_name=selectors["app_name"],
        firewall_tab=selectors["firewall_tab"],
    )
    return _wrap(args, scope="suite", action=args.onepanel_suite_action, payload=payload)


def _handle_fixture_action(args: argparse.Namespace) -> dict[str, Any]:
    spec = resolve_fixture_spec(args.profile, env=args.env)
    executor = _executor_for(args)
    action = args.onepanel_fixture_action
    if action == "plan":
        payload = plan_fixture(executor, spec)
    elif action == "apply":
        payload = apply_fixture(executor, spec, execute=bool(args.execute))
    else:
        payload = cleanup_fixture(executor, spec, execute=bool(args.execute))
    return _wrap(args, scope="fixture", action=action, payload=payload)


def _handle_ingress_ensure(args: argparse.Namespace) -> dict[str, Any]:
    payload = command_ensure_public_ingress(args)
    return _wrap(args, scope="ingress", action="ensure-cloudflare-dns01", payload=payload)


def onepanel_skeleton(env: str) -> dict[str, Any]:
    return {
        "command": "onepanel",
        "env": env,
        "supported_targets": list(supported_targets()),
        "status": "skeleton",
        "hint": "优先使用 uv run python -m agentplane.cli onepanel <panel|firewall|cronjob|task> ...",
    }


def handle_onepanel_command(args: argparse.Namespace) -> dict[str, Any]:
    handler = getattr(args, "onepanel_handler", None)
    if callable(handler):
        return _record_operation(args, handler(args))
    return onepanel_skeleton(args.env)
