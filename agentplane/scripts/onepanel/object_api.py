#!/usr/bin/env python3
"""Object-oriented 1Panel API helpers for CLI-first operations."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .compose_policy import normalize_compose_for_app, requires_host_network


class FakeLikeExecutorProtocol:
    def api_request(self, method: str, path: str, body: dict[str, object] | None = None) -> object:
        raise NotImplementedError


def get_panel_summary(executor: FakeLikeExecutorProtocol) -> dict[str, Any]:
    result = executor.api_request("POST", "/api/v2/core/settings/search", {})
    if not isinstance(result, dict):
        raise ValueError("panel summary must be an object")
    return result


def search_websites(
    executor: FakeLikeExecutorProtocol,
    *,
    name: str = "",
    website_group_id: int = 0,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    result = executor.api_request(
        "POST",
        "/api/v2/websites/search",
        {
            "page": page,
            "pageSize": page_size,
            "name": name,
            "websiteGroupId": website_group_id,
            "orderBy": "created_at",
            "order": "descending",
        },
    )
    if not isinstance(result, dict):
        raise ValueError("website search must be an object")
    return result


def get_website(executor: FakeLikeExecutorProtocol, *, website_id: int) -> dict[str, Any]:
    website = executor.api_request("GET", f"/api/v2/websites/{website_id}")
    https = executor.api_request("GET", f"/api/v2/websites/{website_id}/https")
    if not isinstance(website, dict) or not isinstance(https, dict):
        raise ValueError("website detail must be objects")
    return {"website": website, "https": https}


def search_cronjobs(
    executor: FakeLikeExecutorProtocol,
    *,
    info: str = "",
    group_ids: list[int] | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    result = executor.api_request(
        "POST",
        "/api/v2/cronjobs/search",
        {
            "page": page,
            "pageSize": page_size,
            "info": info,
            "groupIDs": group_ids or [],
            "orderBy": "createdAt",
            "order": "descending",
        },
    )
    if not isinstance(result, dict):
        raise ValueError("cronjob search must be an object")
    return result


def load_cronjob(executor: FakeLikeExecutorProtocol, *, cronjob_id: int) -> dict[str, Any]:
    result = executor.api_request("POST", "/api/v2/cronjobs/load/info", {"id": cronjob_id})
    if not isinstance(result, dict):
        raise ValueError("cronjob detail must be an object")
    return result


def find_website_id(executor: FakeLikeExecutorProtocol, *, name: str = "", alias: str = "") -> int:
    query = alias or name
    payload = search_websites(executor, name=query)
    items = payload.get("items")
    if not isinstance(items, list):
        raise RuntimeError("website search returned no items")
    for item in items:
        if not isinstance(item, dict):
            continue
        if alias and item.get("alias") == alias:
            return int(item["id"])
        if name and item.get("primaryDomain") == name:
            return int(item["id"])
        if name and item.get("alias") == name:
            return int(item["id"])
    if items and isinstance(items[0], dict) and "id" in items[0]:
        return int(items[0]["id"])
    raise RuntimeError("website not found")


def find_cronjob_id(executor: FakeLikeExecutorProtocol, *, name: str) -> int:
    payload = search_cronjobs(executor, info=name)
    items = payload.get("items")
    if not isinstance(items, list):
        raise RuntimeError("cronjob search returned no items")
    for item in items:
        if isinstance(item, dict) and item.get("name") == name:
            return int(item["id"])
    if items and isinstance(items[0], dict) and "id" in items[0]:
        return int(items[0]["id"])
    raise RuntimeError(f"cronjob not found: {name}")


def search_containers(
    executor: FakeLikeExecutorProtocol,
    *,
    name: str = "",
    state: str = "",
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    result = executor.api_request(
        "POST",
        "/api/v2/containers/search",
        {
            "page": page,
            "pageSize": page_size,
            "name": name,
            "state": state,
            "filters": "",
            "orderBy": "created_at",
            "order": "descending",
        },
    )
    if not isinstance(result, dict):
        raise ValueError("container search must be an object")
    return result


def get_container(executor: FakeLikeExecutorProtocol, *, name: str) -> dict[str, Any]:
    result = executor.api_request("POST", "/api/v2/containers/info", {"name": name})
    if not isinstance(result, dict):
        raise ValueError("container detail must be an object")
    return result


def search_tasks(
    executor: FakeLikeExecutorProtocol,
    *,
    task_type: str = "",
    status: str = "",
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    result = executor.api_request(
        "POST",
        "/api/v2/logs/tasks/search",
        {
            "page": page,
            "pageSize": page_size,
            "type": task_type,
            "status": status,
        },
    )
    if not isinstance(result, dict):
        raise ValueError("task search must be an object")
    return result


def get_task_count(executor: FakeLikeExecutorProtocol) -> dict[str, Any]:
    result = executor.api_request("GET", "/api/v2/logs/tasks/executing/count")
    if isinstance(result, dict):
        return result
    return {"executing": result}


def search_installed_apps(
    executor: FakeLikeExecutorProtocol,
    *,
    name: str = "",
    app_type: str = "",
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    result = executor.api_request(
        "POST",
        "/api/v2/apps/installed/search",
        {
            "page": page,
            "pageSize": page_size,
            "name": name,
            "type": app_type,
            "unused": False,
            "all": False,
        },
    )
    if not isinstance(result, dict):
        raise ValueError("installed app search must be an object")
    return result


def get_installed_app(executor: FakeLikeExecutorProtocol, *, install_id: int) -> dict[str, Any]:
    result = executor.api_request("GET", f"/api/v2/apps/installed/info/{install_id}")
    if not isinstance(result, dict):
        raise ValueError("installed app detail must be an object")
    return result


def get_app_catalog(executor: FakeLikeExecutorProtocol, *, app_key: str) -> dict[str, Any]:
    result = executor.api_request("GET", f"/api/v2/apps/{app_key}")
    if not isinstance(result, dict):
        raise ValueError("app catalog detail must be an object")
    return result


def get_app_catalog_detail(
    executor: FakeLikeExecutorProtocol,
    *,
    app_id: int,
    version: str,
    app_type: str,
) -> dict[str, Any]:
    result = executor.api_request("GET", f"/api/v2/apps/detail/{app_id}/{version}/{app_type}")
    if not isinstance(result, dict):
        raise ValueError("app catalog version detail must be an object")
    return result


def _coerce_app_param(value: str) -> Any:
    if value.isdigit():
        return int(value)
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    return value


def _parse_app_params(raw_items: list[str]) -> dict[str, Any]:
    params: dict[str, Any] = {}
    for item in raw_items:
        if "=" not in item:
            raise ValueError(f"Invalid --param value: {item}")
        key, value = item.split("=", 1)
        params[key] = _coerce_app_param(value)
    return params


def _default_install_params_for_app(app_key: str) -> dict[str, Any]:
    if app_key == "openresty":
        return {
            "WEBSITE_DIR": "/data/1panel/www",
            "PANEL_APP_PORT_HTTP": 80,
            "PANEL_APP_PORT_HTTPS": 443,
        }
    return {}


def build_app_install_params(app_key: str, detail: dict[str, Any], raw_items: list[str] | None = None) -> dict[str, Any]:
    params: dict[str, Any] = {}
    detail_params = detail.get("params")
    if isinstance(detail_params, dict):
        form_fields = detail_params.get("formFields")
        if isinstance(form_fields, list):
            for field in form_fields:
                if isinstance(field, dict) and field.get("envKey") is not None:
                    params[str(field["envKey"])] = field.get("default")
    for key, value in _default_install_params_for_app(app_key).items():
        params.setdefault(key, value)
    params.update(_parse_app_params(raw_items or []))
    return params


def search_compose_projects(
    executor: FakeLikeExecutorProtocol,
    *,
    info: str = "",
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    result = executor.api_request(
        "POST",
        "/api/v2/containers/compose/search",
        {
            "page": page,
            "pageSize": page_size,
            "info": info,
            "orderBy": "created_at",
            "order": "descending",
        },
    )
    if not isinstance(result, dict):
        raise ValueError("project search must be an object")
    return result


def get_compose_project(executor: FakeLikeExecutorProtocol, *, name: str) -> dict[str, Any]:
    search = search_compose_projects(executor, info=name)
    items = search.get("items")
    if not isinstance(items, list):
        raise ValueError("project search items must be a list")
    for item in items:
        if isinstance(item, dict) and item.get("name") == name:
            return item
    raise RuntimeError(f"compose project not found: {name}")


def read_inventory_firewall(repo_root: Path, target: str) -> dict[str, Any]:
    inventory_file = repo_root / "inventory" / "servers" / target / "inventory.json"
    payload = json.loads(inventory_file.read_text(encoding="utf-8"))
    security = payload.get("security")
    if not isinstance(security, dict):
        return {}
    firewall = security.get("firewall")
    return firewall if isinstance(firewall, dict) else {}


def load_firewall_base(executor: FakeLikeExecutorProtocol, *, name: str = "port") -> dict[str, Any]:
    result = executor.api_request("POST", "/api/v2/hosts/firewall/base", {"name": name})
    if not isinstance(result, dict):
        raise ValueError("firewall base must be an object")
    return result


def search_firewall_rules(
    executor: FakeLikeExecutorProtocol,
    *,
    rule_type: str,
    info: str = "",
    status: str = "",
    strategy: str = "",
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    result = executor.api_request(
        "POST",
        "/api/v2/hosts/firewall/search",
        {
            "page": page,
            "pageSize": page_size,
            "info": info,
            "status": status,
            "strategy": strategy,
            "type": rule_type,
        },
    )
    if not isinstance(result, dict):
        raise ValueError("firewall search must be an object")
    return result


@dataclass(frozen=True)
class ObjectPlan:
    object_name: str
    mode: str
    path: str
    body: dict[str, Any]


def plan_panel_setting_update(*, key: str, value: str) -> ObjectPlan:
    return ObjectPlan("panel", "setting-update", "/api/v2/core/settings/update", {"key": key, "value": value})


def plan_website_create(
    *,
    alias: str,
    domain: str,
    proxy: str,
    website_group_id: int = 1,
    website_type: str = "proxy",
    remark: str = "",
    ipv6: bool = True,
) -> ObjectPlan:
    return ObjectPlan(
        "website",
        "create",
        "/api/v2/websites",
        {
            "alias": alias,
            "type": website_type,
            "appType": "new",
            "proxy": proxy,
            "remark": remark,
            "webSiteGroupID": website_group_id,
            "IPV6": ipv6,
            "domains": [{"domain": domain, "port": 80, "ssl": False}],
        },
    )


def plan_cronjob_operation(*, mode: str, body: dict[str, Any]) -> ObjectPlan:
    supported = {
        "create": "/api/v2/cronjobs",
        "update": "/api/v2/cronjobs/update",
        "handle": "/api/v2/cronjobs/handle",
        "status": "/api/v2/cronjobs/status",
    }
    if mode not in supported:
        raise ValueError(f"unsupported cronjob plan mode: {mode}")
    return ObjectPlan("cronjob", mode, supported[mode], body)


def plan_installed_app_operation(*, install_id: int, operate: str) -> ObjectPlan:
    return ObjectPlan(
        "app",
        operate,
        "/api/v2/apps/installed/op",
        {
            "installId": install_id,
            "operate": operate,
            "forceDelete": False,
            "deleteBackup": False,
            "deleteDB": False,
            "deleteImage": False,
            "backup": False,
            "pullImage": False,
            "dockerCompose": "",
            "favorite": False,
        },
    )


def plan_installed_app_params_update(*, install_id: int, params: dict[str, Any]) -> ObjectPlan:
    return ObjectPlan(
        "app",
        "params-update",
        "/api/v2/apps/installed/params/update",
        {
            "installId": install_id,
            "params": params,
        },
    )


def plan_app_install(
    *,
    app_key: str,
    app_type: str,
    detail: dict[str, Any],
    name: str = "",
    container_name: str = "",
    raw_params: list[str] | None = None,
    pull_image: bool = False,
    specify_ip: str = "",
    restart_policy: str = "always",
) -> ObjectPlan:
    detail_id = detail.get("id")
    docker_compose = detail.get("dockerCompose")
    if detail_id is None:
        raise ValueError("app catalog detail missing id")
    if not isinstance(docker_compose, str):
        raise ValueError("app catalog detail missing dockerCompose")
    return ObjectPlan(
        "app",
        "install",
        "/api/v2/apps/install",
        {
            "appDetailId": int(detail_id),
            "name": name or app_key,
            "params": build_app_install_params(app_key, detail, raw_params),
            "advanced": True,
            "cpuQuota": 0,
            "memoryLimit": 0,
            "memoryUnit": "M",
            "containerName": container_name,
            "allowPort": True,
            "editCompose": True,
            "dockerCompose": normalize_compose_for_app(app_key, docker_compose),
            "hostMode": requires_host_network(app_key) or bool(detail.get("hostMode", False)),
            "pullImage": pull_image,
            "gpuConfig": False,
            "webUI": "",
            "type": app_type,
            "specifyIP": specify_ip,
            "restartPolicy": restart_policy,
        },
    )


def plan_compose_project_operation(*, name: str, operation: str, with_file: bool = False, force: bool = False) -> ObjectPlan:
    project_path = f"/data/1panel/docker/compose/{name}/docker-compose.yml"
    return ObjectPlan(
        "project",
        operation,
        "/api/v2/containers/compose/operate",
        {
            "name": name,
            "path": project_path,
            "operation": operation,
            "withFile": with_file,
            "force": force,
        },
    )


def plan_container_operation(*, names: list[str], operation: str) -> ObjectPlan:
    return ObjectPlan(
        "container",
        operation,
        "/api/v2/containers/operate",
        {
            "taskID": "",
            "names": names,
            "operation": operation,
        },
    )


def plan_firewall_operation(*, operation: str, with_docker_restart: bool = False) -> ObjectPlan:
    return ObjectPlan(
        "firewall",
        operation,
        "/api/v2/hosts/firewall/operate",
        {
            "operation": operation,
            "withDockerRestart": with_docker_restart,
        },
    )
