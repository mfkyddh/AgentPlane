from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentplane.domain.app.catalog import load_app_catalog, resolve_app_contract_source
from agentplane.domain.app.models import AppObject
from agentplane.domain.app.resource_paths import canonical_contract_ref
from agentplane.domain.app.runtime_helpers import render_domain_path
from agentplane.providers import get_provider
from agentplane.runtime.observation import build_verification_payload


def _inventory_entry(repo_root: Path, target: str, service_key: str) -> dict[str, Any]:
    from agentplane.domain.app.runtime_helpers import load_inventory

    _, payload = load_inventory(repo_root, target)
    services = payload.get("services", {})
    if not isinstance(services, dict):
        return {}
    entry = services.get(service_key, {})
    return entry if isinstance(entry, dict) else {}


def _object_from_entry(repo_root: Path, target: str, entry_app: str, app_repo_root: str | None = None) -> AppObject:
    entry, contract_file = resolve_app_contract_source(
        repo_root,
        target=target,
        app=entry_app,
        app_repo_root=app_repo_root,
    )
    return AppObject(
        app=entry.app,
        target=target,
        repo_name=entry.repo_name,
        repo_root=entry.repo_root.resolve(),
        service_key=entry.service_key,
        contract_file=contract_file,
    )


def _canonical_ref(obj: AppObject) -> str:
    return canonical_contract_ref(obj.app, obj.target)


def _object_payload(obj: AppObject, inventory_entry: dict[str, Any], *, include_resolved_path: bool) -> dict[str, Any]:
    payload = {
        "app": obj.app,
        "target": obj.target,
        "repo_name": obj.repo_name,
        "service_key": obj.service_key,
        "canonical_ref": _canonical_ref(obj),
        "control_plane": inventory_entry.get("control_plane", ""),
        "public_url": inventory_entry.get("public_url", ""),
    }
    if include_resolved_path:
        payload["resolved_path"] = render_domain_path(obj.contract_file)
        payload["contract_file"] = render_domain_path(obj.contract_file)
    return payload


