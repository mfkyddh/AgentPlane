"""Unit tests for roadmap risk and next-step derivation.

Tests _derive_risks() and _derive_next_step() logic against
synthetic roadmap data structures.
"""

from __future__ import annotations

import pytest
from agentplane.domain.repository.status import (
    _derive_next_step,
    _derive_risks,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Tests: _derive_risks
# ---------------------------------------------------------------------------


class TestDeriveRisks:
    def test_detects_blocked_phase(self) -> None:
        roadmap = {
            "ok": True,
            "current_phase": {"id": "P1", "name": "Beta", "status": "blocked", "gate": "pending"},
            "next_task": {"id": "P1-T1", "title": "Task", "status": "blocked"},
        }
        risks = _derive_risks(roadmap, {"docs": {"ok": True}}, {"count": 0, "items": []})
        kinds = [r["kind"] for r in risks]
        assert "blocked_phase" in kinds

    def test_detects_discussion_required(self) -> None:
        roadmap = {
            "ok": True,
            "current_phase": {"id": "P2", "name": "Gamma", "status": "planned", "gate": "pending"},
            "next_task": None,
        }
        risks = _derive_risks(roadmap, {"docs": {"ok": True}}, {"count": 0, "items": []})
        kinds = [r["kind"] for r in risks]
        assert "discussion_required" in kinds

    def test_detects_failed_check(self) -> None:
        roadmap = {"ok": True, "current_phase": {"id": "P1", "name": "Beta", "status": "active"}}
        checks = {"docs": {"ok": False}, "boundaries": {"ok": True}}
        risks = _derive_risks(roadmap, checks, {"count": 0, "items": []})
        kinds = [r["kind"] for r in risks]
        assert "failed_check" in kinds

    def test_detects_missing_inventory(self) -> None:
        roadmap = {"ok": True, "current_phase": {"id": "P1", "name": "Beta", "status": "active"}}
        targets = {
            "count": 1,
            "items": [{"target": "wsl", "inventory_exists": False, "readme_exists": False}],
        }
        risks = _derive_risks(roadmap, {"docs": {"ok": True}}, targets)
        kinds = [r["kind"] for r in risks]
        assert "missing_inventory" in kinds

    def test_detects_blocked_task(self) -> None:
        roadmap = {
            "ok": True,
            "current_phase": {"id": "P1", "name": "Beta", "status": "active", "gate": "confirmed"},
            "next_task": {"id": "P1-T1", "title": "Stuck", "status": "blocked"},
        }
        risks = _derive_risks(roadmap, {"docs": {"ok": True}}, {"count": 0, "items": []})
        kinds = [r["kind"] for r in risks]
        assert "blocked_task" in kinds

    def test_no_risks_when_everything_ok(self) -> None:
        roadmap = {
            "ok": True,
            "current_phase": {"id": "P1", "status": "active", "gate": "confirmed"},
            "next_task": {"id": "P1-T1", "title": "Task", "status": "todo"},
        }
        risks = _derive_risks(roadmap, {"docs": {"ok": True}}, {"count": 0, "items": []})
        assert risks == []

    def test_no_discussion_required_for_non_current_planned_phase(self) -> None:
        """Only the current phase should produce discussion_required, not later ones."""
        roadmap = {
            "ok": True,
            "current_phase": {"id": "P1", "status": "active", "gate": "confirmed"},
            "next_task": {"id": "P1-T1", "title": "Task", "status": "todo"},
        }
        risks = _derive_risks(roadmap, {"docs": {"ok": True}}, {"count": 0, "items": []})
        kinds = [r["kind"] for r in risks]
        assert "discussion_required" not in kinds


# ---------------------------------------------------------------------------
# Tests: _derive_next_step
# ---------------------------------------------------------------------------


class TestDeriveNextStep:
    def test_fix_issue_takes_priority(self) -> None:
        risks = [{"kind": "failed_check", "severity": "high", "message": "fail", "source_ref": "docs"}]
        roadmap = {
            "ok": True,
            "current_phase": {"id": "P1", "status": "active"},
            "next_task": {"id": "P1-T1", "title": "T", "status": "todo"},
        }
        result = _derive_next_step(risks, roadmap)
        assert result["type"] == "fix_issue"

    def test_commit_changes_second_priority(self) -> None:
        risks = [{"kind": "dirty_worktree", "severity": "medium", "message": "dirty", "source_ref": "git"}]
        roadmap = {
            "ok": True,
            "current_phase": {"id": "P1", "status": "active"},
            "next_task": {"id": "P1-T1", "title": "T", "status": "todo"},
        }
        result = _derive_next_step(risks, roadmap)
        assert result["type"] == "commit_changes"

    def test_discuss_gate_third_priority(self) -> None:
        roadmap = {
            "ok": True,
            "current_phase": {"id": "P2", "status": "planned", "gate": "pending"},
            "next_task": None,
        }
        result = _derive_next_step([], roadmap)
        assert result["type"] == "discuss_gate"

    def test_continue_task_fourth_priority(self) -> None:
        roadmap = {
            "ok": True,
            "current_phase": {"id": "P1", "status": "active"},
            "next_task": {"id": "P1-T2", "title": "Implement", "status": "todo"},
        }
        result = _derive_next_step([], roadmap)
        assert result["type"] == "continue_task"
        assert "P1-T2" in result["description"]

    def test_all_done_when_no_current_phase(self) -> None:
        roadmap = {"ok": True, "current_phase": None, "next_task": None}
        result = _derive_next_step([], roadmap)
        assert result["type"] == "all_done"
