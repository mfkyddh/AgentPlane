from __future__ import annotations

from pathlib import Path
from typing import Any

from agentplane.scripts.onepanel import fixture_manager
from agentplane.scripts.onepanel.verification import run_verification_suite


def resolve_fixture_spec(*args: Any, **kwargs: Any) -> Any:
    return fixture_manager.resolve_fixture_spec(*args, **kwargs)


def plan_fixture(*args: Any, **kwargs: Any) -> Any:
    return fixture_manager.plan_fixture(*args, **kwargs)


def apply_fixture(*args: Any, **kwargs: Any) -> Any:
    return fixture_manager.apply_fixture(*args, **kwargs)


def cleanup_fixture(*args: Any, **kwargs: Any) -> Any:
    return fixture_manager.cleanup_fixture(*args, **kwargs)


def run_onepanel_verification_suite(
    executor: object,
    *,
    profile: str,
    env: str,
    repo_root: Path,
    write_report: bool,
    website_alias: str,
    container_name: str,
    project_name: str,
    cronjob_id: int | None,
    cronjob_name: str,
    app_name: str,
    firewall_tab: str,
) -> dict[str, Any]:
    return run_verification_suite(
        executor,
        profile=profile,
        env=env,
        repo_root=repo_root,
        write_report=write_report,
        website_alias=website_alias,
        container_name=container_name,
        project_name=project_name,
        cronjob_id=cronjob_id,
        cronjob_name=cronjob_name,
        app_name=app_name,
        firewall_tab=firewall_tab,
    )
