from __future__ import annotations

import ipaddress
import json
from pathlib import Path
from typing import Any

from agentplane.cli.app_resource_state import APP_RESOURCE_SUMMARY_FIELDS, registry_secret_file
from agentplane.runtime.backends import build_backend_runner
from agentplane.runtime.execution import ExecutionBindings, ExecutionPlan
from agentplane.runtime.host_profile import HostProfile, detect_host_profile
from agentplane.runtime.target_resolver import TargetResolver

LEGACY_PORTS = {2053, 2054}
REQUIRED_NETWORK = "zqf_network"
SUPPORTED_AUDIT_ENVS = ("wsl", "prod0-main", "prod2-main")
RUNTIME_SERVICE_CONTROL_PLANES = {"compose", "onepanel-app", "onepanel-compose"}
FORBIDDEN_PROD0_MARKERS = (
    "nginx-ui",
    "nginxwebui",
    "/data/apps/nginx-ui-official",
    "/usr/local/sbin/renew_example_net_cert.sh",
    "2053",
    "2054",
)
LEGACY_FLAT_SECRET_FILES = (
    "secrets/services/postgres.env",
    "secrets/services/redis.conf",
    "secrets/services/minio.env",
)
_WSL_HOST_AUDIT_SCRIPT = """
import json
import pathlib
import sys

repo_root = pathlib.Path.cwd()
sys.path.insert(0, str(repo_root))
from agentplane.cli.audit import _audit_wsl_host_state

print(json.dumps(_audit_wsl_host_state(), ensure_ascii=False))
""".strip()


class _TrackedJsonObject(dict):
    duplicate_keys: set[str]


def _violation(
    scope: str,
    rule_id: str,
    message: str,
    *,
    path: Path | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "scope": scope,
        "id": rule_id,
        "severity": "error",
        "message": message,
    }
    if path is not None:
        item["path"] = str(path)
    if details:
        item["details"] = details
    return item

def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def _sub2api_inventory_entry(services: dict[str, Any]) -> dict[str, Any]:
    modern = services.get("sub2api")
    if isinstance(modern, dict) and modern:
        return modern
    legacy = services.get("token_backend")
    if isinstance(legacy, dict):
        return legacy
    return {}


def _audit_wsl_templates(repo_root: Path) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    compose_root = repo_root / "infra" / "compose"
    if not compose_root.is_dir():
        return violations
    expected_targets = _wsl_required_compose_targets(repo_root)

    for service_dir in sorted(path for path in compose_root.iterdir() if path.is_dir()):
        service_name = service_dir.name
        legacy_compose = service_dir / "docker-compose.yml"
        legacy_env = service_dir / ".env"
        required_wsl = service_dir / "docker-compose.wsl.yml"
        required_prod0 = service_dir / "docker-compose.prod0.yml"

        if legacy_compose.exists():
            violations.append(
                _violation(
                    "wsl",
                    "wsl.legacy.compose_entrypoint",
                    "发现 legacy docker-compose.yml；仓库规范要求使用 docker-compose.wsl.yml 与 docker-compose.prod0.yml。",
                    path=legacy_compose,
                )
            )
        if legacy_env.exists():
            violations.append(
                _violation(
                    "wsl",
                    "wsl.legacy.env_file",
                    "发现 legacy .env；仓库规范要求使用环境专用文件（如 .env.wsl / .env.prod0）。",
                    path=legacy_env,
                )
            )
        for private_env in sorted(service_dir.glob(".env.*")):
            if private_env.name.endswith(".example"):
                continue
            violations.append(
                _violation(
                    "wsl",
                    "wsl.compose.private_env_file",
                    "发现 compose 目录内的环境专用私有 env 文件；仓库规范要求将其收口到 secrets/services/。",
                    path=private_env,
                )
            )
        if service_name in expected_targets["wsl"] and not required_wsl.exists():
            violations.append(
                _violation(
                    "wsl",
                    "wsl.missing.compose_wsl",
                    "缺少 docker-compose.wsl.yml。",
                    path=required_wsl,
                )
            )
        if service_name in expected_targets["prod0-main"] and not required_prod0.exists():
            violations.append(
                _violation(
                    "wsl",
                    "wsl.missing.compose_prod0",
                    "缺少 docker-compose.prod0.yml。",
                    path=required_prod0,
                )
            )
    return violations


