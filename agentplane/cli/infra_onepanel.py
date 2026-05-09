from __future__ import annotations

import argparse
from typing import Any

from agentplane.domain.infra.onepanel import (
    handle_cronjob_action,
    handle_firewall_action,
    handle_panel_action,
    handle_task_action,
    onepanel_skeleton,
    record_onepanel_operation,
)


def add_onepanel_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    onepanel_parser = subparsers.add_parser("onepanel", help=argparse.SUPPRESS)
    onepanel_parser.add_argument("--env", default="wsl", choices=["wsl", "prod0-main"], help="目标环境")
    onepanel_parser.add_argument("--env-file", help="覆盖选定环境的 1Panel API env 文件")
    onepanel_parser.add_argument("--json", action="store_true", help="输出结构化 JSON")
    onepanel_subparsers = onepanel_parser.add_subparsers(dest="onepanel_scope")

    _add_panel_parser(onepanel_subparsers)
    _add_firewall_parser(onepanel_subparsers)
    _add_cronjob_parser(onepanel_subparsers)
    _add_task_parser(onepanel_subparsers)


def _add_refresh_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    handler: Any,
    help_text: str,
) -> None:
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
        sub.set_defaults(onepanel_handler=handle_panel_action)
    for action in ("plan", "apply"):
        sub = panel_subparsers.add_parser(action, help=f"{action} panel setting update")
        sub.add_argument("--key", required=True, help="设置项 key")
        sub.add_argument("--value", required=True, help="设置项值")
        _add_execute_args(sub)
        sub.set_defaults(onepanel_handler=handle_panel_action)
    _add_refresh_parser(panel_subparsers, handler=handle_panel_action, help_text="刷新对象台帐")


def _add_firewall_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("firewall", help="防火墙对象")
    firewall_subparsers = parser.add_subparsers(dest="onepanel_firewall_action", required=True)
    search = firewall_subparsers.add_parser("search", help="搜索 firewall rules")
    search.add_argument("--type", default="port", choices=("port", "address", "forward"), help="规则类型")
    search.add_argument("--info", default="", help="搜索关键字")
    search.add_argument("--status", default="", help="状态过滤")
    search.add_argument("--strategy", default="", help="策略过滤")
    search.set_defaults(onepanel_handler=handle_firewall_action)
    get = firewall_subparsers.add_parser("get", help="读取 firewall base")
    get.add_argument("--tab", default="port", choices=("port", "address", "forward"), help="firewall tab")
    get.set_defaults(onepanel_handler=handle_firewall_action)
    verify = firewall_subparsers.add_parser("verify", help="校验 firewall")
    verify.add_argument("--tab", default="port", choices=("port", "address", "forward"), help="firewall tab")
    verify.add_argument("--expected-active", default="", help="期望是否激活 true/false")
    verify.add_argument("--expected-name", default="", help="期望防火墙名称")
    verify.set_defaults(onepanel_handler=handle_firewall_action)
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
        sub.set_defaults(onepanel_handler=handle_firewall_action)
    _add_refresh_parser(firewall_subparsers, handler=handle_firewall_action, help_text="刷新对象台帐")


def _add_cronjob_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("cronjob", help="1Panel 计划任务对象")
    cron_subparsers = parser.add_subparsers(dest="onepanel_cronjob_action", required=True)
    search = cron_subparsers.add_parser("search", help="搜索计划任务")
    search.add_argument("--info", default="", help="搜索关键字")
    search.set_defaults(onepanel_handler=handle_cronjob_action)
    get = cron_subparsers.add_parser("get", help="读取计划任务")
    get.add_argument("--id", required=True, type=int, help="计划任务 ID")
    get.set_defaults(onepanel_handler=handle_cronjob_action)
    for action in ("plan", "apply"):
        sub = cron_subparsers.add_parser(action, help=f"{action} cronjob mutation")
        sub.add_argument("--mode", required=True, choices=("create", "update", "handle", "status"), help="操作模式")
        sub.add_argument("--body-json", required=True, help="请求体 JSON")
        _add_execute_args(sub)
        sub.set_defaults(onepanel_handler=handle_cronjob_action)
    verify = cron_subparsers.add_parser("verify", help="校验计划任务")
    verify.add_argument("--id", required=True, type=int, help="计划任务 ID")
    verify.add_argument("--expected-status", default="", help="期望状态")
    verify.set_defaults(onepanel_handler=handle_cronjob_action)
    _add_refresh_parser(cron_subparsers, handler=handle_cronjob_action, help_text="刷新对象台帐")


def _add_task_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("task", help="1Panel 任务中心对象")
    task_subparsers = parser.add_subparsers(dest="onepanel_task_action", required=True)
    search = task_subparsers.add_parser("search", help="搜索任务")
    search.add_argument("--type", default="", help="任务类型")
    search.add_argument("--status", default="", help="任务状态")
    search.set_defaults(onepanel_handler=handle_task_action)
    get = task_subparsers.add_parser("get", help="读取任务概况")
    get.set_defaults(onepanel_handler=handle_task_action)
    verify = task_subparsers.add_parser("verify", help="校验执行中的任务数量")
    verify.add_argument("--expected-count", type=int, default=None, help="期望 executing 数量")
    verify.set_defaults(onepanel_handler=handle_task_action)
    _add_refresh_parser(task_subparsers, handler=handle_task_action, help_text="刷新对象台帐")


def handle_onepanel_command(args: argparse.Namespace) -> dict[str, Any]:
    import sys

    sys.stderr.write("[warn] onepanel 是 provider 调试入口，正式操作请使用 ingress / service / app / infra 域。\n")
    handler = getattr(args, "onepanel_handler", None)
    if callable(handler):
        return record_onepanel_operation(args, handler(args))
    return onepanel_skeleton(args.env)
