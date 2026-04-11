from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

PROD0_MAIN_TARGET = "prod0-main"
ALLOWED_ONBOARDING_OPERATIONS = (
    "inventory_sync",
    "projection_verify",
    "host_audit",
    "host_network_audit",
    "document_onboard",
    "compose_candidate",
)
ALLOWED_OFFBOARDING_OPERATIONS = (
    "dry_run",
    "compose_down",
    "inventory_prune",
    "document_offboard",
    "projection_verify",
    "host_audit",
)
ALLOWED_PROD0_NETWORKS = ("zqf_network", "zqf-private", "1panel-openresty-prod")
DISALLOWED_SERVICE_KEY_PREFIXES = ("wsl-", "dev-", "test-", "local-")
MANDATORY_ONBOARDING_CHECKS = frozenset("""inventory_sync projection_verify host_audit""".split())


@dataclass(frozen=True)
class Prod0MainLifecyclePlan:
    action: Literal["onboard", "offboard"]
    project: str
    target: str
    service_key: str | None = None
    operations: tuple[str, ...] = ()
    networks: tuple[str, ...] = ()
    requires_dry_run: bool = False


class Prod0MainLifecyclePolicy:
    """Policy guardrail covering onboarding/offboarding planning for prod0-main."""

    @classmethod
    def validate_onboarding_plan(cls, plan: Prod0MainLifecyclePlan) -> None:
        if plan.action != "onboard":
            raise ValueError("onboarding plan must declare action='onboard'")
        cls._ensure_prod0_target(plan.target)
        cls._ensure_service_key(plan.service_key)
        cls._ensure_networks(plan.networks)
        cls._ensure_operations_subset(plan.operations, ALLOWED_ONBOARDING_OPERATIONS, "onboarding")
        cls._ensure_mandatory_checks(plan.operations)

    @classmethod
    def validate_offboarding_plan(cls, plan: Prod0MainLifecyclePlan) -> None:
        if plan.action != "offboard":
            raise ValueError("offboarding plan must declare action='offboard'")
        cls._ensure_prod0_target(plan.target)
        cls._ensure_networks(plan.networks)
        cls._ensure_operations_subset(plan.operations, ALLOWED_OFFBOARDING_OPERATIONS, "offboarding")
        cls._ensure_offboarding_dry_run(plan)

    @classmethod
    def lane2_policy_helper(cls) -> dict[str, object]:
        return {
            "target": PROD0_MAIN_TARGET,
            "onboarding_operations": ALLOWED_ONBOARDING_OPERATIONS,
            "offboarding_operations": ALLOWED_OFFBOARDING_OPERATIONS,
            "allowed_networks": ALLOWED_PROD0_NETWORKS,
            "disallowed_service_key_prefixes": DISALLOWED_SERVICE_KEY_PREFIXES,
            "mandatory_onboarding_checks": tuple(sorted(MANDATORY_ONBOARDING_CHECKS)),
            "requires_offboard_dry_run": True,
        }

    @classmethod
    def _ensure_prod0_target(cls, target: str) -> None:
        if target != PROD0_MAIN_TARGET:
            raise ValueError(f"prod0-main lifecycle policy only applies to target '{PROD0_MAIN_TARGET}', got {target!r}")

    @classmethod
    def _ensure_service_key(cls, service_key: str | None) -> None:
        if service_key is None:
            return
        lowered = service_key.lower()
        for prefix in DISALLOWED_SERVICE_KEY_PREFIXES:
            if lowered.startswith(prefix):
                raise ValueError(
                    f"prod0-main lifecycle service_key must not start with reserved prefix {prefix!r}, got {service_key!r}"
                )

    @classmethod
    def _ensure_networks(cls, networks: tuple[str, ...]) -> None:
        disallowed = [net for net in networks if net not in ALLOWED_PROD0_NETWORKS]
        if disallowed:
            raise ValueError(
                f"prod0-main lifecycle plans cannot touch unknown networks: {disallowed}, allowed: {ALLOWED_PROD0_NETWORKS}"
            )

    @classmethod
    def _ensure_operations_subset(cls, operations: tuple[str, ...], allowed: tuple[str, ...], label: str) -> None:
        if not operations:
            raise ValueError(f"{label.capitalize()} plan must list at least one operation")
        disallowed = [op for op in operations if op not in allowed]
        if disallowed:
            raise ValueError(
                f"{label.capitalize()} plan contains operations not permitted for prod0-main lifecycle: {disallowed}"
            )

    @classmethod
    def _ensure_mandatory_checks(cls, operations: tuple[str, ...]) -> None:
        if not MANDATORY_ONBOARDING_CHECKS.intersection(operations):
            raise ValueError(
                f"onboarding plan must include at least one production safety check: {sorted(MANDATORY_ONBOARDING_CHECKS)}"
            )

    @classmethod
    def _ensure_offboarding_dry_run(cls, plan: Prod0MainLifecyclePlan) -> None:
        if plan.requires_dry_run or "dry_run" in plan.operations:
            return
        raise ValueError("prod0-main offboarding plans must declare requires_dry_run=True or include the 'dry_run' operation")


def lane2_policy_helper() -> dict[str, object]:
    return Prod0MainLifecyclePolicy.lane2_policy_helper()
