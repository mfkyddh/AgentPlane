from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from agentplane.domain.app.models import AppCatalogEntry
from agentplane.domain.app.resource_paths import (
    canonical_app_repo_ref,
    canonical_contract_ref,
    contract_relpath_for_target,
    resolve_catalog_repo_root,
)
from agentplane.runtime.path_policy import assert_canonical_ref, is_canonical_ref
from agentplane.runtime.resolution import ResolvedReference, materialize_path
from agentplane.runtime.wsl_bridge import wsl_posix_to_unc


def _catalog_file(repo_root: Path) -> Path:
    return repo_root / "inventory" / "apps" / "catalog.json"


def _normalize_repo_root_for_current_host(repo_root_value: str) -> str:
    if os.name == "nt" and repo_root_value.startswith("/"):
        unc_path = wsl_posix_to_unc(repo_root_value)
        if unc_path:
            return unc_path
    return repo_root_value


def _coerce_catalog_repo_root(repo_root_value: str) -> Path:
    return Path(_normalize_repo_root_for_current_host(repo_root_value)).expanduser()


def _runtime_repo_root_from_item(
    repo_root: Path,
    *,
    app: str,
    repo_name: str,
    repo_ref_value: str | None,
    repo_root_value: str | None,
) -> Path:
    if isinstance(repo_root_value, str) and repo_root_value:
        coerced = _coerce_catalog_repo_root(repo_root_value)
        if not coerced.is_absolute():
            return (repo_root / coerced).resolve()
        return coerced
    if isinstance(repo_ref_value, str) and repo_ref_value:
        canonical_repo_ref = assert_canonical_ref(repo_ref_value)
        expected_repo_ref = canonical_app_repo_ref(app)
        if canonical_repo_ref != expected_repo_ref:
            raise ValueError(f"app catalog repo_ref mismatch: expected {expected_repo_ref}, got {canonical_repo_ref}")
        return resolve_catalog_repo_root(repo_root, repo_name=repo_name)
    raise ValueError(f"app catalog missing repo locator: app={app}")


