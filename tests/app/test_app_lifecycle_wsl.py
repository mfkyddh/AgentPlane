from __future__ import annotations

import pytest

from agentplane.domain.app.lifecycle_wsl import (
    ALLOWED_ONBOARDING_OPERATIONS,
    ALLOWED_OFFBOARDING_OPERATIONS,
    WslLifecyclePlan,
    WslLifecyclePolicy,
    lane2_policy_helper,
)


def test_onboarding_plan_requires_wsl_target() -> None:
    plan = WslLifecyclePlan(
        action="onboard",
        project="wsl-app",
        target="prod0-main",
        operations=(ALLOWED_ONBOARDING_OPERATIONS[0],),
    )
    with pytest.raises(ValueError, match="WSL lifecycle policy only applies to the 'wsl' target"):
        WslLifecyclePolicy.validate_onboarding_plan(plan)


def test_onboarding_plan_disallows_production_networks() -> None:
    plan = WslLifecyclePlan(
        action="onboard",
        project="wsl-app",
        target="wsl",
        operations=(ALLOWED_ONBOARDING_OPERATIONS[0],),
        networks=("zqf_network",),
    )
    with pytest.raises(ValueError, match="production networks"):
        WslLifecyclePolicy.validate_onboarding_plan(plan)


def test_onboarding_plan_requires_local_service_key_prefix() -> None:
    plan = WslLifecyclePlan(
        action="onboard",
        project="wsl-app",
        target="wsl",
        service_key="prod-service",
        operations=(ALLOWED_ONBOARDING_OPERATIONS[0],),
    )
    with pytest.raises(ValueError, match="service_key"):
        WslLifecyclePolicy.validate_onboarding_plan(plan)


def test_offboarding_plan_requires_explicit_dry_run() -> None:
    plan = WslLifecyclePlan(
        action="offboard",
        project="wsl-app",
        target="wsl",
        operations=(
            ALLOWED_OFFBOARDING_OPERATIONS[1],
            ALLOWED_OFFBOARDING_OPERATIONS[2],
        ),
    )
    with pytest.raises(ValueError, match="dry_run"):
        WslLifecyclePolicy.validate_offboarding_plan(plan)


def test_lane2_policy_helper_describes_detailed_constraints() -> None:
    summary = lane2_policy_helper()
    assert summary["target"] == "wsl"
    assert "dry_run" in summary["offboarding_operations"]
    assert "zqf_network" in summary["forbidden_networks"]

