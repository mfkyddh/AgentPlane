from __future__ import annotations

from typing import Any

from agentplane.scripts.onepanel import object_api
from agentplane.scripts.onepanel.env_targets import get_target, supported_targets
from agentplane.scripts.onepanel.executor import TargetExecutor


def supported_onepanel_targets() -> tuple[str, ...]:
    return tuple(supported_targets())


def onepanel_target_executor(target: str, env_file: str | None = None) -> TargetExecutor:
    return TargetExecutor(get_target(target, env_file))


def onepanel_search_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    items = payload.get("items")
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def get_ingress(*args: Any, **kwargs: Any) -> Any:
    return object_api.get_ingress(*args, **kwargs)


def get_website_ssl(*args: Any, **kwargs: Any) -> Any:
    return object_api.get_website_ssl(*args, **kwargs)


def get_openresty_status(*args: Any, **kwargs: Any) -> Any:
    return object_api.get_openresty_status(*args, **kwargs)


def get_panel_summary(*args: Any, **kwargs: Any) -> Any:
    return object_api.get_panel_summary(*args, **kwargs)


def get_task_count(*args: Any, **kwargs: Any) -> Any:
    return object_api.get_task_count(*args, **kwargs)


def load_cronjob(*args: Any, **kwargs: Any) -> Any:
    return object_api.load_cronjob(*args, **kwargs)


def load_firewall_base(*args: Any, **kwargs: Any) -> Any:
    return object_api.load_firewall_base(*args, **kwargs)


def plan_compose_project_operation(*args: Any, **kwargs: Any) -> Any:
    return object_api.plan_compose_project_operation(*args, **kwargs)


def plan_cronjob_operation(*args: Any, **kwargs: Any) -> Any:
    return object_api.plan_cronjob_operation(*args, **kwargs)


def plan_firewall_operation(*args: Any, **kwargs: Any) -> Any:
    return object_api.plan_firewall_operation(*args, **kwargs)


def plan_installed_app_operation(*args: Any, **kwargs: Any) -> Any:
    return object_api.plan_installed_app_operation(*args, **kwargs)


def plan_panel_setting_update(*args: Any, **kwargs: Any) -> Any:
    return object_api.plan_panel_setting_update(*args, **kwargs)


def plan_website_create(*args: Any, **kwargs: Any) -> Any:
    return object_api.plan_website_create(*args, **kwargs)


def search_cronjobs(*args: Any, **kwargs: Any) -> Any:
    return object_api.search_cronjobs(*args, **kwargs)


def search_firewall_rules(*args: Any, **kwargs: Any) -> Any:
    return object_api.search_firewall_rules(*args, **kwargs)


def search_ingresses(*args: Any, **kwargs: Any) -> Any:
    return object_api.search_ingresses(*args, **kwargs)


def search_installed_apps(*args: Any, **kwargs: Any) -> Any:
    return object_api.search_installed_apps(*args, **kwargs)


def search_tasks(*args: Any, **kwargs: Any) -> Any:
    return object_api.search_tasks(*args, **kwargs)


def search_cronjob_records(*args: Any, **kwargs: Any) -> Any:
    return object_api.search_cronjob_records(*args, **kwargs)
