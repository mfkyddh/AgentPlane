from __future__ import annotations

import ipaddress
import json
from pathlib import Path
from typing import Any

from agentplane.domain.app.resource_state import APP_RESOURCE_SUMMARY_FIELDS, registry_secret_file
from agentplane.domain.infra.audit_common import (
    FORBIDDEN_PROD0_MARKERS,
    LEGACY_FLAT_SECRET_FILES,
    LEGACY_PORTS,
    RUNTIME_SERVICE_CONTROL_PLANES,
    _as_list,
    _load_json,
    _sub2api_inventory_entry,
    _TrackedJsonObject,
    _violation,
)


def _duplicate_json_key_paths(raw_text: str) -> set[str]:
    def _hook(pairs: list[tuple[str, Any]]) -> _TrackedJsonObject:
        obj: _TrackedJsonObject = _TrackedJsonObject()
        seen: set[str] = set()
        duplicates: set[str] = set()
        for key, value in pairs:
            if key in seen:
                duplicates.add(key)
            seen.add(key)
            obj[key] = value
        obj.duplicate_keys = duplicates
        return obj

    try:
        payload = json.loads(raw_text, object_pairs_hook=_hook)
    except json.JSONDecodeError:
        return set()

    paths: set[str] = set()

    def _walk(node: Any, path: list[str]) -> None:
        if isinstance(node, _TrackedJsonObject):
            for key in node.duplicate_keys:
                paths.add(".".join([*path, key]))
            for key, value in node.items():
                _walk(value, [*path, key])
            return
        if isinstance(node, list):
            for index, item in enumerate(node):
                _walk(item, [*path, str(index)])

    _walk(payload, [])
    return paths


def _find_legacy_flat_secret_references(node: Any) -> list[str]:
    refs: list[str] = []
    if isinstance(node, dict):
        for value in node.values():
            refs.extend(_find_legacy_flat_secret_references(value))
        return refs
    if isinstance(node, list):
        for item in node:
            refs.extend(_find_legacy_flat_secret_references(item))
        return refs
    if isinstance(node, str):
        for legacy in LEGACY_FLAT_SECRET_FILES:
            if legacy in node:
                refs.append(node)
                break
    return refs


def _formal_app_services(services: dict[str, Any]) -> dict[str, dict[str, Any]]:
    formal_apps: dict[str, dict[str, Any]] = {}
    for app_id, raw_service in services.items():
        if not isinstance(app_id, str) or not isinstance(raw_service, dict):
            continue
        control_plane = raw_service.get("control_plane")
        if not isinstance(control_plane, str) or not control_plane.strip():
            continue
        depends = raw_service.get("depends_on_containers")
        if not isinstance(depends, list):
            continue
        depends_text = " ".join(item.lower() for item in depends if isinstance(item, str))
        if not any(kind in depends_text for kind in APP_RESOURCE_SUMMARY_FIELDS):
            continue
        formal_apps[app_id] = raw_service
    return formal_apps


def _app_resource_summary_registry_mismatches(
    app_id: str,
    inventory_summary: dict[str, Any],
    registry_entry: dict[str, Any],
) -> list[str]:
    mismatches: list[str] = []
    for kind, fields in APP_RESOURCE_SUMMARY_FIELDS.items():
        inventory_spec = inventory_summary.get(kind)
        registry_spec = registry_entry.get(kind)
        if not isinstance(inventory_spec, dict) and not isinstance(registry_spec, dict):
            continue
        if not isinstance(inventory_spec, dict) or not isinstance(registry_spec, dict):
            mismatches.append(f"{kind} missing")
            continue
        for field in fields:
            if inventory_spec.get(field) != registry_spec.get(field):
                mismatches.append(
                    f"{kind}.{field} inventory={inventory_spec.get(field)!r} registry={registry_spec.get(field)!r}"
                )
        registry_secret_path = registry_secret_file(registry_entry, kind)
        if isinstance(registry_secret_path, str):
            if inventory_spec.get("secret_file") != registry_secret_path:
                mismatches.append(
                    f"{kind}.secret_file inventory={inventory_spec.get('secret_file')!r} registry={registry_secret_path!r}"
                )
        if not isinstance(registry_entry.get("owner_app"), str):
            mismatches.append(f"{app_id}.owner_app missing")
    return mismatches


