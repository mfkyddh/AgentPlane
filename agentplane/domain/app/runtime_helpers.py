from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentplane.domain.app.contracts import has_public_ingress, load_yaml, public_sites
from agentplane.domain.app.resource_paths import secrets_root as shared_secrets_root
from agentplane.domain.targets import is_production_target, remote_compose_filename, target_alias
from agentplane.runtime.wsl_bridge import wsl_unc_to_posix


def load_inventory(repo_root: Path, target: str) -> tuple[Path, dict[str, Any]]:
    inventory_file = repo_root / "inventory" / "servers" / target / "inventory.json"
    if not inventory_file.exists():
        return inventory_file, {}
    payload = json.loads(inventory_file.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"inventory 顶层必须是对象: {inventory_file}")
    return inventory_file, payload


def nested_get(payload: dict[str, Any], dotted_key: str) -> Any:
    current: Any = payload
    for part in dotted_key.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def render_domain_path(path: Path | str) -> str:
    wsl_posix = wsl_unc_to_posix(path)
    if wsl_posix is not None:
        return wsl_posix.as_posix()
    if isinstance(path, Path):
        rendered = str(path)
    else:
        rendered = path
    return rendered.replace("\\", "/") if rendered.startswith("/") else rendered


def _is_production_target(target: str) -> bool:
    return is_production_target(target)


def _target_alias(target: str) -> str:
    return target_alias(target)


def _remote_compose_filename(target: str) -> str:
    return remote_compose_filename(target)


def _prod0_data_env_path(app_id: str, *, candidate_suffix: str | None = None) -> str | None:
    if app_id != "sub2api":
        return None
    filename = f"{app_id}-prod"
    if candidate_suffix:
        filename = f"{filename}.candidate.{candidate_suffix}"
    return f"/data/{app_id}/config/{filename}.env"


def _remote_env_path(app_id: str, target: str, *, candidate_suffix: str | None = None) -> str:
    if target == "prod0-main":
        data_path = _prod0_data_env_path(app_id, candidate_suffix=candidate_suffix)
        if data_path:
            return data_path
    candidate_fragment = f".candidate.{candidate_suffix}" if candidate_suffix else ""
    return f"/opt/agentplane/secrets/services/{app_id}.{_target_alias(target)}{candidate_fragment}.env"


def _remote_env_parent(remote_env: str) -> str:
    return str(Path(remote_env).parent).replace("\\", "/")


def _secrets_root(repo_root: Path) -> Path:
    return shared_secrets_root(repo_root)


def _payload_path(path: Path | str) -> str:
    rendered = str(path)
    if len(rendered) >= 2 and rendered[0].isalpha() and rendered[1] == ":":
        return rendered
    return rendered.replace("\\", "/")


def _split_host_binding(host_binding: str) -> tuple[str, str]:
    host, sep, port = host_binding.rpartition(":")
    if not sep or not port:
        raise ValueError(f"runtime.host_binding 格式不合法: {host_binding}")
    return host or "127.0.0.1", port


def _port_mapping(runtime: dict[str, Any], *, target: str) -> str:
    _, host_port = _split_host_binding(str(runtime["host_binding"]))
    host_ip = "0.0.0.0" if target == "wsl" else "127.0.0.1"
    return f"{host_ip}:{host_port}:{runtime['container_port']}"


def _runtime_base_url(runtime: dict[str, Any], *, target: str) -> str:
    _, host_port = _split_host_binding(str(runtime["host_binding"]))
    host = "127.0.0.1"
    if _is_production_target(target):
        return ""
    return f"http://{host}:{host_port}"


def _healthcheck_url(contract: dict[str, Any], *, target: str) -> str:
    runtime = contract["runtime"]
    health_path = str(runtime["healthcheck"]["path"])
    if target == "wsl":
        return f"{_runtime_base_url(runtime, target=target)}{health_path}"
    sites = public_sites(contract)
    if not sites:
        _, host_port = _split_host_binding(str(runtime["host_binding"]))
        return f"http://127.0.0.1:{host_port}{health_path}"
    public_url = str(sites[0]["public_url"]).rstrip("/")
    return f"{public_url}{health_path}"


