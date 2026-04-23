#!/usr/bin/env python3
"""Generate object ledgers from tracked inventory state."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from agentplane.runtime.observation import extract_ledger_fields

from .redaction import scrub_persisted_payload


LEDGER_NAMES = ("websites", "containers", "firewall", "cronjobs", "apps", "app_resources", "automations")
LEDGER_SCOPE_NAMES = {
    "websites": "ingress",
    "containers": "container",
    "firewall": "firewall",
    "cronjobs": "cronjob",
    "apps": "app",
    "app_resources": "app_resource",
    "automations": "automation",
}
README_BEGIN = "<!-- BEGIN AGENTPLANE_ONEPANEL_LEDGER -->"
README_END = "<!-- END AGENTPLANE_ONEPANEL_LEDGER -->"


def _server_root(repo_root: Path, target: str) -> Path:
    return repo_root / "inventory" / "servers" / target


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _services(payload: dict[str, Any]) -> dict[str, Any]:
    services = payload.get("services")
    return services if isinstance(services, dict) else {}


def _website_rows(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    rows = _services(inventory).get("public_ingresses")
    return [item for item in rows if isinstance(item, dict)] if isinstance(rows, list) else []


def _container_rows(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, value in _services(inventory).items():
        if key == "public_ingresses" or not isinstance(value, dict):
            continue
        if "container_name" in value:
            row = dict(value)
            row.setdefault("service_key", key)
            rows.append(row)
    return rows


def _app_rows(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, value in _services(inventory).items():
        if not isinstance(value, dict):
            continue
        if "control_plane" in value or "project_name" in value:
            row = dict(value)
            row.setdefault("service_key", key)
            rows.append(row)
    return rows


def _cronjob_rows(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    automations = inventory.get("automations")
    if not isinstance(automations, list):
        return []
    return [item for item in automations if isinstance(item, dict) and "cronjob" in str(item.get("controller", "")).lower()]


def _automation_rows(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    automations = inventory.get("automations")
    return [item for item in automations if isinstance(item, dict)] if isinstance(automations, list) else []


def _firewall_rows(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    security = inventory.get("security")
    if not isinstance(security, dict):
        return []
    firewall = security.get("firewall")
    return [firewall] if isinstance(firewall, dict) else []


def _tenant_rows(server_root: Path) -> list[dict[str, Any]]:
    registry_file = server_root / "app-resources.json"
    if not registry_file.is_file():
        return []
    payload = _load_json(registry_file)
    rows: list[dict[str, Any]] = []
    for app_id, value in payload.items():
        if not isinstance(value, dict):
            continue
        owner_app = value.get("owner_app")
        if not isinstance(owner_app, str) or owner_app != app_id:
            continue
        row = dict(value)
        row.setdefault("app_id", app_id)
        rows.append(row)
    return rows


def _row_tokens(row: dict[str, Any]) -> set[str]:
    tokens: set[str] = set()
    for key in (
        "id",
        "alias",
        "name",
        "service_key",
        "app_id",
        "container_name",
        "primaryDomain",
        "primary_domain",
        "project_name",
        "public_url",
    ):
        value = row.get(key)
        if value in (None, ""):
            continue
        tokens.add(str(value))
    return tokens


def _onepanel_operation_entries(repo_root: Path, target: str) -> list[dict[str, Any]]:
    ledger_root = repo_root / "tmp" / "operation-ledger"
    entries: list[dict[str, Any]] = []
    if not ledger_root.is_dir():
        return entries
    for ledger_file in sorted(ledger_root.glob("*.jsonl"), reverse=True):
        for raw_line in ledger_file.read_text(encoding="utf-8").splitlines():
            if not raw_line.strip():
                continue
            try:
                payload = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            if payload.get("command") != "onepanel" or payload.get("target") != target:
                continue
            entries.append(payload)
    entries.sort(key=lambda item: str(item.get("timestamp", "")), reverse=True)
    return entries


def _operation_summary(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "action": entry.get("action"),
        "result": entry.get("result"),
        "op_id": entry.get("op_id"),
        "timestamp": entry.get("timestamp"),
        "dry_run": entry.get("dry_run", False),
    }


def _latest_operation_for(scope: str, row: dict[str, Any], entries: list[dict[str, Any]]) -> dict[str, Any] | None:
    row_tokens = _row_tokens(row)
    if not row_tokens:
        return None
    for entry in entries:
        if entry.get("scope") != scope:
            continue
        selectors = {str(item) for item in entry.get("selectors", []) if str(item)}
        if row_tokens & selectors:
            return _operation_summary(entry)
    return None


def _annotate_rows(name: str, rows: list[dict[str, Any]], entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scope = LEDGER_SCOPE_NAMES[name]
    annotated: list[dict[str, Any]] = []
    for row in rows:
        item = extract_ledger_fields(row)
        last_operation = _latest_operation_for(scope, item, entries)
        if last_operation:
            item["last_cli_operation"] = last_operation
        annotated.append(item)
    return annotated


def _latest_scope_operations(entries: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for entry in entries:
        scope = entry.get("scope")
        if not isinstance(scope, str) or not scope or scope in latest:
            continue
        latest[scope] = _operation_summary(entry)
    return latest


def _ledger_payloads(repo_root: Path, target: str) -> dict[str, list[dict[str, Any]]]:
    server_root = _server_root(repo_root, target)
    inventory = _load_json(server_root / "inventory.json")
    entries = _onepanel_operation_entries(repo_root, target)
    # "apps" ledger is a formal app object ledger (app id + contract pointer + projection metadata),
    # not a raw runtime summary projection. Delegate row building to the app domain contract.
    from agentplane.domain.app.object_handlers import search_apps as search_formal_apps

    apps_payload = search_formal_apps(repo_root, target, include_resolved_path=False)
    apps_rows = apps_payload.get("items") if isinstance(apps_payload, dict) else []
    apps_rows = [row for row in apps_rows if isinstance(row, dict)] if isinstance(apps_rows, list) else []
    return {
        "websites": _annotate_rows("websites", _website_rows(inventory), entries),
        "containers": _annotate_rows("containers", _container_rows(inventory), entries),
        "firewall": _annotate_rows("firewall", _firewall_rows(inventory), entries),
        "cronjobs": _annotate_rows("cronjobs", _cronjob_rows(inventory), entries),
        "apps": _annotate_rows("apps", apps_rows, entries),
        "app_resources": _annotate_rows("app_resources", _tenant_rows(server_root), entries),
        "automations": _annotate_rows("automations", _automation_rows(inventory), entries),
    }


def _markdown_for(name: str, rows: list[dict[str, Any]]) -> str:
    lines = [
        f"# {name} ledger",
        "",
        "- 本文件是 Markdown 摘要投影，只保留对象清单与最近状态。",
        "- 机器真源：同目录同名 `.json` 文件。",
        "- 对应 JSON 真源见同目录同名 `.json` 文件；脚本消费与结构化字段以 JSON 为准。",
        "",
    ]
    if name == "app_resources":
        lines.extend(
            [
                "- Redis 采用共享 runtime 凭据，并通过 DB 级逻辑分区 + key prefix 区分租户；这不是强隔离。",
                "- PostgreSQL/MinIO 继续记录各自租户凭据标识，其中 MinIO 额外登记 bucket-scoped policy 元数据。",
                "",
            ]
        )
    if not rows:
        lines.append("- none")
        return "\n".join(lines) + "\n"
    for row in rows:
        label = row.get("alias") or row.get("name") or row.get("service_key") or row.get("app_id") or row.get("container_name") or "item"
        lines.append(f"- `{label}`")
        status = row.get("status")
        if status not in (None, ""):
            lines.append(f"  status: `{status}`")
        last_operation = row.get("last_cli_operation")
        if isinstance(last_operation, dict):
            lines.append(
                "  last_cli_operation: "
                f"`{last_operation.get('action', 'unknown')}` / `{last_operation.get('result', 'unknown')}` / "
                f"`{last_operation.get('timestamp', '-')}`"
            )
    return "\n".join(lines) + "\n"


def _project_inventory_summary(repo_root: Path, target: str, counts: dict[str, int], latest_operations: dict[str, dict[str, Any]]) -> Path:
    inventory_file = _server_root(repo_root, target) / "inventory.json"
    inventory = _load_json(inventory_file)
    inventory["object_ledgers"] = scrub_persisted_payload({
        "generated_at": datetime.now(UTC).isoformat(),
        "counts": counts,
        "ledgers": {
            name: f"inventory/servers/{target}/ledgers/{name}.json"
            for name in LEDGER_NAMES
        },
        "last_operations": latest_operations,
    })
    _dump_json(inventory_file, inventory)
    return inventory_file


def _render_readme_projection(target: str, counts: dict[str, int], latest_operations: dict[str, dict[str, Any]]) -> str:
    lines = [
        "## 1Panel 对象台帐投影",
        "",
        f"- 生成时间：`{datetime.now(UTC).isoformat()}`",
        f"- 刷新命令：`uv run python -m agentplane.cli projection ledger refresh --target {target} --repo-root <repo-root> --write`",
        "",
        "### 对象计数",
        "",
    ]
    for name in LEDGER_NAMES:
        lines.append(f"- `{name}`: {counts.get(name, 0)}")
    lines.extend(["", "### 最近 CLI 动作", ""])
    if latest_operations:
        for scope, payload in sorted(latest_operations.items()):
            lines.append(
                f"- `{scope}`: `{payload.get('action', 'unknown')}` / `{payload.get('result', 'unknown')}` / "
                f"`{payload.get('timestamp', '-')}`"
            )
    else:
        lines.append("- 无最近 onepanel CLI 记录。")
    return "\n".join(lines) + "\n"


def _project_readme(repo_root: Path, target: str, counts: dict[str, int], latest_operations: dict[str, dict[str, Any]]) -> Path:
    readme_file = _server_root(repo_root, target) / "README.md"
    section = f"{README_BEGIN}\n{_render_readme_projection(target, counts, latest_operations)}{README_END}\n"
    if readme_file.is_file():
        current = readme_file.read_text(encoding="utf-8")
    else:
        current = f"# {target} 摘要\n"
    if README_BEGIN in current and README_END in current:
        before, _, rest = current.partition(README_BEGIN)
        _, _, after = rest.partition(README_END)
        updated = before.rstrip() + "\n\n" + section + after.lstrip()
    else:
        updated = current.rstrip() + "\n\n" + section
    readme_file.write_text(updated, encoding="utf-8")
    return readme_file


def refresh_ledgers(repo_root: Path, target: str, *, write: bool = False) -> dict[str, Any]:
    resolved_root = repo_root.resolve()
    payloads = _ledger_payloads(resolved_root, target)
    counts = {name: len(rows) for name, rows in payloads.items()}
    ledger_root = _server_root(resolved_root, target) / "ledgers"
    latest_operations = _latest_scope_operations(_onepanel_operation_entries(resolved_root, target))
    inventory_file = _server_root(resolved_root, target) / "inventory.json"
    readme_file = _server_root(resolved_root, target) / "README.md"
    if write:
        ledger_root.mkdir(parents=True, exist_ok=True)
        for name, rows in payloads.items():
            # "apps" ledger is owned by app object contract; it must be rendered as
            # `inventory/servers/<target>/ledgers/apps.json|md` with the formal schema/format.
            if name == "apps":
                continue
            persisted_rows = scrub_persisted_payload(rows)
            (ledger_root / f"{name}.json").write_text(
                json.dumps({"items": persisted_rows, "count": len(rows)}, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            (ledger_root / f"{name}.md").write_text(_markdown_for(name, persisted_rows), encoding="utf-8")

        # Delegate apps ledger writing to the app domain so it won't drift back to runtime summaries.
        from agentplane.domain.app.object_handlers import refresh_app_ledger as refresh_formal_app_ledger

        refresh_formal_app_ledger(resolved_root, target, write=True)
        inventory_file = _project_inventory_summary(resolved_root, target, counts, latest_operations)
        readme_file = _project_readme(resolved_root, target, counts, latest_operations)
    return {
        "target": target,
        "ledger_root": str(ledger_root),
        "counts": counts,
        "inventory_file": str(inventory_file),
        "readme_file": str(readme_file),
        "last_operations": latest_operations,
        "ledgers": {name: str(ledger_root / f"{name}.json") for name in LEDGER_NAMES},
    }
