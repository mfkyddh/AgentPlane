"""App rollback execution logic extracted from runtime."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agentplane.domain.app.doc_sync import render_rollback_entry
from agentplane.domain.app.runtime import (
    _control_plane_transition_step,
    _execute_step,
    _local_backend_type,
    _record_app_operation,
    _target_ssh_target,
)
from agentplane.domain.app.runtime_helpers import _remote_compose_filename
from agentplane.runtime.operations import next_operation_id


def rollback_app(
    contract: dict[str, Any], *, repo_root: Path, target: str, dry_run: bool, execute: bool
) -> dict[str, Any]:
    op_id = next_operation_id("rollback-app")
    rollback_entry = contract["rollback"]["previous_control_plane"]
    local_backend = _local_backend_type()
    if target == "wsl":
        operation = _record_app_operation(
            repo_root,
            action="rollback",
            target=target,
            dry_run=dry_run,
            operation={"op_id": op_id, "target": target, "result": "planned" if dry_run else "local-only"},
            details={"artifact_summary": rollback_entry.get("kind", "unknown")},
        )
        return {
            "rollback_entry": rollback_entry,
            "operation": operation,
            "dry_run": dry_run,
        }
    if execute and dry_run:
        raise ValueError("rollback 不允许同时传 --dry-run 和 --execute")
    if rollback_entry.get("kind") == "none":
        operation = _record_app_operation(
            repo_root,
            action="rollback",
            target=target,
            dry_run=dry_run,
            operation={"op_id": op_id, "target": target, "result": "noop"},
            details={"artifact_summary": rollback_entry.get("kind", "none")},
        )
        return {
            "rollback_entry": rollback_entry,
            "commands": [],
            "warning": render_rollback_entry(rollback_entry),
            "operation": operation,
            "dry_run": dry_run,
            "ok": True,
        }
    ssh_target = _target_ssh_target(repo_root, target)
    transition_step = _control_plane_transition_step(
        repo_root, target=target, rollback_entry=rollback_entry, operate="start"
    )
    commands = [
        ssh_target.display_ssh_command(
            f"cd /opt/agentplane/infra/compose/{contract['app_id']} && docker compose -f {_remote_compose_filename(target)} down || true"
        ),
        transition_step[1] if transition_step else None,
    ]
    commands = [command for command in commands if command]
    if not execute:
        operation = _record_app_operation(
            repo_root,
            action="rollback",
            target=target,
            dry_run=dry_run,
            operation={
                "op_id": op_id,
                "target": target,
                "artifact_summary": rollback_entry.get("kind", "unknown"),
                "result": "planned",
            },
            details={"artifact_summary": rollback_entry.get("kind", "unknown")},
        )
        return {
            "rollback_entry": rollback_entry,
            "commands": commands,
            "operation": operation,
            "dry_run": dry_run,
        }
    steps = [
        (
            ssh_target.local_ssh_args_for_shell(
                f"cd /opt/agentplane/infra/compose/{contract['app_id']} && docker compose -f {_remote_compose_filename(target)} down || true"
            ),
            ssh_target.display_ssh_command(
                f"cd /opt/agentplane/infra/compose/{contract['app_id']} && docker compose -f {_remote_compose_filename(target)} down || true"
            ),
        ),
    ]
    if transition_step:
        steps.append(transition_step)
    step_results = [
        _execute_step(
            argv=argv,
            display=display,
            backend_type=local_backend if argv and argv[0] == "python3" else None,
            capabilities=("python3",) if argv and argv[0] == "python3" else None,
        )
        for argv, display in steps
    ]
    ok = all(item["ok"] for item in step_results)
    operation = _record_app_operation(
        repo_root,
        action="rollback",
        target=target,
        dry_run=False,
        operation={
            "op_id": op_id,
            "target": target,
            "artifact_summary": rollback_entry.get("kind", "unknown"),
            "result": "rolled-back" if ok else "failed",
        },
        details={"artifact_summary": rollback_entry.get("kind", "unknown")},
    )
    return {
        "rollback_entry": rollback_entry,
        "commands": [display for _, display in steps],
        "results": step_results,
        "operation": operation,
        "dry_run": False,
        "ok": ok,
    }
