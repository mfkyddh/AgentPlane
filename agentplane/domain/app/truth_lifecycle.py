from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from agentplane.domain.app.catalog import load_app_catalog, write_app_catalog
from agentplane.domain.app.models import AppCatalogEntry


APP_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
ALLOWED_APP_RESOURCE_KINDS: tuple[str, ...] = ("postgres", "redis", "minio")


@dataclass(frozen=True)
class CatalogMutationResult:
    path: Path
    changed: bool
    before_count: int
    after_count: int
    entry: AppCatalogEntry | None


def validate_app_id(app_id: str) -> None:
    if not isinstance(app_id, str) or not app_id or not APP_ID_PATTERN.match(app_id):
        raise ValueError(f"invalid app_id (must match {APP_ID_PATTERN.pattern}): {app_id!r}")


def validate_contract_relpath(relpath: str) -> None:
    if not isinstance(relpath, str) or not relpath:
        raise ValueError("contract path must be a non-empty string")
    path = Path(relpath)
    if path.is_absolute():
        raise ValueError(f"contract path must be repo-relative: {relpath}")
    # Strictly disallow parent traversal. Onboarding/offboarding should never rely on it.
    if any(part == ".." for part in path.parts):
        raise ValueError(f"contract path must not contain '..': {relpath}")


def validate_catalog_entry(entry: AppCatalogEntry) -> None:
    validate_app_id(entry.app)
    if entry.service_key != entry.app:
        raise ValueError(f"service_key must equal app_id: app={entry.app} service_key={entry.service_key}")
    if not isinstance(entry.repo_name, str) or not entry.repo_name:
        raise ValueError("repo_name must be a non-empty string")
    if not isinstance(entry.repo_root, Path):
        raise ValueError("repo_root must be a pathlib.Path")
    if not isinstance(entry.contracts, dict) or not entry.contracts:
        raise ValueError("contracts must be a non-empty mapping")
    for target, relpath in entry.contracts.items():
        if not isinstance(target, str) or not target:
            raise ValueError("contracts keys must be non-empty strings")
        validate_contract_relpath(relpath)


def _catalog_path(repo_root: Path) -> Path:
    return repo_root / "inventory" / "apps" / "catalog.json"


def onboard_catalog_entry(
    repo_root: Path,
    entry: AppCatalogEntry,
    *,
    write: bool,
    allow_replace: bool = False,
) -> CatalogMutationResult:
    """Add (or replace) one app entry in `inventory/apps/catalog.json`."""

    repo_root = Path(repo_root).resolve()
    validate_catalog_entry(entry)
    current = load_app_catalog(repo_root)
    before_count = len(current)
    by_app = {item.app: item for item in current}
    by_service_key = {item.service_key: item for item in current}

    existing_by_app = by_app.get(entry.app)
    existing_by_service = by_service_key.get(entry.service_key)
    if existing_by_app is not None or existing_by_service is not None:
        if not allow_replace:
            raise ValueError(f"catalog entry already exists for app/service_key: {entry.app}")
        # Ensure the existing entry refers to the same logical identity.
        if existing_by_app is not None and existing_by_app.service_key != entry.service_key:
            raise ValueError("refusing to replace: existing catalog app has different service_key")
        if existing_by_service is not None and existing_by_service.app != entry.app:
            raise ValueError("refusing to replace: existing catalog service_key has different app")

    # Upsert by app_id (service_key is contractually equal).
    next_entries: list[AppCatalogEntry] = [item for item in current if item.app != entry.app]
    next_entries.append(entry)
    next_entries = sorted(next_entries, key=lambda it: (it.app, it.service_key))
    changed = existing_by_app != entry

    if write and changed:
        write_app_catalog(repo_root, next_entries)
    return CatalogMutationResult(
        path=_catalog_path(repo_root),
        changed=changed,
        before_count=before_count,
        after_count=len(next_entries),
        entry=entry,
    )


def offboard_catalog_entry(repo_root: Path, *, app_id: str, write: bool) -> CatalogMutationResult:
    """Remove one app entry from `inventory/apps/catalog.json`."""

    repo_root = Path(repo_root).resolve()
    validate_app_id(app_id)
    current = load_app_catalog(repo_root)
    before_count = len(current)
    removed: AppCatalogEntry | None = None
    kept: list[AppCatalogEntry] = []
    for item in current:
        if item.app == app_id or item.service_key == app_id:
            removed = item
            continue
        kept.append(item)
    kept = sorted(kept, key=lambda it: (it.app, it.service_key))
    changed = removed is not None
    if write and changed:
        write_app_catalog(repo_root, kept)
    return CatalogMutationResult(
        path=_catalog_path(repo_root),
        changed=changed,
        before_count=before_count,
        after_count=len(kept),
        entry=removed,
    )


def catalog_service_keys(repo_root: Path) -> set[str]:
    """Return the set of canonical service keys (Phase 1 equals app_id)."""

    keys: set[str] = set()
    for entry in load_app_catalog(Path(repo_root).resolve()):
        keys.add(entry.service_key)
    return keys


