"""Rollback state assembly and post-action execution for delivery handlers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agentplane.domain.app.lifecycle import run_delivery_post_actions

_OBSERVATION_WINDOW_NOTE = (
    "旧 runtime 作为 rollback state 保留；只有 post-cutover verification 通过且 observation window 结束后才允许清理。"
)


def _delayed_cleanup_state(rollback_entry: dict[str, Any]) -> dict[str, Any]:
    kind = rollback_entry.get("kind")
    if kind == "none":
        return {
            "status": "not-applicable",
            "rollback_entry": rollback_entry,
            "observation_window_required": False,
            "commands": [],
            "note": "无旧 runtime 可保留或清理。",
        }
    return {
        "status": "observation-window-pending",
        "rollback_entry": rollback_entry,
        "observation_window_required": True,
        "commands": [],
        "note": _OBSERVATION_WINDOW_NOTE,
    }


def _rollback_state_payload(
    *,
    previous_control_plane: dict[str, Any],
    candidate: dict[str, Any],
    cutover: dict[str, Any],
    post_cutover_verification: dict[str, Any],
    rollback_on_failure: dict[str, Any],
    delayed_cleanup: dict[str, Any],
) -> dict[str, Any]:
    return {
        "previous_control_plane": previous_control_plane,
        "candidate": candidate,
        "cutover": cutover,
        "post_cutover_verification": post_cutover_verification,
        "rollback_on_failure": rollback_on_failure,
        "delayed_cleanup": delayed_cleanup,
    }


def _run_delivery_post_actions(
    repo_root: Path,
    *,
    target: str,
    app: str,
    app_repo_root: str | None = None,
    write: bool,
    write_evidence: bool,
    deploy_operation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return run_delivery_post_actions(
        repo_root,
        target=target,
        app=app,
        app_repo_root=app_repo_root,
        write=write,
        write_evidence=write_evidence,
        evidence_action="deploy",
        evidence_op_prefix="deploy-post-actions",
        deploy_operation=deploy_operation,
    )
