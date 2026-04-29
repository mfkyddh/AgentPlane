from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentplane.domain.service.models import ServiceDefinition
from agentplane.domain.targets import SUPPORTED_SERVICE_TARGETS

FIXED_SERVICE_DEFINITIONS: dict[str, ServiceDefinition] = {
    "postgres": ServiceDefinition(
        name="postgres",
        runtime_kind="docker",
        control_plane="compose",
        supported_operations=("restart", "reconcile"),
        supported_targets=SUPPORTED_SERVICE_TARGETS,
        inventory_key="postgres",
        metadata={"container_name_key": "container_name"},
    ),
    "redis": ServiceDefinition(
        name="redis",
        runtime_kind="docker",
        control_plane="compose",
        supported_operations=("restart", "reconcile"),
        supported_targets=SUPPORTED_SERVICE_TARGETS,
        inventory_key="redis",
        metadata={"container_name_key": "container_name"},
    ),
    "minio": ServiceDefinition(
        name="minio",
        runtime_kind="docker",
        control_plane="compose",
        supported_operations=("restart", "reconcile"),
        supported_targets=SUPPORTED_SERVICE_TARGETS,
        inventory_key="minio",
        metadata={"container_name_key": "container_name"},
    ),
    "mihomo": ServiceDefinition(
        name="mihomo",
        runtime_kind="systemd",
        control_plane="systemd",
        supported_operations=("restart", "reload"),
        supported_targets=("prod0-main",),
        metadata={"unit_name": "mihomo", "listen_port": 7890, "listen_host": "172.18.0.1"},
    ),
    "onepanel_openresty": ServiceDefinition(
        name="onepanel_openresty",
        runtime_kind="docker",
        control_plane="onepanel-app",
        supported_operations=("restart", "reload"),
        supported_targets=("prod0-main",),
        inventory_key="onepanel_openresty",
        metadata={"container_name_key": "container_name"},
    ),
}
_RESERVED_SERVICE_KEYS = {"public_ingresses", "docker", "onepanel"}
_DYNAMIC_CONTROL_PLANES = {"compose", "onepanel-app", "onepanel-compose"}
RESERVED_SERVICE_KEYS = frozenset(_RESERVED_SERVICE_KEYS)
DYNAMIC_CONTROL_PLANES = frozenset(_DYNAMIC_CONTROL_PLANES)


def load_target_inventory(repo_root: Path, target: str) -> dict[str, Any]:
    inventory_file = repo_root / "inventory" / "servers" / target / "inventory.json"
    if not inventory_file.is_file():
        raise ValueError(f"缺少 inventory 文件: {inventory_file}")
    payload = json.loads(inventory_file.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"inventory 顶层必须是对象: {inventory_file}")
    return payload


def _wsl_service_names(inventory: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    compose_services = inventory.get("compose_services")
    if isinstance(compose_services, list):
        for item in compose_services:
            if isinstance(item, str) and item in {"postgres", "redis", "minio"}:
                names.add(item)
    return names


def service_inventory_entry(inventory: dict[str, Any], definition: ServiceDefinition, *, target: str) -> dict[str, Any] | None:
    services = inventory.get("services")
    if isinstance(services, dict):
        raw = services.get(definition.inventory_key or definition.name)
        if isinstance(raw, dict):
            return raw
    if target == "wsl" and definition.name in _wsl_service_names(inventory):
        return {"service_name": definition.name, "control_plane": definition.control_plane}
    return None


def _dynamic_supported_operations(control_plane: str) -> tuple[str, ...]:
    if control_plane == "compose":
        return ("restart", "reconcile")
    return ("restart",)


def _dynamic_service_definition(name: str, declared: dict[str, Any], *, target: str) -> ServiceDefinition | None:
    control_plane = declared.get("control_plane")
    if not isinstance(control_plane, str) or control_plane not in _DYNAMIC_CONTROL_PLANES:
        return None
    container_name = declared.get("container_name")
    if not isinstance(container_name, str) or not container_name:
        return None
    metadata: dict[str, Any] = {"container_name_key": "container_name", "dynamic": True}
    if control_plane in {"compose", "onepanel-compose"}:
        metadata["projection_app"] = name
    return ServiceDefinition(
        name=name,
        runtime_kind="docker",
        control_plane=control_plane,
        supported_operations=_dynamic_supported_operations(control_plane),
        supported_targets=(target,),
        inventory_key=name,
        metadata=metadata,
    )


def _dynamic_services_for_target(inventory: dict[str, Any], *, target: str) -> list[tuple[ServiceDefinition, dict[str, Any]]]:
    services = inventory.get("services")
    if not isinstance(services, dict):
        return []

    items: list[tuple[ServiceDefinition, dict[str, Any]]] = []
    for name in sorted(services):
        if name in FIXED_SERVICE_DEFINITIONS or name in _RESERVED_SERVICE_KEYS:
            continue
        raw = services.get(name)
        if not isinstance(raw, dict):
            continue
        definition = _dynamic_service_definition(name, raw, target=target)
        if definition is None:
            continue
        items.append((definition, raw))
    return items


def available_services(repo_root: Path, target: str) -> list[tuple[ServiceDefinition, dict[str, Any] | None]]:
    inventory = load_target_inventory(repo_root, target)
    items: list[tuple[ServiceDefinition, dict[str, Any] | None]] = []
    for definition in FIXED_SERVICE_DEFINITIONS.values():
        if target not in definition.supported_targets:
            continue
        declared = service_inventory_entry(inventory, definition, target=target)
        if declared is None and definition.name != "mihomo":
            continue
        items.append((definition, declared))
    items.extend(_dynamic_services_for_target(inventory, target=target))
    return items


def resolve_service(repo_root: Path, target: str, name: str) -> tuple[ServiceDefinition, dict[str, Any] | None]:
    for definition, declared in available_services(repo_root, target):
        if definition.name == name:
            return definition, declared
    raise ValueError(f"unknown service for {target}: {name}")


def resolve_service_name(
    repo_root: Path,
    target: str,
    *,
    service_name: str = "",
    container_name: str = "",
    project_name: str = "",
) -> str:
    inventory = load_target_inventory(repo_root, target)
    services = inventory.get("services")
    if not isinstance(services, dict):
        raise ValueError(f"inventory.services 缺失: {target}")
    if service_name and service_name in services and isinstance(services[service_name], dict):
        return service_name
    for candidate, raw in services.items():
        if not isinstance(candidate, str) or not isinstance(raw, dict):
            continue
        if container_name and raw.get("container_name") == container_name:
            return candidate
        if project_name and raw.get("project_name") == project_name:
            return candidate
    raise ValueError(
        f"unable to resolve tracked service for {target}: service_name={service_name!r} container_name={container_name!r} project_name={project_name!r}"
    )
