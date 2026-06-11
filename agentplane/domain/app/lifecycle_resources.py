"""Resource registry, secret lifecycle, and ingress data helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from agentplane.domain.app.resource_paths import (
    app_resource_secret_dir,
    app_resource_secret_relative,
    resolve_secret_file_path,
)
from agentplane.domain.app.truth_lifecycle import (
    load_json_file,
    make_app_resource_registry_entry,
)
from agentplane.domain.ingress.models import IngressDefinition

if TYPE_CHECKING:
    from agentplane.domain.app.lifecycle import ValidatedDeliveryContract


def _canonical_secret_files(*, target: str, app: str, tenant_resources: dict[str, Any]) -> list[str]:
    secret_files: list[str] = []
    for kind in sorted(tenant_resources):
        secret_files.append(app_resource_secret_relative(target, app, kind))
    return secret_files


def _resource_registry_path(repo_root: Path, target: str) -> Path:
    return repo_root / "inventory" / "servers" / target / "app-resources.json"


def _load_resource_registry(repo_root: Path, target: str) -> dict[str, Any]:
    return load_json_file(_resource_registry_path(repo_root, target))


def _write_resource_registry(path: Path, registry: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _build_resource_registry_entry(validated: ValidatedDeliveryContract, *, target: str) -> dict[str, Any]:
    tenant_resources = validated.contract.get("infra", {}).get("tenant_resources")
    resolved_resources = tenant_resources if isinstance(tenant_resources, dict) else {}
    return make_app_resource_registry_entry(
        app_id=validated.app,
        resources={kind: value for kind, value in resolved_resources.items() if isinstance(value, dict)},
        secret_files=_canonical_secret_files(target=target, app=validated.app, tenant_resources=resolved_resources),
        ledger_status={"local_secret_presence": "planned"},
    )


def _secret_files_from_registry_entry(
    registry_entry: dict[str, Any] | None,
    *,
    target: str,
    app: str,
    tenant_resources: dict[str, Any] | None = None,
) -> list[str]:
    if isinstance(registry_entry, dict):
        secret_files = registry_entry.get("secret_files")
        if isinstance(secret_files, list):
            resolved = [item for item in secret_files if isinstance(item, str) and item]
            if resolved:
                return resolved
    return _canonical_secret_files(target=target, app=app, tenant_resources=tenant_resources or {})


def _fallback_secret_plan(
    *,
    repo_root: Path,
    target: str,
    app: str,
    operation: str,
    secret_files: list[str],
) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    missing: list[str] = []
    for relative_path in secret_files:
        resolved = resolve_secret_file_path(repo_root, relative_path)
        exists = resolved.is_file()
        files.append({"relative": relative_path, "path": str(resolved), "exists": exists})
        if not exists:
            missing.append(relative_path)
    return {
        "operation": operation,
        "target": target,
        "app": app,
        "planned": True,
        "guarded": operation == "retire",
        "files": files,
        "missing_files": missing,
        "secret_root": str(app_resource_secret_dir(repo_root, target, app)),
    }


def _fallback_secret_apply(
    *,
    repo_root: Path,
    operation: str,
    secret_files: list[str],
) -> dict[str, Any]:
    changed_files: list[str] = []
    for relative_path in secret_files:
        resolved = resolve_secret_file_path(repo_root, relative_path)
        if operation == "allocate":
            if not resolved.is_file():
                resolved.parent.mkdir(parents=True, exist_ok=True)
                resolved.write_text("", encoding="utf-8")
                resolved.chmod(0o600)
                changed_files.append(str(resolved))
        else:
            if resolved.is_file():
                resolved.unlink()
                changed_files.append(str(resolved))
    key = "created_files" if operation == "allocate" else "removed_files"
    return {key: changed_files, "fallback": True}


def _ingress_sites(contract: dict[str, Any]) -> list[dict[str, Any]]:
    top_level = contract.get("public_sites")
    if isinstance(top_level, list):
        return [site for site in top_level if isinstance(site, dict)]
    ingress_sites = contract.get("ingress", {}).get("public_sites")
    if isinstance(ingress_sites, list):
        return [site for site in ingress_sites if isinstance(site, dict)]
    return []


def _ingress_definitions(validated: ValidatedDeliveryContract) -> list[IngressDefinition]:
    runtime = validated.contract.get("runtime", {})
    proxy = f"http://{runtime.get('host_binding', '127.0.0.1:80')}"
    definitions: list[IngressDefinition] = []
    for site in _ingress_sites(validated.contract):
        alias = str(site.get("website_object") or site.get("alias") or validated.app)
        primary_domain = str(site.get("domain") or site.get("primary_domain") or alias)
        public_url = str(site.get("public_url") or "")
        definitions.append(
            IngressDefinition(
                alias=alias,
                primary_domain=primary_domain,
                public_url=public_url,
                proxy=proxy,
                status=str(site.get("status") or ""),
                config_file=str(site.get("config_file") or ""),
                control_plane=str(site.get("control_plane") or "onepanel"),
            )
        )
    return definitions
