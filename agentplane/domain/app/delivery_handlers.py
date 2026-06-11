"""Delivery handlers — facade that re-exports from sub-modules for backward compatibility."""

from __future__ import annotations

# Candidate runtime
from agentplane.domain.app.delivery_handlers_candidate import (
    _candidate_host_binding,
    _candidate_precheck_steps,
    _candidate_runtime_material,
)

# Deploy
from agentplane.domain.app.delivery_handlers_deploy import deploy_for_app

# Simple handlers
from agentplane.domain.app.delivery_handlers_handlers import (
    build_artifact_for_app,
    doc_sync_for_app,
    inventory_refresh_for_app,
    offboard_for_app,
    onboard_for_app,
    package_runtime_for_app,
    render_runtime_for_app,
    ship_image_for_app,
    validate_contract_for_app,
    validate_contract_standalone_for_app,
)

# Planning
from agentplane.domain.app.delivery_handlers_planning import (
    _execute_origin_verify,
    _plan_delivery_rollback_steps,
    _plan_delivery_verify_steps,
    _plan_production_rollback,
    _plan_production_verify,
    _plan_remote_deploy_steps,
    _plan_wsl_deploy_steps,
)

# Shared infrastructure
from agentplane.domain.app.delivery_handlers_shared import (
    _check_delivery_preconditions,
    _display_commands,
    _execute_steps,
    _load_validated_contract,
    _render_execution_steps,
    _resolve_contract_file,
    _transition_step_to_execution,
)

# Rollback state
from agentplane.domain.app.delivery_handlers_state import (
    _OBSERVATION_WINDOW_NOTE,
    _delayed_cleanup_state,
    _rollback_state_payload,
    _run_delivery_post_actions,
)

# Verify & rollback
from agentplane.domain.app.delivery_handlers_verify_rollback import (
    rollback_for_app,
    verify_delivery_for_app,
)

__all__ = [
    "_OBSERVATION_WINDOW_NOTE",
    "_candidate_host_binding",
    "_candidate_precheck_steps",
    "_candidate_runtime_material",
    "_check_delivery_preconditions",
    "_delayed_cleanup_state",
    "_display_commands",
    "_execute_origin_verify",
    "_execute_steps",
    "_load_validated_contract",
    "_plan_delivery_rollback_steps",
    "_plan_delivery_verify_steps",
    "_plan_production_rollback",
    "_plan_production_verify",
    "_plan_remote_deploy_steps",
    "_plan_wsl_deploy_steps",
    "_render_execution_steps",
    "_resolve_contract_file",
    "_rollback_state_payload",
    "_run_delivery_post_actions",
    "_transition_step_to_execution",
    "build_artifact_for_app",
    "deploy_for_app",
    "doc_sync_for_app",
    "inventory_refresh_for_app",
    "offboard_for_app",
    "onboard_for_app",
    "package_runtime_for_app",
    "render_runtime_for_app",
    "rollback_for_app",
    "ship_image_for_app",
    "validate_contract_for_app",
    "validate_contract_standalone_for_app",
    "verify_delivery_for_app",
]
