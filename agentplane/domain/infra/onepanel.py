from __future__ import annotations

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


def _executor_for(args: object) -> object:
    return onepanel_target_executor(args.env, getattr(args, "env_file", None))


def _refresh_ledger_payload(args: object) -> dict[str, Any]:
    return refresh_onepanel_ledgers(
        Path(getattr(args, "repo_root", ".")).resolve(),
        args.env,
        write=bool(getattr(args, "write", False)),
    )


def _bool_arg(raw: str) -> bool:
    return str(raw).strip().lower() not in {"0", "false", "no", "off"}


def _wrap(args: object, *, scope: str, action: str, payload: dict[str, Any] | Any) -> dict[str, Any]:
    return {
        "command": "onepanel",
        "env": args.env,
        "scope": scope,
        "action": action,
        "payload": redact_sensitive_value(payload),
    }


def _repo_root_for(args: object) -> Path:
    return Path(getattr(args, "repo_root", ".")).resolve()


def _selector_values(args: object, payload: dict[str, Any]) -> list[str]:
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


def _record_operation(args: object, payload: dict[str, Any]) -> dict[str, Any]:
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


def onepanel_error_payload(args: object, exc: Exception) -> dict[str, Any]:
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


def handle_panel_action(args: object) -> dict[str, Any]:
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
    payload: dict[str, Any] = {
        "plan": {"object": plan.object_name, "mode": plan.mode, "path": plan.path, "body": plan.body}
    }
    if action == "apply" and args.execute:
        payload["result"] = _executor_for(args).api_request("POST", plan.path, plan.body)
        payload["verified"] = {"ok": True}
    return _wrap(args, scope="panel", action=action, payload=payload)


def handle_firewall_action(args: object) -> dict[str, Any]:
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
    payload: dict[str, Any] = {
        "plan": {"object": plan.object_name, "mode": plan.mode, "path": plan.path, "body": plan.body}
    }
    if action == "apply" and args.execute:
        payload["result"] = executor.api_request("POST", plan.path, plan.body)
        payload["verified"] = {"ok": True, "firewall": load_firewall_base(executor, name="port")}
    return _wrap(args, scope="firewall", action=action, payload=payload)


def handle_cronjob_action(args: object) -> dict[str, Any]:
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
    payload: dict[str, Any] = {
        "plan": {"object": plan.object_name, "mode": plan.mode, "path": plan.path, "body": plan.body}
    }
    if action == "apply" and args.execute:
        payload["result"] = executor.api_request("POST", plan.path, plan.body)
        payload["verified"] = {"ok": True}
    return _wrap(args, scope="cronjob", action=action, payload=payload)


def handle_task_action(args: object) -> dict[str, Any]:
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


# Public alias for CLI layer
record_onepanel_operation = _record_operation
