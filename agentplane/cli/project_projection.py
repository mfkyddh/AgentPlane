from __future__ import annotations

import argparse
from typing import Any

from agentplane.domain.app.projection.runtime_env import (
    apply_runtime_env_projection,
    plan_runtime_env_projection,
    verify_runtime_env_projection,
)
from agentplane.providers.onepanel_fixtures import (
    apply_fixture,
    cleanup_fixture,
    plan_fixture,
    resolve_fixture_spec,
    run_onepanel_verification_suite,
)
from agentplane.providers.onepanel_ledgers import refresh_onepanel_ledgers
from agentplane.providers.onepanel_objects import onepanel_target_executor
from agentplane.runtime.redaction import redact_sensitive_value
from agentplane.runtime.wsl_bridge import normalize_repo_root_for_current_host

_PROJECTION_SURFACE_CONTRACTS = {
    "runtime-env": "projection",
    "verification": "observation",
    "fixture": "projection",
    "ledger": "projection",
}


def _wrap_projection(surface: str, action: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "command": "project",
        "surface_contract": _PROJECTION_SURFACE_CONTRACTS[surface],
        "action": action,
        **payload,
    }


def _handle_projection(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = normalize_repo_root_for_current_host(args.repo_root)
    surface = args.project_projection_surface

    if surface == "runtime-env" and args.project_projection_action == "plan":
        return _wrap_projection("runtime-env", "runtime-env.plan",
            plan_runtime_env_projection(repo_root, args.target, args.app, reveal_secrets=args.reveal_secrets))
    if surface == "runtime-env" and args.project_projection_action == "apply":
        return _wrap_projection("runtime-env", "runtime-env.apply",
            apply_runtime_env_projection(repo_root, args.target, args.app, reveal_secrets=args.reveal_secrets))
    if surface == "runtime-env" and args.project_projection_action == "verify":
        return _wrap_projection("runtime-env", "runtime-env.verify",
            verify_runtime_env_projection(repo_root, args.target, args.app, reveal_secrets=args.reveal_secrets))
    if surface == "verification" and args.project_projection_verification_action == "run":
        payload = run_onepanel_verification_suite(
            onepanel_target_executor(args.target),
            profile=args.profile, env=args.target, repo_root=repo_root,
            write_report=bool(args.write_report), website_alias=args.website_alias,
            container_name=args.container_name, project_name=args.project_name,
            cronjob_id=args.cronjob_id, cronjob_name=args.cronjob_name,
            app_name=args.app_name, firewall_tab=args.firewall_tab,
        )
        return _wrap_projection("verification", "verification.run", redact_sensitive_value(payload))
    if surface == "fixture":
        fixture_action = args.project_projection_fixture_action
        if fixture_action in {"apply", "cleanup"} and not bool(args.execute):
            raise ValueError(f"project projection fixture {fixture_action} requires --execute")
        spec = resolve_fixture_spec(
            args.profile, env=args.target, website_alias=args.website_alias,
            container_name=args.container_name, project_name=args.project_name,
            cronjob_name=args.cronjob_name, firewall_tab=args.firewall_tab,
        )
        executor = onepanel_target_executor(args.target)
        if fixture_action == "plan":
            payload = plan_fixture(executor, spec)
        elif fixture_action == "apply":
            payload = apply_fixture(executor, spec, execute=True)
        else:
            payload = cleanup_fixture(executor, spec, execute=True)
        return _wrap_projection("fixture", f"fixture.{fixture_action}", payload)
    if surface == "ledger" and args.project_projection_ledger_action == "refresh":
        return _wrap_projection("ledger", "ledger.refresh",
            refresh_onepanel_ledgers(repo_root, args.target, write=bool(args.write)))

    action = (getattr(args, "project_projection_action", None)
        or getattr(args, "project_projection_verification_action", None)
        or getattr(args, "project_projection_fixture_action", None)
        or getattr(args, "project_projection_ledger_action", None)
        or "unknown")
    raise ValueError(f"Unsupported projection action: {surface}.{action}")
