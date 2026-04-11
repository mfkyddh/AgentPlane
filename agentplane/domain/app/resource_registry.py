from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentplane.domain.app.models import AppCatalogEntry
from agentplane.domain.app.resource_models import AppResourceDefinition


def load_target_inventory(repo_root: Path, target: str) -> dict[str, Any]:
    inventory_file = repo_root / "inventory" / "servers" / target / "inventory.json"
    if not inventory_file.is_file():
        return {}
    payload = json.loads(inventory_file.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"inventory 顶层必须是对象: {inventory_file}")
    return payload


def _catalog_entry_maps(repo_root: Path) -> tuple[dict[str, AppCatalogEntry], dict[str, AppCatalogEntry]]:
    from agentplane.domain.app.catalog import load_app_catalog

    try:
        entries = load_app_catalog(repo_root)
    except FileNotFoundError:
        return {}, {}

    by_app: dict[str, AppCatalogEntry] = {}
    by_service_key: dict[str, AppCatalogEntry] = {}
    for entry in entries:
        by_app[entry.app] = entry
        by_service_key[entry.service_key] = entry
    return by_app, by_service_key


def _catalog_identity(
    by_app: dict[str, AppCatalogEntry],
    by_service_key: dict[str, AppCatalogEntry],
    *,
    app: str,
) -> tuple[str, str]:
    entry = by_app.get(app) or by_service_key.get(app)
    if entry is None:
        return app, app
    return entry.app, entry.service_key


def _registry_identity(
    registry_key: str,
    owner_app: str,
    *,
    by_app: dict[str, AppCatalogEntry],
    by_service_key: dict[str, AppCatalogEntry],
) -> tuple[str, str]:
    entry = by_service_key.get(registry_key) or by_app.get(registry_key)
    if entry is None:
        owner_entry = by_app.get(owner_app)
        if owner_entry is not None:
            entry = owner_entry
    if entry is None:
        return registry_key, registry_key
    return entry.app, entry.service_key


def app_resource_inventory_projection(repo_root: Path, target: str, app: str) -> dict[str, Any]:
    inventory = load_target_inventory(repo_root, target)
    by_app, by_service_key = _catalog_entry_maps(repo_root)
    _, service_key = _catalog_identity(by_app, by_service_key, app=app)
    services = inventory.get("services")
    summary_field = "app_resource_summary"
    if not isinstance(services, dict):
        return {"found": False, "service_key": service_key, summary_field: None}
    service = services.get(service_key)
    if not isinstance(service, dict):
        return {"found": False, "service_key": service_key, summary_field: None}
    app_resource_summary = service.get(summary_field)
    if not isinstance(app_resource_summary, dict):
        return {"found": False, "service_key": service_key, summary_field: None}
    return {"found": True, "service_key": service_key, summary_field: app_resource_summary}


def _resource_kinds(raw_entry: dict[str, Any]) -> tuple[str, ...]:
    items = [name for name, value in raw_entry.items() if name in {"postgres", "redis", "minio"} and isinstance(value, dict)]
    return tuple(sorted(items))


def _resource_payload(raw_entry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {name: dict(value) for name, value in raw_entry.items() if name in {"postgres", "redis", "minio"} and isinstance(value, dict)}


def available_app_resources(repo_root: Path, target: str) -> list[tuple[AppResourceDefinition, dict[str, Any]]]:
    from agentplane.cli.app_resource_state import load_registry

    _, registry = load_registry(repo_root, target)
    by_app, by_service_key = _catalog_entry_maps(repo_root)
    best_items: dict[str, tuple[int, AppResourceDefinition, dict[str, Any]]] = {}
    ordered_apps: list[str] = []

    for registry_key, raw_entry in registry.items():
        if not isinstance(registry_key, str) or not isinstance(raw_entry, dict):
            continue
        owner_app = raw_entry.get("owner_app")
        if not isinstance(owner_app, str):
            continue
        canonical_app, _ = _registry_identity(
            registry_key,
            owner_app,
            by_app=by_app,
            by_service_key=by_service_key,
        )
        secret_files = raw_entry.get("secret_files")
        definition = AppResourceDefinition(
            app=canonical_app,
            owner_app=owner_app,
            resource_kinds=_resource_kinds(raw_entry),
            ledger_status=dict(raw_entry.get("ledger_status", {})) if isinstance(raw_entry.get("ledger_status"), dict) else {},
            resources=_resource_payload(raw_entry),
            secret_files=tuple(item for item in secret_files if isinstance(item, str)) if isinstance(secret_files, list) else (),
        )
        score = 0 if registry_key == canonical_app else 1
        existing = best_items.get(canonical_app)
        if existing is None:
            ordered_apps.append(canonical_app)
            best_items[canonical_app] = (score, definition, raw_entry)
            continue
        if score < existing[0]:
            best_items[canonical_app] = (score, definition, raw_entry)

    items: list[tuple[AppResourceDefinition, dict[str, Any]]] = []
    for canonical_app in ordered_apps:
        _, definition, raw_entry = best_items[canonical_app]
        items.append((definition, raw_entry))
    return items


def resolve_app_resource(repo_root: Path, target: str, app: str) -> tuple[AppResourceDefinition, dict[str, Any]]:
    by_app, by_service_key = _catalog_entry_maps(repo_root)
    requested_app, _ = _catalog_identity(by_app, by_service_key, app=app)
    for definition, raw_entry in available_app_resources(repo_root, target):
        if definition.app == requested_app:
            return definition, raw_entry
    raise ValueError(f"unknown app resource for {target}: {app}")
