from __future__ import annotations

import pytest

from agentplane.domain.app.lifecycle_prod0_main import (
    ALLOWED_OFFBOARDING_OPERATIONS,
    ALLOWED_ONBOARDING_OPERATIONS,
    Prod0MainLifecyclePlan,
    Prod0MainLifecyclePolicy,
    lane2_policy_helper,
)


def test_onboarding_plan_enforces_prod0_target() -> None:
    plan = Prod0MainLifecyclePlan(action="onboard", project="app", target="wsl", operations=(ALLOWED_ONBOARDING_OPERATIONS[0],))
    with pytest.raises(ValueError, match="prod0-main lifecycle policy only applies to target"):
        Prod0MainLifecyclePolicy.validate_onboarding_plan(plan)


def test_onboarding_plan_requires_safety_check() -> None:
    plan = Prod0MainLifecyclePlan(
        action="onboard",
        project="app",
        target="prod0-main",
        operations=("compose_candidate",),
    )
    with pytest.raises(ValueError, match="production safety check"):
        Prod0MainLifecyclePolicy.validate_onboarding_plan(plan)


def test_onboarding_plan_allows_required_operations() -> None:
    plan = Prod0MainLifecyclePlan(
        action="onboard",
        project="app",
        target="prod0-main",
        operations=("inventory_sync", "projection_verify"),
        networks=("zqf_network",),
        service_key="prod0-app",
    )
    Prod0MainLifecyclePolicy.validate_onboarding_plan(plan)


def test_offboarding_plan_must_dry_run() -> None:
    plan = Prod0MainLifecyclePlan(
        action="offboard",
        project="app",
        target="prod0-main",
        operations=(ALLOWED_OFFBOARDING_OPERATIONS[1],),
    )
    with pytest.raises(ValueError, match="offboarding plans must declare requires_dry_run"):
        Prod0MainLifecyclePolicy.validate_offboarding_plan(plan)


def test_offboarding_plan_accepts_dry_run_flag() -> None:
    plan = Prod0MainLifecyclePlan(
        action="offboard",
        project="app",
        target="prod0-main",
        operations=("dry_run",),
        requires_dry_run=True,
    )
    Prod0MainLifecyclePolicy.validate_offboarding_plan(plan)


def test_policy_helper_lists_constraints() -> None:
    summary = lane2_policy_helper()
    assert summary["target"] == "prod0-main"
    assert "zqf_network" in summary["allowed_networks"]
    assert "dry_run" in summary["offboarding_operations"]