def _runtime_contract_relpaths(app: str, contracts: dict[str, str]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for target, value in contracts.items():
        if not isinstance(target, str) or not target or not isinstance(value, str) or not value:
            continue
        if is_canonical_ref(value):
            canonical_contract = assert_canonical_ref(value)
            expected = canonical_contract_ref(app, target)
            if canonical_contract != expected:
                raise ValueError(f"app catalog contract ref mismatch: expected {expected}, got {canonical_contract}")
            normalized[target] = contract_relpath_for_target(target)
            continue
        normalized[target] = value
    return normalized


def _resolved_contract_reference(entry: AppCatalogEntry, *, target: str, contract_rel: str) -> ResolvedReference:
    return ResolvedReference(
        canonical_ref=canonical_contract_ref(entry.app, target),
        resolved_path=materialize_path(entry.repo_root, contract_rel),
    )


def load_app_catalog(repo_root: Path) -> list[AppCatalogEntry]:
    catalog_file = _catalog_file(repo_root)
    if not catalog_file.exists():
        raise FileNotFoundError(f"missing app catalog: {catalog_file}")
    payload = json.loads(catalog_file.read_text(encoding="utf-8"))
    items = payload.get("apps", [])
    if not isinstance(items, list):
        raise ValueError(f"app catalog must contain a list at apps: {catalog_file}")
    entries: list[AppCatalogEntry] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        app = item.get("app")
        repo_name = item.get("repo_name")
        repo_root_value = item.get("repo_root")
        repo_ref_value = item.get("repo_ref")
        service_key = item.get("service_key")
        contracts = item.get("contracts")
        if not all(isinstance(value, str) and value for value in (app, repo_name, service_key)):
            continue
        if not isinstance(contracts, dict):
            continue
        runtime_repo_root = _runtime_repo_root_from_item(
            repo_root,
            app=app,
            repo_name=repo_name,
            repo_ref_value=repo_ref_value if isinstance(repo_ref_value, str) else None,
            repo_root_value=repo_root_value if isinstance(repo_root_value, str) else None,
        )
        normalized_contracts = _runtime_contract_relpaths(
            app,
            {
                key: value
                for key, value in contracts.items()
                if isinstance(key, str) and key and isinstance(value, str) and value
            },
        )
        entries.append(
            AppCatalogEntry(
                app=app,
                repo_name=repo_name,
                repo_root=runtime_repo_root,
                service_key=service_key,
                contracts=normalized_contracts,
            )
        )
    return entries


def _find_catalog_entry(
    entries: list[AppCatalogEntry],
    *,
    app: str | None = None,
    service_key: str | None = None,
) -> AppCatalogEntry | None:
    for entry in entries:
        if app is not None and entry.app == app:
            return entry
        if service_key is not None and entry.service_key == service_key:
            return entry
    return None


def resolve_app_entry(repo_root: Path, *, app: str) -> AppCatalogEntry:
    entry = _find_catalog_entry(load_app_catalog(repo_root), app=app)
    if entry is not None:
        return entry
    raise ValueError(f"app catalog missing app entry: app={app}")


def resolve_app_entry_by_service_key(repo_root: Path, *, service_key: str) -> AppCatalogEntry:
    entry = _find_catalog_entry(load_app_catalog(repo_root), service_key=service_key)
    if entry is not None:
        return entry
    raise ValueError(f"app catalog missing service_key entry: service_key={service_key}")


def resolve_app_entry_for_identifier(repo_root: Path, *, app_or_service_key: str) -> AppCatalogEntry:
    entries = load_app_catalog(repo_root)
    entry = _find_catalog_entry(entries, app=app_or_service_key)
    if entry is not None:
        return entry
    entry = _find_catalog_entry(entries, service_key=app_or_service_key)
    if entry is not None:
        return entry
    raise ValueError(f"app catalog missing app entry: app={app_or_service_key}")


def resolve_app_contract_reference(
    repo_root: Path,
    *,
    target: str,
    app: str,
    app_repo_root: str | None = None,
) -> tuple[AppCatalogEntry, ResolvedReference]:
    entry = resolve_app_entry(repo_root, app=app)
    if app_repo_root:
        resolved_app_root = materialize_path(_coerce_catalog_repo_root(app_repo_root))
        contract_rel = Path(contract_relpath_for_target(target))
        entry = AppCatalogEntry(
            app=entry.app,
            repo_name=resolved_app_root.name,
            repo_root=resolved_app_root,
            service_key=entry.service_key,
            contracts=dict(entry.contracts),
        )
        return entry, _resolved_contract_reference(entry, target=target, contract_rel=str(contract_rel))

    contract_rel = entry.contracts.get(target)
    if not isinstance(contract_rel, str) or not contract_rel:
        raise ValueError(f"app catalog missing target mapping: target={target} app={app}")
    return entry, _resolved_contract_reference(entry, target=target, contract_rel=contract_rel)


def resolve_app_contract(repo_root: Path, *, target: str, app: str) -> tuple[AppCatalogEntry, Path]:
    entry, resolved = resolve_app_contract_reference(repo_root, target=target, app=app)
    return entry, resolved.resolved_path


def resolve_app_contract_source(
    repo_root: Path,
    *,
    target: str,
    app: str,
    app_repo_root: str | None = None,
) -> tuple[AppCatalogEntry, Path]:
    entry, resolved = resolve_app_contract_reference(
        repo_root,
        target=target,
        app=app,
        app_repo_root=app_repo_root,
    )
    return entry, resolved.resolved_path


def write_app_catalog(repo_root: Path, entries: list[AppCatalogEntry]) -> Path:
    """Write `inventory/apps/catalog.json` with stable formatting.

    This is a low-level helper used by lifecycle code. It intentionally does not
    enforce naming contracts; validation belongs to the lifecycle layer.
    """

    catalog_file = _catalog_file(repo_root)
    catalog_file.parent.mkdir(parents=True, exist_ok=True)
    items = []
    for entry in sorted(entries, key=lambda it: (it.app, it.service_key)):
        item: dict[str, Any] = {
            "app": entry.app,
            "repo_name": entry.repo_name,
            "repo_ref": canonical_app_repo_ref(entry.app),
            "service_key": entry.service_key,
            "contracts": {
                target: canonical_contract_ref(entry.app, target)
                if entry.contracts.get(target) == contract_relpath_for_target(target)
                else entry.contracts[target]
                for target in sorted(entry.contracts)
            },
        }
        try:
            repo_root_str = str(entry.repo_root.relative_to(repo_root))
        except ValueError:
            repo_root_str = str(entry.repo_root)
        item["repo_root"] = repo_root_str
        items.append(item)
    payload = {"apps": items}
    catalog_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return catalog_file
