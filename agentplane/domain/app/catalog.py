from __future__ import annotations

import json
import os
from pathlib import Path

from agentplane.domain.app.models import AppCatalogEntry
from agentplane.runtime.wsl_bridge import wsl_posix_to_unc

_TARGET_CONTRACT_PATHS = {
    "wsl": Path("deploy/agentplane/contract.wsl.yaml"),
    "prod0-main": Path("deploy/agentplane/contract.yaml"),
    "prod2-main": Path("deploy/agentplane/contract.prod2.yaml"),
}


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
        service_key = item.get("service_key")
        contracts = item.get("contracts")
        if not all(isinstance(value, str) and value for value in (app, repo_name, repo_root_value, service_key)):
            continue
        if not isinstance(contracts, dict):
            continue
        normalized_contracts = {
            key: value
            for key, value in contracts.items()
            if isinstance(key, str) and key and isinstance(value, str) and value
        }
        entries.append(
            AppCatalogEntry(
                app=app,
                repo_name=repo_name,
                repo_root=_coerce_catalog_repo_root(repo_root_value),
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


def resolve_app_contract(repo_root: Path, *, target: str, app: str) -> tuple[AppCatalogEntry, Path]:
    entry = resolve_app_entry(repo_root, app=app)
    contract_rel = entry.contracts.get(target)
    if not isinstance(contract_rel, str) or not contract_rel:
        raise ValueError(f"app catalog missing target mapping: target={target} app={app}")
    return entry, (entry.repo_root / contract_rel).resolve()


def resolve_app_contract_source(
    repo_root: Path,
    *,
    target: str,
    app: str,
    app_repo_root: str | None = None,
) -> tuple[AppCatalogEntry, Path]:
    entry = resolve_app_entry(repo_root, app=app)
    if not app_repo_root:
        return resolve_app_contract(repo_root, target=target, app=app)
    resolved_app_root = _coerce_catalog_repo_root(app_repo_root).resolve()
    try:
        contract_rel = _TARGET_CONTRACT_PATHS[target]
    except KeyError as exc:
        raise ValueError(f"Unsupported target for app_repo_root override: {target}") from exc
    return (
        AppCatalogEntry(
            app=entry.app,
            repo_name=resolved_app_root.name,
            repo_root=resolved_app_root,
            service_key=entry.service_key,
            contracts=dict(entry.contracts),
        ),
        (resolved_app_root / contract_rel).resolve(),
    )


def write_app_catalog(repo_root: Path, entries: list[AppCatalogEntry]) -> Path:
    """Write `inventory/apps/catalog.json` with stable formatting.

    This is a low-level helper used by lifecycle code. It intentionally does not
    enforce naming contracts; validation belongs to the lifecycle layer.
    """

    catalog_file = _catalog_file(repo_root)
    catalog_file.parent.mkdir(parents=True, exist_ok=True)
    items = [
        {
            "app": entry.app,
            "repo_name": entry.repo_name,
            "repo_root": str(entry.repo_root),
            "service_key": entry.service_key,
            "contracts": dict(sorted(entry.contracts.items())),
        }
        for entry in sorted(entries, key=lambda it: (it.app, it.service_key))
    ]
    payload = {"apps": items}
    catalog_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return catalog_file