def _origin_health_wait_command(contract: dict[str, Any], *, container_name: str) -> str:
    runtime = contract["runtime"]
    host_port = _split_host_binding(str(runtime["host_binding"]))[1]
    health_path = str(runtime["healthcheck"]["path"])
    health_command = f"curl -fsS http://127.0.0.1:{host_port}{health_path}"
    inspect_format = "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}"
    return (
        "for i in $(seq 1 12); do "
        f"status=$(docker inspect {container_name} --format '{inspect_format}' 2>/dev/null || true); "
        f'if [ "$status" = healthy ]; then {health_command}; exit 0; fi; '
        f'if [ "$status" = running ] && {health_command} >/dev/null 2>&1; then {health_command}; exit 0; fi; '
        "sleep 5; "
        "done; "
        f"{health_command}"
    )


def _inventory_public_url(contract: dict[str, Any], *, target: str) -> str:
    if target == "wsl":
        return _runtime_base_url(contract["runtime"], target=target)
    if not has_public_ingress(contract):
        _, host_port = _split_host_binding(str(contract["runtime"]["host_binding"]))
        return f"internal://127.0.0.1:{host_port}"
    return str(public_sites(contract)[0]["public_url"])


def _runtime_container_name(app_id: str, runtime: dict[str, Any], *, target: str) -> str:
    return str(runtime["container_name"]) if _is_production_target(target) else f"{app_id}-dev"


def _inventory_host_binding(runtime: dict[str, Any], *, target: str) -> str:
    _, host_port = _split_host_binding(str(runtime["host_binding"]))
    host_ip = "0.0.0.0" if target == "wsl" else "127.0.0.1"
    return f"{host_ip}:{host_port}"


def _target_dependency_names(depends: list[str], *, target: str) -> list[str]:
    if target != "wsl":
        return depends
    target_names: list[str] = []
    for item in depends:
        if item.endswith("-prod"):
            target_names.append(f"{item[:-5]}-dev")
        else:
            target_names.append(item)
    return target_names


def _target_config_files(repo_root: Path, app_id: str, runtime: dict[str, Any], *, target: str) -> list[str]:
    if target == "wsl":
        return [str(_secrets_root(repo_root) / "services" / f"{app_id}.wsl.env")]
    prod0_data_env = _prod0_data_env_path(app_id) if target == "prod0-main" else None
    if prod0_data_env:
        return [prod0_data_env]
    config_files = runtime.get("config_files")
    if isinstance(config_files, list) and config_files:
        return config_files
    return [_remote_env_path(app_id, target)]


def _compose_template_path(repo_root: Path, app_id: str, *, target: str) -> Path:
    if target == "wsl":
        return repo_root / "infra" / "compose" / app_id / "docker-compose.wsl.yml"
    return repo_root / "infra" / "compose" / app_id / _remote_compose_filename(target)


def _target_docker_networks(repo_root: Path, app_id: str, *, target: str) -> list[str]:
    template_path = _compose_template_path(repo_root, app_id, target=target)
    if not template_path.is_file():
        return []
    compose = load_yaml(template_path)
    service = compose.get("services", {}).get(app_id)
    if not isinstance(service, dict):
        return []
    networks = service.get("networks")
    if not isinstance(networks, list):
        return []
    return [str(item) for item in networks if isinstance(item, str) and item]


def _default_dependency_env(depends: list[str], contract: dict[str, Any], *, target: str) -> dict[str, str]:
    tenant_resources = nested_get(contract, "infra.tenant_resources")
    if not isinstance(tenant_resources, dict):
        return {}

    target_depends = _target_dependency_names(depends, target=target)
    env: dict[str, str] = {}
    if "postgres" in tenant_resources:
        postgres_host = next((item for item in target_depends if "postgres" in item), "")
        if postgres_host:
            env["DATABASE_HOST"] = postgres_host
    if "redis" in tenant_resources:
        redis_host = next((item for item in target_depends if "redis" in item), "")
        if redis_host:
            env["REDIS_HOST"] = redis_host
    return env


def _service_env_path(repo_root: Path, app_id: str, target: str) -> Path:
    if target == "wsl":
        return _secrets_root(repo_root) / "services" / f"{app_id}.wsl.env"
    if _is_production_target(target):
        return _secrets_root(repo_root) / "services" / f"{app_id}.{_target_alias(target)}.env"
    raise ValueError(f"Unsupported target for env path: {target}")
