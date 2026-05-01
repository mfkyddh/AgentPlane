from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

WSL_ONLY_TARGET = "wsl"
FORBIDDEN_PRODUCTION_TARGETS = {"prod0-main"}
FORBIDDEN_NETWORKS = {"zqf_network", "zqf-net", "prod-network", "zqf-private"}
ALLOWED_ONBOARDING_OPERATIONS = (
    "inventory_sync",
    "compose_up",
    "register_local_service",
    "document_onboard",
)
ALLOWED_OFFBOARDING_OPERATIONS = (
    "dry_run",
    "compose_down",
    "inventory_prune",
    "document_offboard",
)
ALLOWED_SERVICE_KEY_PREFIXES = ("wsl-", "local-", "dev-", "test-")


@dataclass(frozen=True)
class WslLifecyclePlan:
    """
    Structured input that Lane 7 and Lane 2 can validate before onboarding or offboarding
    a WSL-only project.
    """

    action: Literal["onboard", "offboard"]
    project: str
    target: str
    service_key: str | None = None
    operations: tuple[str, ...] = ()
    networks: tuple[str, ...] = ()
    requires_dry_run: bool = False


class WslLifecyclePolicy:
    """
    Policy guardrail covering onboarding and offboarding of WSL-only projects.
    Lane 2 can call these helpers to enforce the constraints before touching the wider
    app delivery flow.
    """

    @classmethod
    def validate_onboarding_plan(cls, plan: WslLifecyclePlan) -> None:
        if plan.action != "onboard":
            raise ValueError("onboarding plan must declare action='onboard'")
        cls._ensure_wsl_target(plan.target)
        cls._ensure_disallowed_networks(plan.networks)
        cls._ensure_service_key_prefix(plan.service_key)
        cls._ensure_operations_subset(plan.operations, ALLOWED_ONBOARDING_OPERATIONS, "onboarding")

    @classmethod
    def validate_offboarding_plan(cls, plan: WslLifecyclePlan) -> None:
        if plan.action != "offboard":
            raise ValueError("offboarding plan must declare action='offboard'")
        cls._ensure_wsl_target(plan.target)
        cls._ensure_disallowed_networks(plan.networks)
        cls._ensure_service_key_prefix(plan.service_key)
        cls._ensure_operations_subset(plan.operations, ALLOWED_OFFBOARDING_OPERATIONS, "offboarding")
        cls._ensure_offboarding_dry_run(plan)

    @classmethod
    def lane2_policy_helper(cls) -> dict[str, object]:
        """
        Provides Lane 2 with the hard constraints that must be described or enforced during
        WSL-only lifecycle planning.
        """
        return {
            "target": WSL_ONLY_TARGET,
            "onboarding_operations": ALLOWED_ONBOARDING_OPERATIONS,
            "offboarding_operations": ALLOWED_OFFBOARDING_OPERATIONS,
            "forbidden_networks": tuple(sorted(FORBIDDEN_NETWORKS)),
            "service_key_prefixes": ALLOWED_SERVICE_KEY_PREFIXES,
            "production_targets": tuple(sorted(FORBIDDEN_PRODUCTION_TARGETS)),
            "requires_offboard_dry_run": True,
        }

    @classmethod
    def _ensure_wsl_target(cls, target: str) -> None:
        if target != WSL_ONLY_TARGET:
            raise ValueError(f"WSL lifecycle policy only applies to the '{WSL_ONLY_TARGET}' target, got {target!r}")
        if target in FORBIDDEN_PRODUCTION_TARGETS:
            raise ValueError(f"target {target!r} is reserved for production hosts")

    @classmethod
    def _ensure_service_key_prefix(cls, service_key: str | None) -> None:
        if service_key is None:
            return
        lowered = service_key.lower()
        if lowered.startswith("prod") or not any(lowered.startswith(prefix) for prefix in ALLOWED_SERVICE_KEY_PREFIXES):
            raise ValueError(
                "WSL lifecycle service_key must start with one of "
                f"{ALLOWED_SERVICE_KEY_PREFIXES} and must not look like a production key"
            )

    @classmethod
    def _ensure_disallowed_networks(cls, networks: tuple[str, ...]) -> None:
        bad = [net for net in networks if net in FORBIDDEN_NETWORKS]
        if bad:
            raise ValueError(f"WSL lifecycle plans cannot reference production networks: {bad}")

    @classmethod
    def _ensure_operations_subset(
        cls,
        operations: tuple[str, ...],
        allowed: tuple[str, ...],
        label: str,
    ) -> None:
        if not operations:
            raise ValueError(f"{label.capitalize()} plan must list at least one operation")
        disallowed = [op for op in operations if op not in allowed]
        if disallowed:
            raise ValueError(
                f"{label.capitalize()} plan contains operations not permitted for WSL lifecycle: {disallowed}"
            )

    @classmethod
    def _ensure_offboarding_dry_run(cls, plan: WslLifecyclePlan) -> None:
        if not plan.requires_dry_run and "dry_run" not in plan.operations:
            raise ValueError(
                "WSL offboarding plans must declare `requires_dry_run=True` or include the 'dry_run' operation"
            )


def lane2_policy_helper() -> dict[str, object]:
    """
    Simple facade so Lane 2 callers can import a plain function without referencing the policy class.
    """
    return WslLifecyclePolicy.lane2_policy_helper()