def _inventory_compose_service_names(inventory_file: Path, *, target: str) -> set[str]:
    if not inventory_file.exists():
        return set()
    try:
        payload = json.loads(inventory_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return set()
    services = payload.get("services")
    if not isinstance(services, dict):
        return set()

    names: set[str] = set()
    for service_name, service_payload in services.items():
        if not isinstance(service_name, str) or not isinstance(service_payload, dict):
            continue
        if target == "wsl":
            names.add(service_name)
            continue
        if service_payload.get("control_plane") == "compose":
            names.add(service_name)
    return names


def _wsl_required_compose_targets(repo_root: Path) -> dict[str, set[str]]:
    return {
        "wsl": _inventory_compose_service_names(
            repo_root / "inventory" / "servers" / "wsl" / "inventory.json",
            target="wsl",
        ),
        "prod0-main": _inventory_compose_service_names(
            repo_root / "inventory" / "servers" / "prod0-main" / "inventory.json",
            target="prod0-main",
        ),
    }


def _audit_wsl_host_state(repo_root: Path | None = None) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    resolved_repo_root = (repo_root or Path.cwd()).resolve(strict=False)
    forbidden_paths = (
        Path("/root/.cli-proxy-api"),
        Path("/root/8443-cutover"),
        Path("/tmp/1panel-src"),
    )
    for path in forbidden_paths:
        if path.exists():
            violations.append(
                _violation(
                    "wsl",
                    "wsl.host.legacy_path",
                    "发现应已清理的 WSL legacy 运行态目录。",
                    path=path,
                )
            )

    expected_symlinks = {
        Path("/root/.ssh/config"): resolved_repo_root / "secrets" / "ssh" / "config",
        Path("/root/.openclaw"): Path("/data/openclaw/config/home"),
        Path("/root/.local/share/openclaw-feishu-uat"): Path("/data/openclaw/config/openclaw-feishu-uat"),
    }
    for path, expected_target in expected_symlinks.items():
        if path.exists() and not path.is_symlink():
            violations.append(
                _violation(
                    "wsl",
                    "wsl.host.expected_symlink",
                    "发现应为符号链接的治理路径仍为实体文件或目录。",
                    path=path,
                    details={"expected_target": str(expected_target)},
                )
            )
        elif path.is_symlink():
            actual_target = path.resolve(strict=False)
            if actual_target != expected_target:
                violations.append(
                    _violation(
                        "wsl",
                        "wsl.host.symlink_target",
                        "治理路径的符号链接目标不符合规范。",
                        path=path,
                        details={"expected_target": str(expected_target), "actual_target": str(actual_target)},
                    )
                )

    for path in (
        Path("/data/openclaw/config/home"),
        Path("/data/openclaw/config/openclaw-feishu-uat"),
    ):
        if not path.exists():
            violations.append(
                _violation(
                    "wsl",
                    "wsl.host.required_data_path",
                    "缺少规范要求的 /data 持久化目录。",
                    path=path,
                )
            )
    return violations


def _wsl_backend_type(host_profile: HostProfile | None = None) -> str:
    profile = host_profile or detect_host_profile()
    return str(TargetResolver(profile).resolve("wsl").execution_backend)


def _audit_wsl_host_state_via_backend(
    repo_root: Path,
    *,
    backend_type: str,
    runner: Any | None = None,
) -> list[dict[str, Any]]:
    effective_runner = runner or build_backend_runner()
    plan = ExecutionPlan(
        backend_type=backend_type,  # type: ignore[arg-type]
        cwd_ref="workspace.control_root",
        argv=("python3", "-c", _WSL_HOST_AUDIT_SCRIPT),
        env_refs=(),
        input_refs=(),
        expected_outputs=("violations-json",),
        capabilities=("python3",),
        timeout=300,
    )
    result = effective_runner.execute(
        plan,
        bindings=ExecutionBindings(cwd_values={"workspace.control_root": repo_root}),
    )
    if not result.ok:
        raise ValueError(result.stdout or result.stderr or "failed to audit wsl host state via backend runner")
    payload = json.loads(result.stdout)
    if not isinstance(payload, list):
        raise ValueError("wsl audit backend payload must be a list")
    return [item for item in payload if isinstance(item, dict)]


def _load_json(path: Path, scope: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if not path.exists():
        return None, _violation(scope, f"{scope}.inventory.missing", f"缺少 {scope} inventory.json。", path=path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, _violation(
            scope,
            f"{scope}.inventory.invalid_json",
            f"{scope} inventory.json 不是合法 JSON。",
            path=path,
            details={"error": str(exc)},
        )
    if not isinstance(payload, dict):
        return None, _violation(
            scope,
            f"{scope}.inventory.invalid_shape",
            f"{scope} inventory.json 顶层必须是对象。",
            path=path,
        )
    return payload, None


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
    if not declared_ports or legacy_ports_found or (security_ports and service_ports and security_ports != service_ports):
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


def _audit_managed_bridge_network_declarations(scope: str, inventory_file: Path, payload: dict[str, Any]) -> list[dict[str, Any]]:
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
        missing_fields = [field for field in required_fields if not isinstance(item.get(field), str) or not str(item.get(field)).strip()]
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
            not isinstance(required_for, list) or any(not isinstance(entry, str) or not entry.strip() for entry in required_for)
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


def _audit_runtime_service_summary_contract(scope: str, inventory_file: Path, payload: dict[str, Any]) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    services = payload.get("services")
    if not isinstance(services, dict):
        return violations

    for service_name, service_payload in sorted(services.items()):
        if not isinstance(service_name, str) or not isinstance(service_payload, dict):
            continue
        runtime_root = service_payload.get("runtime_root")
        rollback_entry = service_payload.get("rollback_entry")
        # 仅约束已经进入“运行态+回滚态”模型的服务，避免把静态对象误判为 runtime 服务。
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


def _audit_prod2_inventory(repo_root: Path) -> list[dict[str, Any]]:
    inventory_file = repo_root / "inventory" / "servers" / "prod2-main" / "inventory.json"
    payload, error = _load_json(inventory_file, "prod2")
    if error is not None:
        return [error]
    assert payload is not None
    return (
        _audit_openresty_contract("prod2", inventory_file, payload)
        + _audit_managed_bridge_network_declarations("prod", inventory_file, payload)
        + _audit_runtime_service_summary_contract("prod2", inventory_file, payload)
    )


def audit_filesystem(
    repo_root: Path,
    target_env: str,
    *,
    host_profile: HostProfile | None = None,
    runner: Any | None = None,
) -> dict[str, Any]:
    resolved_root = repo_root.resolve()
    path_check_mode = "local-path"
    if target_env == "wsl":
        backend_type = _wsl_backend_type(host_profile)
        if backend_type == "windows-wsl" and runner is not None:
            path_check_mode = "backend-exec"
            host_violations = _audit_wsl_host_state_via_backend(resolved_root, backend_type=backend_type, runner=runner)
        elif backend_type == "windows-wsl":
            path_check_mode = "tracked-snapshot"
            host_violations = []
        else:
            host_violations = _audit_wsl_host_state(resolved_root)
        violations = _audit_wsl_templates(resolved_root) + host_violations
    elif target_env == "prod0-main":
        violations = _audit_prod0_inventory(resolved_root)
    elif target_env == "prod2-main":
        violations = _audit_prod2_inventory(resolved_root)
    else:
        raise ValueError(f"Unsupported audit env: {target_env}")
    return {
        "command": "audit filesystem",
        "env": target_env,
        "repo_root": str(resolved_root),
        "ok": not violations,
        "violations": violations,
        "path_check_mode": path_check_mode,
    }
