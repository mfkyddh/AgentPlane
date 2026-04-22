from __future__ import annotations

from pathlib import Path
from typing import Any

from agentplane.scripts.onepanel.fixture_manager import (
    apply_fixture,
    cleanup_fixture,
    plan_fixture,
    resolve_fixture_spec,
    resolve_suite_targets,
)
from agentplane.scripts.onepanel.verification import run_verification_suite


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
