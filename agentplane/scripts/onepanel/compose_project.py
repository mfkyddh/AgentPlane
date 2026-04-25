#!/usr/bin/env python3
"""Internal helpers for 1Panel compose project operations."""

from __future__ import annotations

import time
from typing import Any

COMPOSE_PROJECT_DIR = "/data/1panel/docker/compose"


class ComposeExecutorProtocol:
    def api_request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        raise NotImplementedError

    def shell(self, command: str) -> str:
        raise NotImplementedError


def search_compose(executor: ComposeExecutorProtocol, info: str = "") -> list[dict[str, Any]]:
    data = executor.api_request("POST", "/api/v2/containers/compose/search", {"page": 1, "pageSize": 100, "info": info})
    items = data.get("items", []) if isinstance(data, dict) else []
    return items if isinstance(items, list) else []


def find_compose(executor: ComposeExecutorProtocol, name: str) -> dict[str, Any] | None:
    for item in search_compose(executor, name):
        if item.get("name") == name:
            return item
    return None


def create_compose(
    executor: ComposeExecutorProtocol,
    *,
    name: str,
    content: str,
    env: str = "",
    force_pull: bool = False,
    test_only: bool = False,
) -> dict[str, Any]:
    payload = {
        "taskID": "",
        "name": name,
        "from": "edit",
        "file": content,
        "env": env,
        "forcePull": force_pull,
    }
    endpoint = "/api/v2/containers/compose/test" if test_only else "/api/v2/containers/compose"
    result = executor.api_request("POST", endpoint, payload)
    if not isinstance(result, dict):
        raise ValueError("compose create result must be an object")
    return result


def update_compose(
    executor: ComposeExecutorProtocol,
    *,
    name: str,
    detail_path: str,
    content: str,
    env: str = "",
    force_pull: bool = False,
) -> dict[str, Any]:
    project_path = f"{COMPOSE_PROJECT_DIR}/{name}/docker-compose.yml"
    payload = {
        "taskID": "",
        "name": name,
        "path": project_path,
        "detailPath": detail_path,
        "content": content,
        "env": env,
        "forcePull": force_pull,
    }
    result = executor.api_request("POST", "/api/v2/containers/compose/update", payload)
    if not isinstance(result, dict):
        raise ValueError("compose update result must be an object")
    return result


def operate_compose(
    executor: ComposeExecutorProtocol,
    *,
    name: str,
    operation: str,
    with_file: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    project_path = f"{COMPOSE_PROJECT_DIR}/{name}/docker-compose.yml"
    payload = {
        "name": name,
        "path": project_path,
        "operation": operation,
        "withFile": with_file,
        "force": force,
    }
    result = executor.api_request("POST", "/api/v2/containers/compose/operate", payload)
    if not isinstance(result, dict):
        raise ValueError("compose operate result must be an object")
    return result


def wait_for_compose(executor: ComposeExecutorProtocol, name: str, timeout_seconds: int = 120) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        item = find_compose(executor, name)
        if item and item.get("runningCount", 0) >= 1:
            return item
        time.sleep(2)
    raise TimeoutError(f"Timed out waiting for compose {name} to become running")
