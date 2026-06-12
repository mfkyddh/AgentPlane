from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentplane.domain.project.status_checks import (
    _apps_status,
    _recommendations,
    _repo_boundary_status,
    _repo_docs_status,
    _skills_status,
    _targets_status,
)
from agentplane.domain.project.status_workbook import _workbook_status

_STALE_THRESHOLD_DAYS = 30


def _derive_risks(
    roadmap: dict[str, Any],
    checks: dict[str, Any],
    targets: dict[str, Any],
) -> list[dict[str, str]]:
    risks: list[dict[str, str]] = []

    current_phase = roadmap.get("current_phase")
    if current_phase and current_phase["status"] == "blocked":
        risks.append(
            {
                "kind": "blocked_phase",
                "severity": "high",
                "message": f"{current_phase['id']} ({current_phase['name']}) is blocked.",
                "source_ref": current_phase["id"],
            }
        )

    if current_phase and current_phase["status"] in ("planned", "discussion-required"):
        risks.append(
            {
                "kind": "discussion_required",
                "severity": "high",
                "message": f"{current_phase['id']} ({current_phase['name']}) requires discussion before proceeding.",
                "source_ref": current_phase["id"],
            }
        )

    failed_checks: list[str] = []
    for area, data in checks.items():
        if not data.get("ok", True):
            failed_checks.append(area)
    if failed_checks:
        risks.append(
            {
                "kind": "failed_check",
                "severity": "high",
                "message": f"Checks failed: {', '.join(failed_checks)}.",
                "source_ref": ", ".join(failed_checks),
            }
        )

    if roadmap.get("ok") and current_phase and current_phase["status"] in ("approved", "active"):
        next_task = roadmap.get("next_task")
        if next_task and next_task["status"] == "blocked":
            risks.append(
                {
                    "kind": "blocked_task",
                    "severity": "medium",
                    "message": f"Task {next_task['id']} is blocked.",
                    "source_ref": next_task["id"],
                }
            )

    missing: list[str] = []
    for target in targets.get("items", []):
        if not target.get("inventory_exists"):
            missing.append(target["target"])
        elif not target.get("readme_exists"):
            missing.append(target["target"])
    if missing:
        risks.append(
            {
                "kind": "missing_inventory",
                "severity": "medium",
                "message": f"Targets missing inventory or README: {', '.join(missing)}.",
                "source_ref": ", ".join(missing),
            }
        )

    now = datetime.now(timezone.utc)
    stale: list[str] = []
    for target in targets.get("items", []):
        for ledger_name, updated_str in target.get("ledger_updated", {}).items():
            if updated_str is None:
                continue
            try:
                updated = datetime.fromisoformat(updated_str)
                if (now - updated).days > _STALE_THRESHOLD_DAYS:
                    stale.append(f"{target['target']}/{ledger_name}")
                    break
            except (ValueError, TypeError):
                pass
    if stale:
        risks.append(
            {
                "kind": "stale_data",
                "severity": "low",
                "message": f"Stale ledgers (> {_STALE_THRESHOLD_DAYS} days): {', '.join(stale)}.",
                "source_ref": ", ".join(stale),
            }
        )

    return risks


def _check_dirty_worktree(repo_root: Path) -> bool:
    import subprocess

    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        return bool(result.stdout.strip())
    except (OSError, subprocess.TimeoutExpired):
        return False


def _derive_next_step(
    risks: list[dict[str, str]],
    roadmap: dict[str, Any],
) -> dict[str, str]:
    risk_kinds = {r["kind"] for r in risks}

    if "failed_check" in risk_kinds:
        source = next(r["source_ref"] for r in risks if r["kind"] == "failed_check")
        return {
            "type": "fix_issue",
            "description": "Fix failing checks before continuing.",
            "target_ref": source,
        }

    if "dirty_worktree" in risk_kinds:
        return {
            "type": "commit_changes",
            "description": "Commit or handle uncommitted changes in the working tree.",
            "target_ref": "git",
        }

    current_phase = roadmap.get("current_phase")
    if current_phase and current_phase["status"] in ("planned", "discussion-required"):
        return {
            "type": "discuss_gate",
            "description": f"{current_phase['id']} phase gate needs discussion: confirm direction, technology, and scope.",
            "target_ref": current_phase["id"],
        }

    next_task = roadmap.get("next_task")
    if next_task and next_task["status"] in ("todo", "in-progress"):
        return {
            "type": "continue_task",
            "description": f"Execute {next_task['id']}: {next_task['title']}.",
            "target_ref": next_task["id"],
        }

    if roadmap.get("ok") and roadmap.get("current_phase") is None:
        return {
            "type": "all_done",
            "description": "All roadmap phases are complete. Consider adding new phases or closing the roadmap.",
            "target_ref": "roadmap",
        }

    return {
        "type": "continue_task",
        "description": "No specific next step identified.",
        "target_ref": "",
    }


def build_repo_status(repo_root: Path) -> dict[str, Any]:
    root = repo_root.resolve()
    checks = {
        "docs": _repo_docs_status(root),
        "boundaries": _repo_boundary_status(root),
        "skills": _skills_status(root),
    }
    payload: dict[str, Any] = {
        "command": "repo",
        "action": "status",
        "repo_root": str(root),
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "ok": all(check["ok"] for check in checks.values()),
        "checks": checks,
        "apps": _apps_status(root),
        "targets": _targets_status(root),
    }
    payload["summary"] = {
        "repo_checks_ok": payload["ok"],
        "public_skills": checks["skills"]["count"],
        "targets": payload["targets"]["count"],
        "apps": payload["apps"]["count"],
    }
    payload["recommendations"] = _recommendations(payload)
    payload["roadmap"] = _workbook_status(root)

    risks = _derive_risks(payload["roadmap"], payload["checks"], payload["targets"])
    if _check_dirty_worktree(root):
        risks.append(
            {
                "kind": "dirty_worktree",
                "severity": "medium",
                "message": "Uncommitted changes in the working tree.",
                "source_ref": "git",
            }
        )
    severity_order = {"high": 0, "medium": 1, "low": 2}
    risks.sort(key=lambda r: severity_order.get(r["severity"], 3))
    payload["risks"] = risks
    payload["next_step"] = _derive_next_step(risks, payload["roadmap"])

    return payload