def make_app_resource_registry_entry(
    *,
    app_id: str,
    resources: dict[str, dict[str, Any]] | None = None,
    secret_files: Sequence[str] | None = None,
    ledger_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a Phase-1-compliant app resource registry entry (in-memory)."""

    validate_app_id(app_id)
    payload: dict[str, Any] = {"owner_app": app_id}
    if ledger_status is not None:
        if not isinstance(ledger_status, dict):
            raise ValueError("ledger_status must be a dict when provided")
        payload["ledger_status"] = dict(ledger_status)
    if secret_files is not None:
        items = [item for item in secret_files if isinstance(item, str) and item]
        if items:
            payload["secret_files"] = items
    if resources:
        for kind, spec in resources.items():
            if kind not in ALLOWED_APP_RESOURCE_KINDS:
                raise ValueError(f"unknown resource kind: {kind}")
            if not isinstance(spec, dict):
                raise ValueError(f"resource payload must be an object: kind={kind}")
            payload[kind] = dict(spec)
    return payload


def plan_app_resource_registry_onboard(
    registry: dict[str, Any],
    *,
    app_id: str,
    entry: dict[str, Any] | None = None,
    registry_key: str | None = None,
    allow_replace: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return (next_registry, evidence) for inserting one app resource registry entry.

    This helper does not write files. Callers own persistence.
    """

    if not isinstance(registry, dict):
        raise ValueError("registry must be a dict")
    validate_app_id(app_id)
    key = registry_key or app_id
    if key != app_id:
        # Phase 1: key aliases are not allowed as formal truth.
        raise ValueError("registry_key must equal app_id in Phase 1")
    next_entry = dict(entry) if entry is not None else make_app_resource_registry_entry(app_id=app_id)
    if next_entry.get("owner_app") != app_id:
        raise ValueError("registry entry owner_app must equal app_id")
    exists = key in registry
    if exists and not allow_replace:
        raise ValueError(f"registry entry already exists: {key}")
    next_registry = dict(registry)
    next_registry[key] = next_entry
    return next_registry, {"action": "upsert", "registry_key": key, "replaced": exists}


def plan_app_resource_registry_offboard(registry: dict[str, Any], *, app_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return (next_registry, evidence) for removing an app's resource entry (and aliases)."""

    if not isinstance(registry, dict):
        raise ValueError("registry must be a dict")
    validate_app_id(app_id)
    removed_keys: list[str] = []
    next_registry: dict[str, Any] = {}
    for key, raw in registry.items():
        if not isinstance(key, str):
            continue
        if key == app_id:
            removed_keys.append(key)
            continue
        if isinstance(raw, dict) and raw.get("owner_app") == app_id:
            removed_keys.append(key)
            continue
        next_registry[key] = raw
    return next_registry, {"action": "remove", "app_id": app_id, "removed_keys": removed_keys}


def find_orphaned_registry_keys(registry: dict[str, Any], *, catalog_apps: set[str]) -> list[str]:
    """Return registry keys whose owner_app is not present in catalog_apps."""

    if not isinstance(registry, dict):
        raise ValueError("registry must be a dict")
    orphans: list[str] = []
    for key, raw in registry.items():
        if not isinstance(key, str) or not isinstance(raw, dict):
            continue
        owner_app = raw.get("owner_app")
        if isinstance(owner_app, str) and owner_app and owner_app not in catalog_apps:
            orphans.append(key)
    return sorted(set(orphans))


def find_orphaned_inventory_app_resource_summaries(
    inventory_payload: dict[str, Any],
    *,
    catalog_keys: set[str],
) -> list[str]:
    """Return service_keys that contain app_resource_summary but are not in catalog."""

    if not isinstance(inventory_payload, dict):
        raise ValueError("inventory_payload must be a dict")
    services = inventory_payload.get("services")
    if not isinstance(services, dict):
        return []
    orphans: list[str] = []
    for service_key, raw in services.items():
        if not isinstance(service_key, str) or not isinstance(raw, dict):
            continue
        if service_key in catalog_keys:
            continue
        summary = raw.get("app_resource_summary")
        if isinstance(summary, dict) and summary:
            orphans.append(service_key)
    return sorted(set(orphans))


def load_json_file(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    return payload if isinstance(payload, dict) else {}


def iter_known_targets(repo_root: Path) -> Iterable[str]:
    """Enumerate targets under `inventory/servers/*`."""

    servers_root = Path(repo_root).resolve() / "inventory" / "servers"
    if not servers_root.is_dir():
        return ()
    targets: list[str] = []
    for child in servers_root.iterdir():
        if child.is_dir():
            targets.append(child.name)
    return tuple(sorted(targets))


def scan_offboarding_orphans(repo_root: Path, *, app_id: str) -> dict[str, Any]:
    """Scan tracked inventory for orphaned app resource truth after app offboarding.

    This helper only reads state and returns evidence; it does not modify files.
    """

    repo_root = Path(repo_root).resolve()
    validate_app_id(app_id)
    catalog_apps = {entry.app for entry in load_app_catalog(repo_root) if isinstance(entry.app, str)}
    catalog_keys = {entry.service_key for entry in load_app_catalog(repo_root) if isinstance(entry.service_key, str)}
    results: dict[str, Any] = {"app_id": app_id, "targets": []}

    for target in iter_known_targets(repo_root):
        server_root = repo_root / "inventory" / "servers" / target
        registry_file = server_root / "app-resources.json"
        inventory_file = server_root / "inventory.json"
        registry = load_json_file(registry_file)
        inventory = load_json_file(inventory_file)

        # Orphans in registry are defined by owner_app no longer in catalog.
        registry_orphans = find_orphaned_registry_keys(registry, catalog_apps=catalog_apps)
        summary_orphans = find_orphaned_inventory_app_resource_summaries(inventory, catalog_keys=catalog_keys)
        results["targets"].append(
            {
                "target": target,
                "registry_file": str(registry_file),
                "inventory_file": str(inventory_file),
                "registry_orphans": registry_orphans,
                "inventory_summary_orphans": summary_orphans,
            }
        )

    return results

