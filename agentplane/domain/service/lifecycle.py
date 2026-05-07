from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping

from agentplane.domain.service.registry import (
    DYNAMIC_CONTROL_PLANES,
    RESERVED_SERVICE_KEYS,
    SUPPORTED_SERVICE_TARGETS,
)
from agentplane.inventory.host_inventory import load_host_inventory

SERVICE_KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
SERVICE_SECTION_KEY = "services"


@dataclass(frozen=True)
class ServiceLifecycleMutation:
    path: Path
    target: str
    service_key: str
    action: Literal["onboard", "offboard"]
    changed: bool
    evidence: dict[str, Any]
    entry: dict[str, Any] | None = None


def plan_service_registry_onboard(
    services: Mapping[str, Any] | None,
    *,
    service_key: str,
    entry: Mapping[str, Any],
    allow_replace: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    normalized_key = _normalize_service_key(service_key)
    normalized_entry = _normalize_service_entry(entry)
    base_services = _services_dict(services)
    exists = normalized_key in base_services
    if exists and not allow_replace:
        raise ValueError(f"service registry already contains {normalized_key!r}")
    next_services: dict[str, Any] = dict(base_services)
    next_services[normalized_key] = normalized_entry
    return next_services, {"action": "upsert", "service_key": normalized_key, "replaced": exists}


def plan_service_registry_offboard(
    services: Mapping[str, Any] | None,
    *,
    service_key: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    normalized_key = _normalize_service_key(service_key)
    base_services = _services_dict(services)
    if normalized_key not in base_services:
        raise ValueError(f"service registry does not contain {normalized_key!r}")
    next_services: dict[str, Any] = dict(base_services)
    removed = next_services.pop(normalized_key)
    return next_services, {
        "action": "remove",
        "service_key": normalized_key,
        "removed_entry": removed,
    }


def apply_service_onboard(
    repo_root: Path,
    target: str,
    *,
    service_key: str,
    entry: Mapping[str, Any],
    allow_replace: bool = False,
    write: bool = True,
) -> ServiceLifecycleMutation:
    _ensure_supported_target(target)
    inventory_path = _inventory_path(repo_root, target)
    inventory = load_host_inventory(repo_root, target)
    services_section = inventory.get(SERVICE_SECTION_KEY)
    next_services, evidence = plan_service_registry_onboard(
        services_section,
        service_key=service_key,
        entry=entry,
        allow_replace=allow_replace,
    )
    original_services = _services_dict(services_section)
    changed = next_services != original_services
    if write and changed:
        inventory[SERVICE_SECTION_KEY] = next_services
        _write_inventory(inventory_path, inventory)
    normalized_key = evidence["service_key"]
    return ServiceLifecycleMutation(
        path=inventory_path,
        target=target,
        service_key=normalized_key,
        action="onboard",
        changed=changed,
        evidence=evidence,
        entry=_snapshot_entry(next_services.get(normalized_key)),
    )


def apply_service_offboard(
    repo_root: Path,
    target: str,
    *,
    service_key: str,
    write: bool = True,
) -> ServiceLifecycleMutation:
    _ensure_supported_target(target)
    inventory_path = _inventory_path(repo_root, target)
    inventory = load_host_inventory(repo_root, target)
    services_section = inventory.get(SERVICE_SECTION_KEY)
    normalized_key = _normalize_service_key(service_key)
    normalized_entry = _snapshot_entry(_services_dict(services_section).get(normalized_key))
    next_services, evidence = plan_service_registry_offboard(
        services_section,
        service_key=normalized_key,
    )
    original_services = _services_dict(services_section)
    changed = next_services != original_services
    if write and changed:
        inventory[SERVICE_SECTION_KEY] = next_services
        _write_inventory(inventory_path, inventory)
    normalized_key = evidence["service_key"]
    return ServiceLifecycleMutation(
        path=inventory_path,
        target=target,
        service_key=normalized_key,
        action="offboard",
        changed=changed,
        evidence=evidence,
        entry=normalized_entry,
    )


def _ensure_supported_target(target: str) -> None:
    if target not in SUPPORTED_SERVICE_TARGETS:
        raise ValueError(f"unsupported service target: {target!r}")


def _inventory_path(repo_root: Path, target: str) -> Path:
    return Path(repo_root) / "inventory" / "servers" / target / "inventory.json"


def _services_dict(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        return {}
    return {key: value for key, value in raw.items() if isinstance(key, str)}


def _normalize_service_key(service_key: str) -> str:
    if not isinstance(service_key, str):
        raise ValueError("service_key must be a string")
    normalized = service_key.strip()
    if not normalized:
        raise ValueError("service_key must be a non-empty string")
    if normalized in RESERVED_SERVICE_KEYS:
        raise ValueError(f"service_key {normalized!r} is reserved")
    if not SERVICE_KEY_PATTERN.match(normalized):
        raise ValueError(f"invalid service_key format: {normalized!r}")
    return normalized


def _normalize_service_entry(entry: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(entry, Mapping):
        raise ValueError("service entry must be a mapping")
    normalized: dict[str, Any] = {}
    for key, value in entry.items():
        if not isinstance(key, str) or not key:
            raise ValueError("service entry keys must be non-empty strings")
        normalized_value = value.strip() if isinstance(value, str) else value
        normalized[key] = normalized_value
    container_name = normalized.get("container_name")
    if not isinstance(container_name, str) or not container_name:
        raise ValueError("service entry requires a non-empty container_name")
    control_plane = normalized.get("control_plane")
    if control_plane is not None:
        if not isinstance(control_plane, str):
            raise ValueError("control_plane value must be a string")
        if control_plane not in DYNAMIC_CONTROL_PLANES:
            raise ValueError(f"unsupported control_plane value: {control_plane!r}")
    return normalized


def _snapshot_entry(value: Any) -> dict[str, Any] | None:
    if isinstance(value, Mapping):
        return dict(value)
    return None


def _write_inventory(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
