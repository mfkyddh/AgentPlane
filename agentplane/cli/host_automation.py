from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from agentplane.scripts.automation.backup_secrets_r2 import DEFAULT_ENV_FILE, load_config, run_backup
from agentplane.scripts.automation.sync_zzz_skills import run_sync
from agentplane.scripts.onepanel.env_targets import get_target
from agentplane.scripts.onepanel.executor import TargetExecutor
from agentplane.scripts.onepanel.object_api import load_cronjob, search_cronjobs


SUPPORTED_AUTOMATION_TARGETS = ("wsl", "prod0-main", "prod2-main")
SUPPORTED_AUTOMATION_OPERATIONS = ("reconcile", "run", "trigger")


Runner = Callable[[Path, dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class HostAutomationDefinition:
    name: str
    runner: Runner


def _run_sync_zzz_skills(repo_root: Path, automation: dict[str, Any]) -> dict[str, Any]:
    return run_sync(
        source_root=_resolve_task_path(repo_root, automation["source_root"]),
        target_repo=_resolve_task_path(repo_root, automation["target_repo"]),
        branch=str(automation.get("target_branch", "main")),
    )


def _run_backup_secrets(repo_root: Path, automation: dict[str, Any]) -> dict[str, Any]:
    env_file = _resolve_task_path(repo_root, str(automation.get("env_file", DEFAULT_ENV_FILE)))
    return run_backup(load_config(env_file))


AUTOMATION_DEFINITIONS: dict[str, HostAutomationDefinition] = {
    "wsl-zzz-skills-sync": HostAutomationDefinition(name="wsl-zzz-skills-sync", runner=_run_sync_zzz_skills),
    "wsl-agentplane-secrets-backup": HostAutomationDefinition(name="wsl-agentplane-secrets-backup", runner=_run_backup_secrets),
}


def _inventory_file(repo_root: Path, target: str) -> Path:
    return repo_root / "inventory" / "servers" / target / "inventory.json"


def _require_supported_target(target: str) -> None:
    if target not in SUPPORTED_AUTOMATION_TARGETS:
        raise ValueError(f"unsupported automation target: {target}")


def _load_inventory_payload(repo_root: Path, target: str) -> dict[str, Any]:
    _require_supported_target(target)
    inventory_file = _inventory_file(repo_root, target)
    if not inventory_file.is_file():
        return {}
    payload = json.loads(inventory_file.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"invalid inventory payload: {inventory_file}")
    return payload


def _load_declared_automations(repo_root: Path, target: str) -> list[dict[str, Any]]:
    payload = _load_inventory_payload(repo_root, target)
    automations = payload.get("automations")
    if not isinstance(automations, list):
        return []
    return [item for item in automations if isinstance(item, dict)]


def _find_declared_automation(repo_root: Path, target: str, name: str) -> dict[str, Any]:
    for item in _load_declared_automations(repo_root, target):
        if str(item.get("name", "")) == name:
            return item
    raise ValueError(f"automation not found: {name}")


def _resolve_task_path(repo_root: Path, raw: str) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path
    return (repo_root / path).resolve()


def _task_run_command(automation: dict[str, Any]) -> str:
    cwd = str(automation.get("cwd", "")).strip()
    command = str(automation.get("command", "")).strip()
    if not command:
        raise ValueError(f"automation command missing: {automation.get('name', 'unknown')}")
    return f"cd {cwd} && {command}" if cwd else command


def _supported_operations(automation: dict[str, Any]) -> list[str]:
    operations = ["reconcile"]
    if automation.get("name") in AUTOMATION_DEFINITIONS:
        operations.append("run")
    if str(automation.get("controller", "")) == "1panel-cronjob":
        operations.append("trigger")
    return operations


def _normalize_automation(target: str, automation: dict[str, Any]) -> dict[str, Any]:
    payload = dict(automation)
    payload["target"] = target
    payload["supported"] = automation.get("name") in AUTOMATION_DEFINITIONS
    payload["supported_operations"] = _supported_operations(automation)
    payload["run_command"] = _task_run_command(automation)
    return payload


def _executor_for_target(target: str, env_file: str | None = None) -> TargetExecutor:
    _require_supported_target(target)
    return TargetExecutor(get_target(target, env_file))


def _search_live_cronjob(executor: TargetExecutor, name: str) -> dict[str, Any] | None:
    payload = search_cronjobs(executor, info=name, page_size=50)
    items = payload.get("items")
    if not isinstance(items, list):
        return None
    for item in items:
        if isinstance(item, dict) and str(item.get("name", "")) == name:
            cronjob_id = int(item.get("id") or 0)
            if cronjob_id <= 0:
                return item
            detail = load_cronjob(executor, cronjob_id=cronjob_id)
            if isinstance(detail, dict):
                detail.setdefault("id", cronjob_id)
            return detail
    return None


def _default_group_id(executor: TargetExecutor) -> int:
    payload = search_cronjobs(executor, info="", page_size=50)
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        return 0
    first = items[0]
    if not isinstance(first, dict):
        return 0
    return int(first.get("groupID") or 0)


def _desired_cronjob_payload(automation: dict[str, Any], *, group_id: int, existing: dict[str, Any] | None = None) -> dict[str, Any]:
    existing = existing or {}
    payload = {
        "name": str(automation["name"]),
        "type": "shell",
        "groupID": group_id,
        "specCustom": True,
        "spec": str(automation.get("spec", "")),
        "executor": "bash",
        "scriptMode": "input",
        "script": _task_run_command(automation),
        "command": "",
        "containerName": "",
        "user": "root",
        "scriptID": 0,
        "appID": "",
        "website": "",
        "exclusionRules": "",
        "dbType": "",
        "dbName": "",
        "url": "",
        "isDir": False,
        "sourceDir": "",
        "snapshotRule": {"withImage": False, "ignoreAppIDs": []},
        "sourceAccountIDs": "",
        "downloadAccountID": 0,
        "retainCopies": int(existing.get("retainCopies", 7) or 7),
        "retryTimes": int(existing.get("retryTimes", 3) or 3),
        "timeout": int(existing.get("timeout", 3600) or 3600),
        "ignoreErr": bool(existing.get("ignoreErr", False)),
        "secret": str(existing.get("secret", "")),
        "args": str(existing.get("args", "")),
        "alertCount": int(existing.get("alertCount", 0) or 0),
        "alertTitle": "",
        "alertMethod": "",
    }
    if existing.get("id") is not None:
        payload["id"] = int(existing["id"])
    return payload


def _cronjob_drift(existing: dict[str, Any], desired: dict[str, Any]) -> dict[str, dict[str, Any]]:
    drift: dict[str, dict[str, Any]] = {}
    for field in ("name", "spec", "executor", "scriptMode", "script", "type", "user", "groupID"):
        existing_value = existing.get(field)
        desired_value = desired.get(field)
        if existing_value != desired_value:
            drift[field] = {"actual": existing_value, "expected": desired_value}
    return drift


def _reconcile_actions(automation: dict[str, Any], executor: TargetExecutor) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    live = _search_live_cronjob(executor, str(automation["name"]))
    if live is None:
        group_id = _default_group_id(executor)
        desired = _desired_cronjob_payload(automation, group_id=group_id)
        return (
            [
                {
                    "object": "cronjob",
                    "mode": "create",
                    "path": "/api/v2/cronjobs",
                    "body": desired,
                    "reason": "missing cronjob",
                }
            ],
            None,
        )

    group_id = int(live.get("groupID") or 0)
    desired = _desired_cronjob_payload(automation, group_id=group_id, existing=live)
    actions: list[dict[str, Any]] = []
    drift = _cronjob_drift(live, desired)
    if drift:
        actions.append(
            {
                "object": "cronjob",
                "mode": "update",
                "path": "/api/v2/cronjobs/update",
                "body": desired,
                "drift": drift,
            }
        )
    if str(live.get("status", "")) != "Enable":
        actions.append(
            {
                "object": "cronjob",
                "mode": "status",
                "path": "/api/v2/cronjobs/status",
                "body": {"id": int(live["id"]), "status": "Enable"},
                "reason": "cronjob disabled",
            }
        )
    return actions, live


def search_host_automations(repo_root: Path, target: str) -> dict[str, Any]:
    items = [_normalize_automation(target, item) for item in _load_declared_automations(repo_root, target)]
    return {"items": items}


def get_host_automation(repo_root: Path, target: str, name: str) -> dict[str, Any]:
    automation = _find_declared_automation(repo_root, target, name)
    return {"automation": _normalize_automation(target, automation)}


def verify_host_automation(
    repo_root: Path,
    target: str,
    name: str,
    *,
    executor: TargetExecutor | None = None,
    env_file: str | None = None,
) -> dict[str, Any]:
    automation = _find_declared_automation(repo_root, target, name)
    normalized = _normalize_automation(target, automation)
    checks: dict[str, Any] = {
        "declared": True,
        "supported": normalized["supported"],
        "controller": str(automation.get("controller", "")) == "1panel-cronjob",
    }
    if not checks["controller"]:
        return {"ok": False, "automation": normalized, "checks": checks, "live": None}

    resolved_executor = executor or _executor_for_target(target, env_file)
    live = _search_live_cronjob(resolved_executor, name)
    checks["exists"] = live is not None
    if live is None:
        return {"ok": False, "automation": normalized, "checks": checks, "live": None}

    desired = _desired_cronjob_payload(
        automation,
        group_id=int(live.get("groupID") or 0),
        existing=live,
    )
    checks["spec_match"] = live.get("spec") == desired["spec"]
    checks["script_match"] = live.get("script") == desired["script"]
    checks["enabled"] = str(live.get("status", "")) == "Enable"
    ok = bool(checks["supported"] and checks["spec_match"] and checks["script_match"] and checks["enabled"])
    return {"ok": ok, "automation": normalized, "checks": checks, "live": live}


def plan_host_automation(
    repo_root: Path,
    target: str,
    name: str,
    operation: str,
    *,
    executor: TargetExecutor | None = None,
    env_file: str | None = None,
) -> dict[str, Any]:
    automation = _find_declared_automation(repo_root, target, name)
    normalized = _normalize_automation(target, automation)
    if operation not in SUPPORTED_AUTOMATION_OPERATIONS:
        raise ValueError(f"unsupported automation operation: {operation}")
    if operation not in normalized["supported_operations"]:
        raise ValueError(f"unsupported automation operation for {name}: {operation}")

    if operation == "run":
        return {
            "ok": True,
            "operation": operation,
            "automation": normalized,
            "actions": [{"object": "automation", "mode": "run", "runner": name}],
        }

    resolved_executor = executor or _executor_for_target(target, env_file)
    if operation == "trigger":
        live = _search_live_cronjob(resolved_executor, name)
        if live is None:
            return {
                "ok": False,
                "operation": operation,
                "automation": normalized,
                "actions": [],
                "reason": "cronjob missing",
            }
        return {
            "ok": True,
            "operation": operation,
            "automation": normalized,
            "actions": [{"object": "cronjob", "mode": "handle", "path": "/api/v2/cronjobs/handle", "body": {"id": int(live["id"])}}],
        }

    actions, live = _reconcile_actions(automation, resolved_executor)
    return {
        "ok": True,
        "operation": operation,
        "automation": normalized,
        "actions": actions,
        "live": live,
        "noop": not actions,
    }


def _run_task(repo_root: Path, automation: dict[str, Any]) -> dict[str, Any]:
    definition = AUTOMATION_DEFINITIONS.get(str(automation["name"]))
    if definition is None:
        raise ValueError(f"unsupported automation runner: {automation['name']}")
    return definition.runner(repo_root, automation)


def apply_host_automation(
    repo_root: Path,
    target: str,
    name: str,
    operation: str,
    *,
    execute: bool,
    executor: TargetExecutor | None = None,
    env_file: str | None = None,
) -> dict[str, Any]:
    plan = plan_host_automation(repo_root, target, name, operation, executor=executor, env_file=env_file)
    if not execute:
        return plan

    automation = _find_declared_automation(repo_root, target, name)
    normalized = _normalize_automation(target, automation)

    if operation == "run":
        result = _run_task(repo_root, automation)
        status = result.get("status")
        ok = not (isinstance(status, str) and status.startswith("failed_"))
        return {
            "ok": ok,
            "operation": operation,
            "automation": normalized,
            "actions": plan["actions"],
            "result": result,
        }

    resolved_executor = executor or _executor_for_target(target, env_file)
    results: list[dict[str, Any]] = []
    for action in plan["actions"]:
        results.append(
            {
                "mode": action["mode"],
                "result": resolved_executor.api_request("POST", action["path"], action["body"]),
            }
        )

    if operation == "trigger":
        return {
            "ok": True,
            "operation": operation,
            "automation": normalized,
            "actions": plan["actions"],
            "results": results,
            "verified": {"ok": True},
        }

    verified = verify_host_automation(repo_root, target, name, executor=resolved_executor)
    return {
        "ok": bool(verified.get("ok")),
        "operation": operation,
        "automation": normalized,
        "actions": plan["actions"],
        "results": results,
        "verified": verified,
    }
