from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from agentplane.cli.operations import append_operation_ledger, next_operation_id
from agentplane.providers.onepanel_ledgers import refresh_onepanel_ledgers
from agentplane.providers.onepanel_objects import (
    get_panel_summary,
    get_task_count,
    load_cronjob,
    load_firewall_base,
    onepanel_target_executor,
    plan_cronjob_operation,
    plan_firewall_operation,
    plan_panel_setting_update,
    search_cronjobs,
    search_firewall_rules,
    search_tasks,
    supported_onepanel_targets,
)
from agentplane.runtime.redaction import redact_sensitive_value


def add_onepanel_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    onepanel_parser = subparsers.add_parser("onepanel", help=argparse.SUPPRESS)
    onepanel_parser.add_argument("--env", default="wsl", choices=supported_onepanel_targets(), help="目标环境")
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
        sub.set_defaults(onepanel_handler=_handle_panel_action)
    for action in ("plan", "apply"):
        sub = panel_subparsers.add_parser(action, help=f"{action} panel setting update")
        sub.add_argument("--key", required=True, help="设置项 key")
        sub.add_argument("--value", required=True, help="设置项值")
        _add_execute_args(sub)
        sub.set_defaults(onepanel_handler=_handle_panel_action)
    _add_refresh_parser(panel_subparsers, handler=_handle_panel_action, help_text="刷新对象台帐")


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


def _executor_for(args: argparse.Namespace) -> object:
    return onepanel_target_executor(args.env, getattr(args, "env_file", None))


def _refresh_ledger_payload(args: argparse.Namespace) -> dict[str, Any]:
    return refresh_onepanel_ledgers(
        Path(getattr(args, "repo_root", ".")).resolve(),
        args.env,
        write=bool(getattr(args, "write", False)),
    )


def _bool_arg(raw: str) -> bool:
    return str(raw).strip().lower() not in {"0", "false", "no", "off"}


def _wrap(args: argparse.Namespace, *, scope: str, action: str, payload: dict[str, Any] | Any) -> dict[str, Any]:
    return {"command": "onepanel", "env": args.env, "scope": scope, "action": action, "payload": redact_sensitive_value(payload)}


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
    if action == "plan":
        return "planned"
    if action == "apply":
        return "executed" if execute else "planned"
    if action == "refresh-ledger":
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
        dry_run=not execute if action == "apply" else action == "plan",
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
        label = item.get("alias") or item.get("name") or item.get("id") or "item"
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


def onepanel_skeleton(env: str) -> dict[str, Any]:
    return {
        "command": "onepanel",
        "env": env,
        "supported_targets": list(supported_onepanel_targets()),
        "status": "skeleton",
        "hint": "优先使用 uv run python -m agentplane.cli onepanel <panel|firewall|cronjob|task> ...",
    }


def handle_onepanel_command(args: argparse.Namespace) -> dict[str, Any]:
    import sys

    sys.stderr.write(
        "[warn] onepanel 是 provider 调试入口，正式操作请使用 ingress / service / app / infra 域。\n"
    )
    handler = getattr(args, "onepanel_handler", None)
    if callable(handler):
        return _record_operation(args, handler(args))
    return onepanel_skeleton(args.env)
