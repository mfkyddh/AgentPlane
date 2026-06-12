#!/usr/bin/env python3
"""Read-only 1Panel API query helpers."""

from __future__ import annotations

from typing import Any


class FakeLikeExecutorProtocol:
    def api_request(self, method: str, path: str, body: dict[str, object] | None = None) -> object:
        raise NotImplementedError


def get_panel_summary(executor: FakeLikeExecutorProtocol) -> dict[str, Any]:
    result = executor.api_request("POST", "/api/v2/core/settings/search", {})
    if not isinstance(result, dict):
        raise ValueError("panel summary must be an object")
    return result


def search_ingresses(
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


def get_ingress(executor: FakeLikeExecutorProtocol, *, website_id: int) -> dict[str, Any]:
    website = executor.api_request("GET", f"/api/v2/websites/{website_id}")
    https = executor.api_request("GET", f"/api/v2/websites/{website_id}/https")
    if not isinstance(website, dict) or not isinstance(https, dict):
        raise ValueError("website detail must be objects")
    return {"ingress": website, "https": https}


def get_website_ssl(executor: FakeLikeExecutorProtocol, *, ssl_id: int) -> dict[str, Any]:
    result = executor.api_request("GET", f"/api/v2/websites/ssl/{ssl_id}")
    if not isinstance(result, dict):
        raise ValueError("website SSL detail must be an object")
    return result


def get_openresty_status(executor: FakeLikeExecutorProtocol) -> dict[str, Any]:
    result = executor.api_request("GET", "/api/v2/apps/installed/info/3")
    if not isinstance(result, dict):
        raise ValueError("openresty status must be an object")
    return result


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
    payload = search_ingresses(executor, name=query)
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


def search_cronjob_records(
    executor: FakeLikeExecutorProtocol,
    *,
    cronjob_id: int,
    page: int = 1,
    page_size: int = 5,
) -> dict[str, Any]:
    result = executor.api_request(
        "POST",
        "/api/v2/cronjobs/search/records",
        {
            "page": page,
            "pageSize": page_size,
            "cronjobID": cronjob_id,
        },
    )
    if not isinstance(result, dict):
        raise ValueError("cronjob records search must be an object")
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


def search_databases(
    executor: FakeLikeExecutorProtocol,
    *,
    database: str = " ",
    db_type: str = "mysql",
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    result = executor.api_request(
        "POST",
        "/api/v2/databases/search",
        {
            "page": page,
            "pageSize": page_size,
            "database": database,
            "orderBy": "name",
            "order": "ascending",
            "type": db_type,
        },
    )
    if not isinstance(result, dict):
        raise ValueError("database search must be an object")
    return result


def get_dashboard_current(
    executor: FakeLikeExecutorProtocol,
    *,
    io_option: str = "all",
    net_option: str = "all",
) -> dict[str, Any]:
    """Fetch current dashboard metrics (CPU, memory, load, disk, network)."""
    result = executor.api_request("GET", f"/api/v2/dashboard/current/{io_option}/{net_option}")
    if not isinstance(result, dict):
        raise ValueError("dashboard current must be an object")
    return result


def get_dashboard_base(
    executor: FakeLikeExecutorProtocol,
    *,
    io_option: str = "all",
    net_option: str = "all",
) -> dict[str, Any]:
    """Fetch dashboard base info (hostname, OS, CPU model, resource counts)."""
    result = executor.api_request("GET", f"/api/v2/dashboard/base/{io_option}/{net_option}")
    if not isinstance(result, dict):
        raise ValueError("dashboard base must be an object")
    return result


def get_dashboard_top_cpu(executor: FakeLikeExecutorProtocol) -> list[dict[str, Any]]:
    """Fetch top CPU-consuming processes."""
    result = executor.api_request("GET", "/api/v2/dashboard/current/top/cpu")
    if not isinstance(result, list):
        raise ValueError("dashboard top cpu must be a list")
    return result


def get_dashboard_top_mem(executor: FakeLikeExecutorProtocol) -> list[dict[str, Any]]:
    """Fetch top memory-consuming processes."""
    result = executor.api_request("GET", "/api/v2/dashboard/current/top/mem")
    if not isinstance(result, list):
        raise ValueError("dashboard top mem must be a list")
    return result


def search_alerts(
    executor: FakeLikeExecutorProtocol,
    *,
    alert_type: str = "",
    status: str = "",
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """Search alert rules with optional filters."""
    body: dict[str, Any] = {
        "page": page,
        "pageSize": page_size,
        "orderBy": "created_at",
        "order": "descending",
    }
    if alert_type:
        body["type"] = alert_type
    if status:
        body["status"] = status
    result = executor.api_request("POST", "/api/v2/alerts/search", body)
    if not isinstance(result, dict):
        raise ValueError("alert search must be an object")
    return result


def search_alert_logs(
    executor: FakeLikeExecutorProtocol,
    *,
    status: str = "",
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """Search alert logs with optional status filter."""
    body: dict[str, Any] = {
        "page": page,
        "pageSize": page_size,
    }
    if status:
        body["status"] = status
    result = executor.api_request("POST", "/api/v2/alerts/logs/search", body)
    if not isinstance(result, dict):
        raise ValueError("alert log search must be an object")
    return result


def get_monitor_setting(executor: FakeLikeExecutorProtocol) -> dict[str, Any]:
    """Fetch monitor collection settings (status, interval, store days)."""
    result = executor.api_request("GET", "/api/v2/hosts/monitor/setting")
    if not isinstance(result, dict):
        raise ValueError("monitor setting must be an object")
    return result
