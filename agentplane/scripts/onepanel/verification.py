#!/usr/bin/env python3
"""Reusable onepanel verification suites built on object API helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .object_api import (
    find_cronjob_id,
    find_website_id,
    get_compose_project,
    get_container,
    get_ingress,
    get_installed_app,
    get_panel_summary,
    get_task_count,
    load_cronjob,
    load_firewall_base,
    search_installed_apps,
)
from .redaction import scrub_persisted_payload


def _website_id(executor: Any, alias: str) -> int:
    return find_website_id(executor, alias=alias)


def _app_id(executor: Any, name: str) -> int:
    payload = search_installed_apps(executor, name=name)
    items = payload.get("items")
    if not isinstance(items, list):
        raise RuntimeError("installed app search returned no items")
    for item in items:
        if isinstance(item, dict) and (item.get("name") == name or item.get("appKey") == name):
            return int(item["id"])
    raise RuntimeError(f"installed app not found: {name}")


def _check(scope: str, ok: bool, payload: dict[str, Any]) -> dict[str, Any]:
    return {"scope": scope, "ok": ok, "payload": payload}


def _error_payload(exc: Exception) -> dict[str, Any]:
    message = str(exc)
    try:
        parsed = json.loads(message)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        return {"error": parsed}
    return {"error": {"message": message}}


def _run_check(scope: str, getter: Any, predicate: Any) -> dict[str, Any]:
    try:
        payload = getter()
    except Exception as exc:
        return _check(scope, False, _error_payload(exc))
    return _check(scope, bool(predicate(payload)), payload)


def _report_paths(repo_root: Path, env: str, profile: str) -> tuple[Path, Path]:
    ledger_root = repo_root / "inventory" / "servers" / env / "ledgers"
    stem = f"verification-{profile}"
    return ledger_root / f"{stem}.json", ledger_root / f"{stem}.md"


def _render_report_markdown(payload: dict[str, Any]) -> str:
    lines = [f"# verification {payload['profile']}", ""]
    lines.append(f"- env: `{payload['env']}`")
    lines.append(f"- ok: `{'yes' if payload['ok'] else 'no'}`")
    lines.append("")
    lines.append("## checks")
    lines.append("")
    for item in payload["checks"]:
        lines.append(f"- `{item['scope']}`: `{'ok' if item['ok'] else 'fail'}`")
    return "\n".join(lines) + "\n"


def _write_report(repo_root: Path, env: str, profile: str, payload: dict[str, Any]) -> dict[str, Any]:
    json_path, md_path = _report_paths(repo_root, env, profile)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    persisted_payload = scrub_persisted_payload(payload)
    json_path.write_text(json.dumps(persisted_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(_render_report_markdown(payload), encoding="utf-8")
    return {
        "profile": profile,
        "json_file": str(json_path),
        "markdown_file": str(md_path),
    }


def run_verification_suite(
    executor: Any,
    *,
    profile: str,
    env: str = "wsl",
    repo_root: Path | None = None,
    write_report: bool = False,
    website_alias: str = "",
    container_name: str = "",
    project_name: str = "",
    cronjob_id: int | None = None,
    cronjob_name: str = "",
    app_name: str = "",
    firewall_tab: str = "port",
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    checks.append(
        _run_check("panel", lambda: get_panel_summary(executor), lambda payload: payload.get("systemVersion"))
    )

    if website_alias:
        checks.append(
            _run_check(
                "ingress",
                lambda: get_ingress(executor, website_id=_website_id(executor, website_alias)),
                lambda payload: payload.get("ingress"),
            )
        )

    if container_name:
        checks.append(
            _run_check(
                "container", lambda: get_container(executor, name=container_name), lambda payload: payload.get("name")
            )
        )

    if project_name:
        checks.append(
            _run_check(
                "project", lambda: get_compose_project(executor, name=project_name), lambda payload: payload.get("name")
            )
        )

    resolved_cronjob_id = cronjob_id
    if resolved_cronjob_id is None and cronjob_name:
        resolved_cronjob_id = find_cronjob_id(executor, name=cronjob_name)
    if resolved_cronjob_id is not None:
        checks.append(
            _run_check(
                "cronjob",
                lambda: load_cronjob(executor, cronjob_id=resolved_cronjob_id),
                lambda payload: payload.get("id"),
            )
        )

    checks.append(
        _run_check(
            "firewall", lambda: load_firewall_base(executor, name=firewall_tab), lambda payload: "isActive" in payload
        )
    )

    if app_name:
        checks.append(
            _run_check(
                "app",
                lambda: get_installed_app(executor, install_id=_app_id(executor, app_name)),
                lambda payload: payload.get("id"),
            )
        )

    checks.append(_run_check("task", lambda: get_task_count(executor), lambda payload: "executing" in payload))

    payload = {
        "profile": profile,
        "env": env,
        "ok": all(item["ok"] for item in checks),
        "checks": checks,
    }
    if write_report:
        if repo_root is None:
            raise ValueError("repo_root is required when write_report is enabled")
        payload["report"] = _write_report(repo_root.resolve(), env, profile, payload)
    return payload
