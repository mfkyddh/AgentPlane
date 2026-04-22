from __future__ import annotations

from typing import Any

from agentplane.scripts.onepanel.env_targets import get_target, supported_targets
from agentplane.scripts.onepanel.executor import TargetExecutor
from agentplane.scripts.onepanel.object_api import (
    get_compose_project,
    get_container,
    get_installed_app,
    get_panel_summary,
    get_task_count,
    get_website,
    load_cronjob,
    load_firewall_base,
    plan_compose_project_operation,
    plan_container_operation,
    plan_cronjob_operation,
    plan_firewall_operation,
    plan_installed_app_operation,
    plan_panel_setting_update,
    plan_website_create,
    search_containers,
    search_cronjobs,
    search_firewall_rules,
    search_installed_apps,
    search_tasks,
    search_websites,
)


def supported_onepanel_targets() -> tuple[str, ...]:
    return tuple(supported_targets())


def onepanel_target_executor(target: str, env_file: str | None = None) -> TargetExecutor:
    return TargetExecutor(get_target(target, env_file))


def onepanel_search_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    items = payload.get("items")
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]