def _audit_prod0_app_resource_summary_consistency(
    repo_root: Path, inventory_file: Path, payload: dict[str, Any]
) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    services = payload.get("services")
    if not isinstance(services, dict):
        return violations

    formal_apps = _formal_app_services(services)
    registry_file = repo_root / "inventory" / "servers" / "prod0-main" / "app-resources.json"
    if not registry_file.exists():
        if formal_apps:
            violations.append(
                _violation(
                    "prod0",
                    "prod0.app_resource.registry_missing",
                    "inventory 已登记 formal app，但缺少 app-resources.json。",
                    path=registry_file,
                    details={"apps": sorted(formal_apps)},
                )
            )
        return violations

    try:
        registry = json.loads(registry_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        violations.append(
            _violation(
                "prod0",
                "prod0.app_resource.registry_invalid_json",
                "app-resources.json 不是合法 JSON。",
                path=registry_file,
                details={"error": str(exc)},
            )
        )
        return violations
    if not isinstance(registry, dict):
        violations.append(
            _violation(
                "prod0",
                "prod0.app_resource.registry_invalid_shape",
                "app-resources.json 顶层必须是对象。",
                path=registry_file,
            )
        )
        return violations

    for app_id, service in formal_apps.items():
        app_resource_summary = service.get("app_resource_summary")
        if not isinstance(app_resource_summary, dict):
            violations.append(
                _violation(
                    "prod0",
                    "prod0.app_resource.summary_missing",
                    "formal app 缺少 app_resource_summary。",
                    path=inventory_file,
                    details={"app": app_id},
                )
            )
            continue
        registry_entry = registry.get(app_id)
        if not isinstance(registry_entry, dict):
            violations.append(
                _violation(
                    "prod0",
                    "prod0.app_resource.drift",
                    "inventory app_resource_summary 与 registry 不一致。",
                    path=inventory_file,
                    details={"app": app_id, "mismatches": [f"{app_id} missing in registry"]},
                )
            )
            continue
        mismatches = _app_resource_summary_registry_mismatches(app_id, app_resource_summary, registry_entry)
        if mismatches:
            violations.append(
                _violation(
                    "prod0",
                    "prod0.app_resource.drift",
                    "inventory app_resource_summary 与 registry 不一致。",
                    path=inventory_file,
                    details={"app": app_id, "mismatches": mismatches},
                )
            )
    return violations


def _openresty_declared_public_ports(payload: dict[str, Any]) -> tuple[list[Any], list[Any], list[Any]]:
    security_ports = _as_list(payload.get("security", {}).get("openresty_public_listen", {}).get("ports"))
    service_ports = _as_list(payload.get("services", {}).get("onepanel_openresty", {}).get("listen_ports"))
    declared_ports = security_ports if security_ports else service_ports
    return security_ports, service_ports, declared_ports


def _audit_openresty_contract(scope: str, inventory_file: Path, payload: dict[str, Any]) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    security_ports, service_ports, declared_ports = _openresty_declared_public_ports(payload)
    legacy_ports_found = sorted(port for port in declared_ports if isinstance(port, int) and port in LEGACY_PORTS)
    if (
        not declared_ports
        or legacy_ports_found
        or (security_ports and service_ports and security_ports != service_ports)
    ):
        violations.append(
            _violation(
                scope,
                f"{scope}.openresty.listen_ports",
                (
                    f"{scope} OpenResty 公网端口必须来自 inventory 声明，不能包含 2053/2054；"
                    "若同时声明 security.openresty_public_listen.ports 与 "
                    "services.onepanel_openresty.listen_ports，则两者必须一致。"
                ),
                path=inventory_file,
                details={
                    "declared_ports": declared_ports,
                    "security_ports": security_ports,
                    "service_ports": service_ports,
                    "legacy_ports": legacy_ports_found,
                },
            )
        )

    network_mode = payload.get("services", {}).get("onepanel_openresty", {}).get("network_mode")
    if isinstance(payload.get("services", {}).get("onepanel_openresty"), dict) and network_mode != "infra":
        violations.append(
            _violation(
                scope,
                f"{scope}.openresty.network_mode",
                f"{scope} onepanel_openresty 必须使用 host 网络。",
                path=inventory_file,
                details={"actual": network_mode},
            )
        )
    return violations


def _audit_managed_bridge_network_declarations(
    scope: str, inventory_file: Path, payload: dict[str, Any]
) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    raw = payload.get("managed_bridge_networks")
    if not isinstance(raw, list) or not raw:
        violations.append(
            _violation(
                scope,
                f"{scope}.bridge_network.declaration",
                f"{scope} inventory 必须声明非空 managed_bridge_networks。",
                path=inventory_file,
            )
        )
        return violations

    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            violations.append(
                _violation(
                    scope,
                    f"{scope}.bridge_network.declaration",
                    "managed_bridge_networks 项必须是对象。",
                    path=inventory_file,
                    details={"index": index},
                )
            )
            continue

        required_fields = ("name", "driver", "subnet", "gateway_ip")
        missing_fields = [
            field
            for field in required_fields
            if not isinstance(item.get(field), str) or not str(item.get(field)).strip()
        ]
        if missing_fields:
            violations.append(
                _violation(
                    scope,
                    f"{scope}.bridge_network.declaration",
                    "managed_bridge_networks 缺少必填字段。",
                    path=inventory_file,
                    details={"index": index, "missing_fields": missing_fields},
                )
            )
            continue

        if item.get("driver") != "bridge":
            violations.append(
                _violation(
                    scope,
                    f"{scope}.bridge_network.declaration",
                    "managed_bridge_networks.driver 当前只支持 bridge。",
                    path=inventory_file,
                    details={"index": index, "driver": item.get("driver")},
                )
            )

        try:
            subnet = ipaddress.ip_network(str(item["subnet"]), strict=True)
            gateway = ipaddress.ip_interface(str(item["gateway_ip"]))
            if gateway.network != subnet:
                violations.append(
                    _violation(
                        scope,
                        f"{scope}.bridge_network.declaration",
                        "managed_bridge_networks.gateway_ip 必须位于 subnet 内。",
                        path=inventory_file,
                        details={"index": index, "subnet": item["subnet"], "gateway_ip": item["gateway_ip"]},
                    )
                )
        except ValueError as exc:
            violations.append(
                _violation(
                    scope,
                    f"{scope}.bridge_network.declaration",
                    "managed_bridge_networks 的 subnet/gateway_ip 不是合法 CIDR。",
                    path=inventory_file,
                    details={"index": index, "error": str(exc)},
                )
            )

        required_for = item.get("required_for", [])
        if required_for is not None and (
            not isinstance(required_for, list)
            or any(not isinstance(entry, str) or not entry.strip() for entry in required_for)
        ):
            violations.append(
                _violation(
                    scope,
                    f"{scope}.bridge_network.declaration",
                    "managed_bridge_networks.required_for 必须是字符串列表。",
                    path=inventory_file,
                    details={"index": index},
                )
            )
    return violations


def _audit_runtime_service_summary_contract(
    scope: str, inventory_file: Path, payload: dict[str, Any]
) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    services = payload.get("services")
    if not isinstance(services, dict):
        return violations

    for service_name, service_payload in sorted(services.items()):
        if not isinstance(service_name, str) or not isinstance(service_payload, dict):
            continue
        runtime_root = service_payload.get("runtime_root")
        rollback_entry = service_payload.get("rollback_entry")
        # 仅约束已经进入"运行态+回滚态"模型的服务，避免把静态对象误判为 runtime 服务。
        if not isinstance(runtime_root, str) or not runtime_root.strip() or not isinstance(rollback_entry, dict):
            continue

        missing: list[str] = []
        control_plane = service_payload.get("control_plane")
        container_name = service_payload.get("container_name")
        rollback_kind = rollback_entry.get("kind")
        if not isinstance(control_plane, str) or control_plane not in RUNTIME_SERVICE_CONTROL_PLANES:
            missing.append("control_plane")
        if not isinstance(container_name, str) or not container_name.strip():
            missing.append("container_name")
        if not isinstance(rollback_kind, str) or not rollback_kind.strip():
            missing.append("rollback_entry.kind")
        if missing:
            violations.append(
                _violation(
                    scope,
                    f"{scope}.service.runtime_summary_contract",
                    (
                        f"{scope} runtime service 必须同时提供可生成统一服务摘要的最小字段："
                        "control_plane/container_name/runtime_root/rollback_entry.kind。"
                    ),
                    path=inventory_file,
                    details={"service": service_name, "missing": missing},
                )
            )
    return violations


def _audit_prod0_inventory(repo_root: Path) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    inventory_file = repo_root / "inventory" / "servers" / "prod0-main" / "inventory.json"
    raw_text = inventory_file.read_text(encoding="utf-8") if inventory_file.exists() else ""
    payload, error = _load_json(inventory_file, "prod0")
    if error is not None:
        return [error]
    assert payload is not None

    violations.extend(_audit_openresty_contract("prod0", inventory_file, payload))
    violations.extend(_audit_managed_bridge_network_declarations("prod", inventory_file, payload))

    services = payload.get("services", {})
    if not isinstance(services, dict):
        services = {}
    formal_apps = _formal_app_services(services)
    for duplicate_path in sorted(_duplicate_json_key_paths(raw_text)):
        path_parts = duplicate_path.split(".")
        if len(path_parts) != 3 or path_parts[0] != "services" or path_parts[2] != "app_resource_summary":
            continue
        app_id = path_parts[1]
        if app_id not in formal_apps:
            continue
        violations.append(
            _violation(
                "prod0",
                "prod0.app_resource.summary_duplicate",
                "formal app 在 inventory.json 中出现重复 app_resource_summary block。",
                path=inventory_file,
                details={"app": app_id, "json_path": duplicate_path},
            )
        )
    for app_id, service in formal_apps.items():
        references = sorted(set(_find_legacy_flat_secret_references(service)))
        if references:
            violations.append(
                _violation(
                    "prod0",
                    "prod0.app_resource.legacy_flat_secret_reference",
                    "formal app 仍引用 legacy flat secrets/services/<service>.* 文件。",
                    path=inventory_file,
                    details={"app": app_id, "references": references},
                )
            )

    sub2api = _sub2api_inventory_entry(services)
    sub2api_data_dir = sub2api.get("data_dir")
    sub2api_config_file = sub2api.get("config_file")
    sub2api_config_files = _as_list(sub2api.get("config_files"))
    if not sub2api_config_file and sub2api_config_files:
        sub2api_config_file = sub2api_config_files[0]

    if not isinstance(sub2api_data_dir, str) or not sub2api_data_dir.startswith("/data/sub2api/"):
        violations.append(
            _violation(
                "prod0",
                "prod0.sub2api.data_dir",
                "prod0 sub2api 数据目录必须收口到 /data/sub2api。",
                path=inventory_file,
                details={"actual": sub2api_data_dir},
            )
        )
    if not isinstance(sub2api_config_file, str) or not sub2api_config_file.startswith("/data/sub2api/"):
        violations.append(
            _violation(
                "prod0",
                "prod0.sub2api.config_file",
                "prod0 sub2api 配置文件必须收口到 /data/sub2api。",
                path=inventory_file,
                details={"actual": sub2api_config_file},
            )
        )

    for marker in FORBIDDEN_PROD0_MARKERS:
        if marker in raw_text:
            violations.append(
                _violation(
                    "prod0",
                    "prod0.inventory.legacy_marker",
                    "prod0 inventory 仍包含已退役的 legacy 术语或路径。",
                    path=inventory_file,
                    details={"marker": marker},
                )
            )
    violations.extend(_audit_runtime_service_summary_contract("prod0", inventory_file, payload))
    violations.extend(_audit_prod0_app_resource_summary_consistency(repo_root, inventory_file, payload))
    return violations