def _contract_payload(contract_file: Path) -> dict[str, Any]:
    import yaml

    if not contract_file.is_file():
        return {}
    try:
        payload = yaml.safe_load(contract_file.read_text(encoding="utf-8")) or {}
    except (yaml.YAMLError, UnicodeDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _resolved_summary_path(repo_root: Path, configured_path: str) -> Path | None:
    repo_root = repo_root.resolve()
    resolved = (repo_root / configured_path).resolve()
    try:
        resolved.relative_to(repo_root)
    except ValueError:
        return None
    return resolved


def _summary_files(obj: AppObject) -> list[dict[str, Any]]:
    from agentplane.domain.app.runtime_helpers import nested_get

    contract = _contract_payload(obj.contract_file)
    summary_paths = nested_get(contract, "docs.app_summary_files")
    if isinstance(summary_paths, dict):
        target_path = summary_paths.get(obj.target)
        if isinstance(target_path, str) and target_path:
            resolved = _resolved_summary_path(obj.repo_root, target_path)
            if resolved is not None:
                return [
                    {
                        "target": obj.target,
                        "path": str(resolved),
                        "source": "docs.app_summary_files",
                        "exists": resolved.is_file(),
                    }
                ]
    summary_path = nested_get(contract, "docs.app_summary_file")
    if isinstance(summary_path, str) and summary_path:
        resolved = _resolved_summary_path(obj.repo_root, summary_path)
        if resolved is None:
            return []
        return [
            {
                "target": obj.target,
                "path": str(resolved),
                "source": "docs.app_summary_file",
                "exists": resolved.is_file(),
            }
        ]
    return []


def _ledger_status(repo_root: Path, target: str) -> dict[str, Any]:
    from agentplane.domain.app.runtime_helpers import nested_get

    inventory_file = repo_root / "inventory" / "servers" / target / "inventory.json"
    payload = json.loads(inventory_file.read_text(encoding="utf-8")) if inventory_file.exists() else {}
    expected_pointer = f"inventory/servers/{target}/ledgers/apps.json"
    json_file = repo_root / expected_pointer
    markdown_file = repo_root / "inventory" / "servers" / target / "ledgers" / "apps.md"
    actual_pointer = nested_get(payload, "object_ledgers.ledgers.apps") if isinstance(payload, dict) else None
    inventory_pointer = actual_pointer if isinstance(actual_pointer, str) else ""
    return {
        "json_file": str(json_file),
        "markdown_file": str(markdown_file),
        "inventory_pointer": inventory_pointer,
        "expected_pointer": expected_pointer,
        "json_exists": json_file.is_file(),
        "markdown_exists": markdown_file.is_file(),
        "inventory_pointer_ok": inventory_pointer == expected_pointer,
    }


def search_apps(
    repo_root: Path,
    target: str,
    *,
    app: str | None = None,
    app_repo_root: str | None = None,
    include_resolved_path: bool = True,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    if app:
        entries = [_object_from_entry(repo_root, target, app, app_repo_root=app_repo_root)]
    else:
        try:
            catalog_entries = load_app_catalog(repo_root)
        except FileNotFoundError:
            catalog_entries = []
        entries = [
            _object_from_entry(repo_root, target, entry.app) for entry in catalog_entries if entry.contracts.get(target)
        ]
    for entry in entries:
        inventory_entry = _inventory_entry(repo_root, target, entry.service_key)
        items.append(_object_payload(entry, inventory_entry, include_resolved_path=include_resolved_path))
    return {"target": target, "items": items}


def get_app(repo_root: Path, target: str, app: str, app_repo_root: str | None = None) -> dict[str, Any]:
    obj = _object_from_entry(repo_root, target, app, app_repo_root=app_repo_root)
    inventory_entry = _inventory_entry(repo_root, target, obj.service_key)
    return {
        "app": _object_payload(obj, inventory_entry, include_resolved_path=True),
        "inventory_entry": inventory_entry,
        "summary_files": _summary_files(obj),
        "ledger_status": _ledger_status(repo_root, target),
    }


def verify_app_object(repo_root: Path, target: str, app: str, app_repo_root: str | None = None) -> dict[str, Any]:
    obj = _object_from_entry(repo_root, target, app, app_repo_root=app_repo_root)
    inventory_entry = _inventory_entry(repo_root, target, obj.service_key)
    contract = _contract_payload(obj.contract_file)
    summary_files = _summary_files(obj)
    ledger_status = _ledger_status(repo_root, target)
    failures: list[str] = []
    checks: dict[str, Any] = {}

    contract_exists = obj.contract_file.exists()
    checks["contract_file"] = {
        "ok": contract_exists,
        "canonical_ref": _canonical_ref(obj),
        "resolved_path": render_domain_path(obj.contract_file),
        "path": render_domain_path(obj.contract_file),
    }
    if not contract_exists:
        failures.append("contract_file")

    has_inventory = bool(inventory_entry)
    checks["inventory_projection"] = {"ok": has_inventory, "service_key": obj.service_key}
    if not has_inventory:
        failures.append("inventory_projection")

    declared_summary = False
    docs = contract.get("docs")
    if isinstance(docs, dict):
        summary_paths = docs.get("app_summary_files")
        if isinstance(summary_paths, dict):
            target_path = summary_paths.get(target)
            declared_summary = isinstance(target_path, str) and bool(target_path)
        if not declared_summary:
            summary_path = docs.get("app_summary_file")
            declared_summary = isinstance(summary_path, str) and bool(summary_path)
    summary_ok = (not declared_summary) or (
        bool(summary_files) and all(bool(item.get("exists")) for item in summary_files)
    )
    checks["summary_files"] = {"ok": summary_ok, "items": summary_files}
    if not summary_ok:
        failures.append("summary_files")

    ledger_ok = (
        bool(ledger_status.get("json_exists"))
        and bool(ledger_status.get("markdown_exists"))
        and bool(ledger_status.get("inventory_pointer_ok"))
    )
    checks["ledger_status"] = {"ok": ledger_ok, **ledger_status}
    if not ledger_ok:
        failures.append("ledger_status")

    evidence = {
        "app": obj.app,
        "target": target,
        "canonical_ref": _canonical_ref(obj),
        "resolved_path": render_domain_path(obj.contract_file),
        "inventory_entry": inventory_entry,
        "summary_files": summary_files,
        "ledger_status": ledger_status,
    }
    payload = build_verification_payload(
        canonical_ref=_canonical_ref(obj),
        ledger_fields=_object_payload(obj, inventory_entry, include_resolved_path=False),
        verification_fields={
            "resolved_path": render_domain_path(obj.contract_file),
            "inventory_entry": inventory_entry,
            "summary_files": summary_files,
            "ledger_status": ledger_status,
        },
        resolved_path=render_domain_path(obj.contract_file),
        evidence=evidence,
        checks=checks,
        failures=failures,
        ok=not failures,
    )
    payload["evidence"] = evidence
    return payload


def refresh_app_ledger(repo_root: Path, target: str, write: bool) -> dict[str, Any]:
    payload = search_apps(repo_root, target, include_resolved_path=False)
    server_root = repo_root / "inventory" / "servers" / target
    ledger_root = server_root / "ledgers"
    inventory_file = server_root / "inventory.json"
    json_file = ledger_root / "apps.json"
    markdown_file = ledger_root / "apps.md"
    inventory_pointer = f"inventory/servers/{target}/ledgers/apps.json"
    json_payload = {"target": target, "count": len(payload["items"]), "items": payload["items"]}
    markdown_lines = [f"# {target} apps ledger", ""]
    if not payload["items"]:
        markdown_lines.append("- no active app catalog object")
    for item in payload["items"]:
        markdown_lines.append(
            f"- `{item['app']}` / `{item.get('control_plane', '-')}` / `{item.get('public_url', '-')}`"
        )
    markdown_text = "\n".join(markdown_lines) + "\n"
    if write:
        ledger_root.mkdir(parents=True, exist_ok=True)
        json_file.write_text(json.dumps(json_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        markdown_file.write_text(markdown_text, encoding="utf-8")
        inventory_payload = json.loads(inventory_file.read_text(encoding="utf-8")) if inventory_file.exists() else {}
        object_ledgers = inventory_payload.get("object_ledgers")
        if not isinstance(object_ledgers, dict):
            object_ledgers = {}
        ledgers = object_ledgers.get("ledgers")
        if not isinstance(ledgers, dict):
            ledgers = {}
        ledgers["apps"] = inventory_pointer
        object_ledgers["ledgers"] = ledgers
        inventory_payload["object_ledgers"] = object_ledgers
        inventory_file.write_text(json.dumps(inventory_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "target": target,
        "count": len(payload["items"]),
        "json_file": str(json_file),
        "markdown_file": str(markdown_file),
        "inventory_pointer": inventory_pointer,
    }


def _executor_for_target(target: str) -> object:
    return get_provider().get_target(target)


def discover_installed_apps(
    repo_root: Path,
    target: str,
    *,
    name: str = "",
    include_managed: bool = False,
) -> dict[str, Any]:
    """Discover 1Panel installed apps and classify them as managed or unmanaged."""
    executor = _executor_for_target(target)
    provider = get_provider()
    live_payload = provider.search_installed_apps(executor, name=name)
    live_items = live_payload.get("items") if isinstance(live_payload, dict) else []
    if not isinstance(live_items, list):
        live_items = []

    try:
        catalog_entries = load_app_catalog(repo_root)
    except FileNotFoundError:
        catalog_entries = []

    catalog_service_keys: set[str] = set()
    catalog_app_keys: set[str] = set()
    for entry in catalog_entries:
        catalog_service_keys.add(entry.service_key)
        catalog_app_keys.add(entry.app)

    managed: list[dict[str, Any]] = []
    unmanaged: list[dict[str, Any]] = []

    for item in live_items:
        if not isinstance(item, dict):
            continue
        app_key = str(item.get("appKey", ""))
        install_name = str(item.get("name", ""))
        install_id = item.get("id")
        entry = {
            "install_id": install_id,
            "name": install_name,
            "app_key": app_key,
            "status": item.get("status", ""),
            "version": item.get("version", ""),
        }
        is_managed = app_key in catalog_app_keys or install_name in catalog_service_keys
        if is_managed:
            managed.append(entry)
        else:
            unmanaged.append(entry)

    result: dict[str, Any] = {
        "target": target,
        "total_installed": len(live_items),
        "managed_count": len(managed),
        "unmanaged_count": len(unmanaged),
        "unmanaged": unmanaged,
    }
    if include_managed:
        result["managed"] = managed
    return result
