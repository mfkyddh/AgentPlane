from __future__ import annotations

from pathlib import Path
from typing import Any

from agentplane.domain.app.resource_models import AppResourceDefinition
from agentplane.domain.app.resource_registry import (
    app_resource_inventory_projection,
    available_app_resources,
    resolve_app_resource,
)
from agentplane.domain.app.resource_state import (
    APP_RESOURCE_SUMMARY_FIELDS,
    registry_secret_file,
    resolve_secret_file_path,
    validate_secret_files,
)
from agentplane.providers import get_provider
from agentplane.runtime.observation import build_verification_payload
from agentplane.runtime.path_policy import assert_canonical_ref


def _summary(definition: AppResourceDefinition) -> dict[str, Any]:
    return {
        "app": definition.app,
        "owner_app": definition.owner_app,
        "resource_kinds": list(definition.resource_kinds),
    }


def _declared_payload(raw_entry: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in raw_entry.items()
        if key in {"owner_app", "ledger_status", "postgres", "redis", "minio", "secret_files"}
    }


def _expected_app_resource_summary(raw_entry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    app_resource_summary: dict[str, dict[str, Any]] = {}
    for kind, fields in APP_RESOURCE_SUMMARY_FIELDS.items():
        resource = raw_entry.get(kind)
        if not isinstance(resource, dict):
            continue
        projected: dict[str, Any] = {}
        for field in fields:
            value = resource.get(field)
            if value is None or value == "":
                continue
            projected[field] = value
        secret_file = registry_secret_file(raw_entry, kind)
        if isinstance(secret_file, str) and secret_file:
            projected["secret_file"] = secret_file
        if projected:
            app_resource_summary[kind] = projected
    return app_resource_summary


def _secret_file_statuses(repo_root: Path, definition: AppResourceDefinition) -> list[dict[str, Any]]:
    statuses: list[dict[str, Any]] = []
    for secret_file in definition.secret_files:
        path = resolve_secret_file_path(repo_root, secret_file)
        statuses.append({"secret_file": secret_file, "path": str(path), "exists": path.is_file()})
    return statuses


def _canonical_ref(target: str, app: str) -> str:
    return assert_canonical_ref(f"targets/{target}/app-resources/{app}")


def search_app_resources(repo_root: Path, target: str) -> dict[str, Any]:
    items = [_summary(definition) for definition, _ in available_app_resources(Path(repo_root).resolve(), target)]
    return {"items": items}


def get_app_resource(repo_root: Path, target: str, app: str) -> dict[str, Any]:
    repo_root = Path(repo_root).resolve()
    definition, raw_entry = resolve_app_resource(repo_root, target, app)
    return {
        "resource": _summary(definition),
        "declared": _declared_payload(raw_entry),
        "projection": app_resource_inventory_projection(repo_root, target, app),
        "secret_files": _secret_file_statuses(repo_root, definition),
    }


def _live_database_evidence(repo_root: Path, target: str, definition: AppResourceDefinition) -> dict[str, Any] | None:
    """Query 1Panel for live database state and cross-reference with declared resources."""
    if not definition.resource_kinds:
        return None
    try:
        provider = get_provider()
        executor = provider.get_target(target)
    except Exception:
        return None

    live_databases: dict[str, list[dict[str, Any]]] = {}
    provider_available = True
    for kind in definition.resource_kinds:
        db_type = kind if kind in {"mysql", "postgresql", "redis", "mariadb"} else "mysql"
        if kind == "postgres":
            db_type = "postgresql"
        try:
            payload = provider.search_databases(executor, db_type=db_type)
            items = payload.get("items") if isinstance(payload, dict) else None
            live_databases[kind] = items if isinstance(items, list) else []
        except Exception:
            provider_available = False
            live_databases[kind] = []

    if not provider_available:
        return None

    declared_resources = definition.resources
    cross_references: list[dict[str, Any]] = []
    for kind in definition.resource_kinds:
        declared = declared_resources.get(kind, {})
        if not isinstance(declared, dict):
            continue
        declared_name = declared.get("database") or declared.get("bucket") or declared.get("key_prefix", "")
        live_items = live_databases.get(kind, [])
        found = any(
            isinstance(item, dict) and item.get("name") == declared_name for item in live_items
        ) if declared_name else False
        cross_references.append({
            "kind": kind,
            "declared_name": declared_name,
            "found_in_provider": found,
            "live_count": len(live_items),
        })

    return {
        "databases": live_databases,
        "cross_references": cross_references,
    }


def verify_app_resource(repo_root: Path, target: str, app: str) -> dict[str, Any]:
    repo_root = Path(repo_root).resolve()
    definition, raw_entry = resolve_app_resource(repo_root, target, app)
    projection = app_resource_inventory_projection(repo_root, target, app)
    expected_summary = _expected_app_resource_summary(raw_entry)
    declared_payload = _declared_payload(raw_entry)
    secret_statuses = _secret_file_statuses(repo_root, definition)
    secret_findings = validate_secret_files(repo_root, target, app, raw_entry)
    app_resource_summary_ok = (
        bool(projection.get("found")) and projection.get("app_resource_summary") == expected_summary
    )
    projection_check: dict[str, Any] = {
        "ok": app_resource_summary_ok,
        "actual": projection.get("app_resource_summary"),
        "expected": expected_summary,
    }
    if secret_findings:
        projection_check["ok"] = True
        projection_check["skipped"] = True
        projection_check["reason"] = "secret_files_invalid"

    live_evidence = _live_database_evidence(repo_root, target, definition)
    live_check: dict[str, Any] | None = None
    if live_evidence is not None:
        cross_refs = live_evidence.get("cross_references", [])
        all_found = all(ref.get("found_in_provider", False) for ref in cross_refs if ref.get("declared_name"))
        live_check = {
            "ok": all_found,
            "cross_references": cross_refs,
        }

    checks: dict[str, dict[str, Any]] = {
        "registry_owner": {
            "ok": definition.owner_app == definition.app,
            "actual": definition.owner_app,
            "expected": definition.app,
        },
        "secret_files": {"ok": not secret_findings, "findings": secret_findings},
        "inventory_projection": projection_check,
    }
    if live_check is not None:
        checks["live_provider"] = live_check
    failures = [
        name for name in ("registry_owner", "secret_files", "inventory_projection") if not bool(checks[name].get("ok"))
    ]
    if live_check is not None and not live_check.get("ok"):
        failures.append("live_provider")
    verification_fields = {
        "declared": declared_payload,
        "projection": projection,
        "secret_files": secret_statuses,
    }
    if live_evidence is not None:
        verification_fields["live_provider"] = live_evidence
    payload = build_verification_payload(
        canonical_ref=_canonical_ref(target, app),
        ledger_fields=_summary(definition),
        verification_fields=verification_fields,
        evidence=verification_fields,
        checks=checks,
        failures=failures,
        ok=not failures,
    )
    payload["resource"] = _summary(definition)
    evidence_list = [
        {"kind": "declared", "value": declared_payload},
        {"kind": "projection", "value": projection},
        {"kind": "secret_files", "value": secret_statuses},
    ]
    if live_evidence is not None:
        evidence_list.append({"kind": "live_provider", "value": live_evidence})
    payload["evidence"] = evidence_list
    return payload


def refresh_app_resource_ledger(repo_root: Path, target: str, *, write: bool) -> dict[str, Any]:
    return get_provider().refresh_app_resource_ledgers(repo_root, target, write=write)
