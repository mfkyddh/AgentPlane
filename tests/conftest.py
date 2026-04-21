from __future__ import annotations

from pathlib import Path

import pytest


EXTERNAL_APP_FILES = {
    "test_sub2api_compose_layout.py",
}

INTEGRATION_WSL_FILES = {
    "test_wsl_audit.py",
}

INTEGRATION_WSL_TESTS = {
    "test_build_artifact_executes_script_build_command_with_image_tag",
    "test_build_artifact_auto_version_executes_with_recommended_image_tag",
    "test_build_artifact_auto_version_exposes_recommended_version_env_vars",
    "test_build_artifact_auto_version_uses_git_tag_when_version_file_missing",
    "test_build_artifact_prefers_explicit_app_repo_root_over_catalog_repo_root",
    "test_package_runtime_executes_packaging_command_with_explicit_artifact_output_and_image_ref",
}

DOCKER_OR_SSH_EXECUTION_TESTS = {
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


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        filename = Path(str(item.fspath)).name
        if filename in EXTERNAL_APP_FILES:
            item.add_marker(pytest.mark.external_app)
        if filename in INTEGRATION_WSL_FILES or item.name in INTEGRATION_WSL_TESTS:
            item.add_marker(pytest.mark.integration_wsl)
        if item.name in DOCKER_OR_SSH_EXECUTION_TESTS:
            item.add_marker(pytest.mark.docker_required)
            item.add_marker(pytest.mark.ssh_required)
