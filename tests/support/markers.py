from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest


@dataclass(frozen=True)
class MarkerRule:
    markers: tuple[str, ...]
    filenames: frozenset[str] = frozenset()
    test_names: frozenset[str] = frozenset()

    def matches(self, item: pytest.Item) -> bool:
        filename = Path(str(item.fspath)).name
        return filename in self.filenames or item.name in self.test_names


MARKER_RULES: tuple[MarkerRule, ...] = (
    # Golden tests — one per core module, proves basic functionality
    MarkerRule(
        markers=("golden",),
        test_names=frozenset(
            {
                # app: lifecycle planning
                "test_onboarding_plan_allows_required_operations",
                # infra: inventory CLI wrapper
                "test_infra_inventory_wraps_inventory_payload",
                # ingress: website search
                "test_ingress_search_lists_declared_public_ingresses",
                # inventory: snapshot generation
                "test_inventory_command_outputs_wsl_snapshot",
                # project: naming contract
                "test_naming_registry_declares_phase1_hard_contract",
                # projection: runtime env plan
                "test_runtime_env_plan_returns_target_env_file_without_writing",
                # runtime: batch execution
                "test_backend_runner_execute_batch_runs_serially",
                # service: managed service search
                "test_service_search_lists_formal_managed_services",
                # contracts: provider protocol compatibility
                "test_stub_is_protocol_compatible",
            }
        ),
    ),
    MarkerRule(
        markers=("live_gate",),
        filenames=frozenset({"test_infra_live_gate.py"}),
    ),
    MarkerRule(
        markers=("external_app",),
        filenames=frozenset({"test_sub2api_compose_layout.py"}),
    ),
    MarkerRule(
        markers=("integration_wsl",),
        filenames=frozenset({"test_wsl_audit.py"}),
        test_names=frozenset(
            {
                "test_build_artifact_executes_script_build_command_with_image_tag",
                "test_build_artifact_auto_version_executes_with_recommended_image_tag",
                "test_build_artifact_auto_version_exposes_recommended_version_env_vars",
                "test_build_artifact_auto_version_uses_git_tag_when_version_file_missing",
                "test_build_artifact_prefers_explicit_app_repo_root_over_catalog_repo_root",
                "test_package_runtime_executes_packaging_command_with_explicit_artifact_output_and_image_ref",
            }
        ),
    ),
    MarkerRule(
        markers=("docker_required", "ssh_required"),
        test_names=frozenset(
            {
                "test_deploy_app_execute_runs_local_compose_for_wsl_target",
                "test_deploy_app_execute_uses_canonical_service_env_for_wsl_worktree",
                "test_verify_app_execute_runs_local_healthcheck_for_wsl_target",
                "test_deploy_execute_runs_remote_sync_and_cutover_commands",
                "test_deploy_execute_runs_post_actions_in_projection_inventory_doc_sync_order",
                "test_verify_execute_returns_origin_and_public_results",
                "test_verify_execute_propagates_public_failure",
                "test_verify_app_execute_waits_for_container_health_before_origin_healthcheck",
                "test_network_audit_reports_missing_gateway_and_route",
                "test_network_ensure_repairs_missing_gateway_and_route",
                "test_deploy_execute_runs_onepanel_compose_stop_instead_of_systemd",
                "test_rollback_execute_runs_onepanel_compose_up_instead_of_systemd",
                "test_rollback_execute_runs_compose_down_and_systemd_start",
                "test_host_network_ensure_uses_formal_host_shape_without_compat_source",
                "test_service_apply_reconcile_uses_remote_compose_path_and_verifies",
                "test_service_apply_restarts_systemd_service_and_verifies",
                "test_service_get_and_verify_relay_trojan_contract",
                "test_service_public_endpoint_plan_and_apply_reconcile_dns",
                "test_service_public_endpoint_verify_checks_dns_and_certificate_contract",
                "test_service_verify_allows_host_network_without_ports_metadata",
                "test_service_verify_checks_live_state_for_container_service",
            }
        ),
    ),
)


def apply_marker_rules(items: list[pytest.Item]) -> None:
    for item in items:
        for rule in MARKER_RULES:
            if rule.matches(item):
                for marker in rule.markers:
                    item.add_marker(getattr(pytest.mark, marker))
