#!/usr/bin/env python3
"""Profile-backed WSL fixture orchestration for onepanel verification."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .object_api import (
    find_cronjob_id,
    plan_cronjob_operation,
    plan_website_create,
    search_cronjobs,
    search_installed_apps,
    search_websites,
)
from .compose_project import create_compose, operate_compose, search_compose, update_compose


@dataclass(frozen=True)
class FixtureSpec:
    profile: str
    env: str
    website_alias: str
    website_domain: str
    website_proxy: str
    website_group_id: int
    website_remark: str
    website_ipv6: bool
    project_name: str
    project_container_name: str
    project_host_port: int
    project_container_port: int
    project_image: str
    cronjob_name: str
    cronjob_spec: str
    cronjob_script: str
    firewall_tab: str


def resolve_fixture_spec(
    profile: str,
    *,
    env: str,
    website_alias: str = "",
    container_name: str = "",
    project_name: str = "",
    cronjob_name: str = "",
    firewall_tab: str = "",
) -> FixtureSpec:
    if profile != "wsl-fixture":
        raise ValueError(f"unsupported fixture profile: {profile}")
    if env != "wsl":
        raise ValueError("fixture profile wsl-fixture only supports env=wsl")
    return FixtureSpec(
        profile=profile,
        env=env,
        website_alias=website_alias or "oplinux-fixture",
        website_domain="oplinux-fixture.local",
        website_proxy="http://127.0.0.1:18880",
        website_group_id=1,
        website_remark="OP_Linux WSL fixture",
        website_ipv6=False,
        project_name=project_name or "oplinux-fixture",
        project_container_name=container_name or "oplinux-fixture-web",
        project_host_port=18880,
        project_container_port=80,
        project_image="nginx:alpine",
        cronjob_name=cronjob_name or "oplinux-fixture",
        cronjob_spec="0 */6 * * *",
        cronjob_script="printf fixture_ok\\n",
        firewall_tab=firewall_tab or "port",
    )


def resolve_suite_targets(
    *,
    profile: str,
    env: str,
    website_alias: str = "",
    container_name: str = "",
    project_name: str = "",
    cronjob_id: int | None = None,
    cronjob_name: str = "",
    app_name: str = "",
    firewall_tab: str = "port",
) -> dict[str, Any]:
    if profile != "wsl-fixture":
        return {
            "website_alias": website_alias,
            "container_name": container_name,
            "project_name": project_name,
            "cronjob_id": cronjob_id,
            "cronjob_name": cronjob_name,
            "app_name": app_name,
            "firewall_tab": firewall_tab,
        }
    spec = resolve_fixture_spec(
        profile,
        env=env,
        website_alias=website_alias,
        container_name=container_name,
        project_name=project_name,
        cronjob_name=cronjob_name,
        firewall_tab=firewall_tab,
    )
    return {
        "website_alias": website_alias or spec.website_alias,
        "container_name": container_name or spec.project_container_name,
        "project_name": project_name or spec.project_name,
        "cronjob_id": cronjob_id,
        "cronjob_name": cronjob_name or spec.cronjob_name,
        "app_name": app_name,
        "firewall_tab": firewall_tab or spec.firewall_tab,
    }


def _fixture_compose(spec: FixtureSpec) -> str:
    return (
        "services:\n"
        "  web:\n"
        f"    image: {spec.project_image}\n"
        f"    container_name: {spec.project_container_name}\n"
        "    restart: unless-stopped\n"
        "    ports:\n"
        f"      - \"127.0.0.1:{spec.project_host_port}:{spec.project_container_port}\"\n"
    )


def _find_existing_website(executor: Any, spec: FixtureSpec) -> dict[str, Any] | None:
    payload = search_websites(executor, name=spec.website_alias)
    items = payload.get("items")
    if not isinstance(items, list):
        return None
    for item in items:
        if isinstance(item, dict) and item.get("alias") == spec.website_alias:
            return item
    return None


def _has_openresty_runtime(executor: Any) -> bool:
    payload = search_installed_apps(executor, name="openresty")
    items = payload.get("items")
    return isinstance(items, list) and any(isinstance(item, dict) and item.get("appKey") == "openresty" for item in items)


def _find_existing_project(executor: Any, spec: FixtureSpec) -> dict[str, Any] | None:
    payload = search_compose(executor, spec.project_name)
    for item in payload:
        if isinstance(item, dict) and item.get("name") == spec.project_name:
            return item
    return None


def _find_existing_cronjob(executor: Any, spec: FixtureSpec) -> dict[str, Any] | None:
    payload = search_cronjobs(executor, info=spec.cronjob_name)
    items = payload.get("items")
    if not isinstance(items, list):
        return None
    for item in items:
        if isinstance(item, dict) and item.get("name") == spec.cronjob_name:
            return item
    return None


def _cronjob_group_id(executor: Any, existing: dict[str, Any] | None) -> int:
    if existing is not None:
        return int(existing.get("groupID", 0))
    payload = search_cronjobs(executor, info="")
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        return 0
    first = items[0]
    if not isinstance(first, dict):
        return 0
    return int(first.get("groupID", 0))


def _cronjob_create_payload(spec: FixtureSpec, *, group_id: int, existing: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": spec.cronjob_name,
        "type": "shell",
        "groupID": group_id,
        "specCustom": True,
        "spec": spec.cronjob_spec,
        "executor": "bash",
        "scriptMode": "input",
        "script": spec.cronjob_script,
        "command": "",
        "containerName": "",
        "user": "root",
        "scriptID": 0,
        "appID": "",
        "website": "",
        "exclusionRules": "",
        "dbType": "",
        "dbName": "",
        "url": "",
        "isDir": False,
        "sourceDir": "",
        "snapshotRule": {"withImage": False, "ignoreAppIDs": []},
        "sourceAccountIDs": "",
        "downloadAccountID": 0,
        "retainCopies": int(existing.get("retainCopies", 7)) if existing else 7,
        "retryTimes": int(existing.get("retryTimes", 0)) if existing else 0,
        "timeout": int(existing.get("timeout", 60)) if existing else 60,
        "ignoreErr": bool(existing.get("ignoreErr", False)) if existing else False,
        "secret": str(existing.get("secret", "")) if existing else "",
        "args": str(existing.get("args", "")) if existing else "",
        "alertCount": int(existing.get("alertCount", 0)) if existing else 0,
        "alertTitle": "",
        "alertMethod": "",
        "scopes": [],
    }
    if existing and existing.get("id") is not None:
        payload["id"] = int(existing["id"])
    return payload


def plan_fixture(executor: Any, spec: FixtureSpec) -> dict[str, Any]:
    website_runtime_ready = _has_openresty_runtime(executor)
    website = _find_existing_website(executor, spec)
    project = _find_existing_project(executor, spec)
    cronjob = _find_existing_cronjob(executor, spec)
    items = [
        {
            "object": "website",
            "action": "noop" if website else ("create" if website_runtime_ready else "blocked-missing-openresty"),
            "existing": website,
            "desired": {
                "alias": spec.website_alias,
                "domain": spec.website_domain,
                "proxy": spec.website_proxy,
            },
            "blocked_reason": "" if website_runtime_ready else "WSL onepanel does not have the openresty installed-app runtime yet.",
        },
        {
            "object": "project",
            "action": "update" if project else "create",
            "existing": project,
            "desired": {
                "name": spec.project_name,
                "container_name": spec.project_container_name,
                "host_port": spec.project_host_port,
            },
        },
        {
            "object": "cronjob",
            "action": "create" if cronjob is None else ("enable" if cronjob.get("status") != "Enable" else "noop"),
            "existing": cronjob,
            "desired": {
                "name": spec.cronjob_name,
                "spec": spec.cronjob_spec,
            },
        },
    ]
    return {"profile": spec.profile, "env": spec.env, "spec": asdict(spec), "items": items}


def apply_fixture(executor: Any, spec: FixtureSpec, *, execute: bool) -> dict[str, Any]:
    payload = plan_fixture(executor, spec)
    payload["execute"] = execute
    if not execute:
        payload["ok"] = True
        return payload

    actions: list[dict[str, Any]] = []
    ok = True
    website = _find_existing_website(executor, spec)
    website_item = next((item for item in payload["items"] if item["object"] == "website"), None)
    if website is None and website_item and website_item["action"] == "create":
        plan = plan_website_create(
            alias=spec.website_alias,
            domain=spec.website_domain,
            proxy=spec.website_proxy,
            website_group_id=spec.website_group_id,
            remark=spec.website_remark,
            ipv6=spec.website_ipv6,
        )
        result = executor.api_request("POST", plan.path, plan.body)
        actions.append({"object": "website", "action": "create", "result": result})
    elif website is None and website_item and website_item["action"] == "blocked-missing-openresty":
        ok = False
        actions.append({"object": "website", "action": "blocked-missing-openresty", "reason": website_item["blocked_reason"]})
    else:
        actions.append({"object": "website", "action": "noop", "result": {"id": website.get("id")}})

    project = _find_existing_project(executor, spec)
    compose_content = _fixture_compose(spec)
    if project is None:
        result = create_compose(executor, name=spec.project_name, content=compose_content)
        operate = operate_compose(executor, name=spec.project_name, operation="up")
        actions.append({"object": "project", "action": "create", "result": result, "operate": operate})
    else:
        detail_path = str(project.get("configFile") or f"/data/1panel/docker/compose/{spec.project_name}/docker-compose.yml")
        result = update_compose(executor, name=spec.project_name, detail_path=detail_path, content=compose_content)
        operate = operate_compose(executor, name=spec.project_name, operation="up")
        actions.append({"object": "project", "action": "update", "result": result, "operate": operate})

    cronjob = _find_existing_cronjob(executor, spec)
    if cronjob is None:
        group_id = _cronjob_group_id(executor, cronjob)
        create_plan = plan_cronjob_operation(mode="create", body=_cronjob_create_payload(spec, group_id=group_id))
        result = executor.api_request("POST", create_plan.path, create_plan.body)
        actions.append({"object": "cronjob", "action": "create", "result": result})
    elif cronjob.get("status") != "Enable":
        cronjob_id = int(cronjob.get("id") or find_cronjob_id(executor, name=spec.cronjob_name))
        result = executor.api_request("POST", "/api/v2/cronjobs/status", {"id": cronjob_id, "status": "Enable"})
        actions.append({"object": "cronjob", "action": "enable", "result": result})
    else:
        actions.append({"object": "cronjob", "action": "noop", "result": {"id": cronjob.get("id")}})

    payload["ok"] = ok
    payload["actions"] = actions
    return payload


def cleanup_fixture(executor: Any, spec: FixtureSpec, *, execute: bool) -> dict[str, Any]:
    payload = {"profile": spec.profile, "env": spec.env, "spec": asdict(spec), "execute": execute, "items": []}
    project = _find_existing_project(executor, spec)
    cronjob = _find_existing_cronjob(executor, spec)
    if not execute:
        payload["items"] = [
            {"object": "website", "action": "keep"},
            {"object": "project", "action": "down-project" if project else "noop"},
            {"object": "cronjob", "action": "disable" if cronjob and cronjob.get("status") != "Disable" else "noop"},
        ]
        payload["ok"] = True
        return payload

    actions: list[dict[str, Any]] = [{"object": "website", "action": "keep"}]
    if project is not None:
        result = operate_compose(executor, name=spec.project_name, operation="down", with_file=True)
        actions.append({"object": "project", "action": "down-project", "result": result})
    else:
        actions.append({"object": "project", "action": "noop"})

    if cronjob is not None and cronjob.get("status") != "Disable":
        cronjob_id = int(cronjob.get("id") or find_cronjob_id(executor, name=spec.cronjob_name))
        result = executor.api_request("POST", "/api/v2/cronjobs/status", {"id": cronjob_id, "status": "Disable"})
        actions.append({"object": "cronjob", "action": "disable", "result": result})
    else:
        actions.append({"object": "cronjob", "action": "noop"})
    payload["ok"] = True
    payload["items"] = actions
    return payload
