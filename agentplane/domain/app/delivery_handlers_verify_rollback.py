"""Verify and rollback delivery handlers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agentplane.domain.app.delivery_handlers_planning import (
    _plan_delivery_rollback_steps,
    _plan_delivery_verify_steps,
)
from agentplane.domain.app.delivery_handlers_shared import (
    _load_validated_contract,
    _render_execution_steps,
)


def verify_delivery_for_app(
    repo_root: Path,
    *,
    target: str,
    app: str,
    dry_run: bool,
    execute: bool,
    app_repo_root: str | None = None,
) -> dict[str, Any]:
    app_cli, contract, _ = _load_validated_contract(repo_root, target=target, app=app, app_repo_root=app_repo_root)
    payload = app_cli.verify_app(contract, repo_root=repo_root, target=target, dry_run=dry_run, execute=execute)
    if dry_run:
        steps, _container_name = _plan_delivery_verify_steps(
            app_cli,
            contract,
            repo_root=repo_root,
            target=target,
            include_public=True,
        )
        execution_steps = _render_execution_steps(steps)
        payload["execution_steps"] = execution_steps
        payload["backend_type"] = steps[0].spec.backend_type if steps else None
        payload["commands"] = [step["backend"]["display_command"] for step in execution_steps]
    return {"command": "app", "action": "verify", "target": target, "payload": payload}


def rollback_for_app(
    repo_root: Path,
    *,
    target: str,
    app: str,
    dry_run: bool,
    execute: bool,
    app_repo_root: str | None = None,
) -> dict[str, Any]:
    app_cli, contract, _ = _load_validated_contract(repo_root, target=target, app=app, app_repo_root=app_repo_root)
    payload = app_cli.rollback_app(contract, repo_root=repo_root, target=target, dry_run=dry_run, execute=execute)
    if dry_run:
        steps, _rollback_entry = _plan_delivery_rollback_steps(
            app_cli,
            contract,
            repo_root=repo_root,
            target=target,
        )
        execution_steps = _render_execution_steps(steps)
        payload["execution_steps"] = execution_steps
        payload["backend_type"] = steps[0].spec.backend_type if steps else None
        if steps:
            payload["commands"] = [step["backend"]["display_command"] for step in execution_steps]
    payload["rollback_state"] = {
        "status": "planned" if dry_run or not execute else "executed" if payload.get("ok", True) else "failed",
        "previous_control_plane": contract["rollback"]["previous_control_plane"],
    }
    return {"command": "app", "action": "rollback", "target": target, "payload": payload}
