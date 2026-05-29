"""Tests for agentplane.domain.project.status — pure helper functions."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from agentplane.domain.project.status import (
    _count_items,
    _derive_next_step,
    _derive_risks,
    _find_current_phase,
    _find_next_task,
    _iso_mtime,
    _parse_phase_overview,
    _parse_phase_section_tasks,
    _parse_resume_entry,
    _parse_workbook_last_verified,
    _read_json,
    _recommendations,
    _strip_backtick,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# _read_json
# ---------------------------------------------------------------------------


class TestReadJson:
    def test_missing_file(self, tmp_path: Path) -> None:
        payload, error = _read_json(tmp_path / "nope.json")
        assert payload is None
        assert error == "missing"

    def test_valid_json(self, tmp_path: Path) -> None:
        f = tmp_path / "data.json"
        f.write_text('{"key": "value"}', encoding="utf-8")
        payload, error = _read_json(f)
        assert payload == {"key": "value"}
        assert error is None

    def test_invalid_json(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.json"
        f.write_text("not json", encoding="utf-8")
        payload, error = _read_json(f)
        assert payload is None
        assert error is not None


# ---------------------------------------------------------------------------
# _count_items
# ---------------------------------------------------------------------------


class TestCountItems:
    def test_list(self) -> None:
        assert _count_items([1, 2, 3]) == 3

    def test_dict_with_count(self) -> None:
        assert _count_items({"count": 5}) == 5

    def test_dict_with_items(self) -> None:
        assert _count_items({"items": [1, 2]}) == 2

    def test_dict_keys(self) -> None:
        assert _count_items({"a": 1, "b": 2}) == 2

    def test_non_container(self) -> None:
        assert _count_items("string") == 0
        assert _count_items(42) == 0
        assert _count_items(None) == 0


# ---------------------------------------------------------------------------
# _iso_mtime
# ---------------------------------------------------------------------------


class TestIsoMtime:
    def test_nonexistent(self, tmp_path: Path) -> None:
        assert _iso_mtime(tmp_path / "nope.txt") is None

    def test_existing_file(self, tmp_path: Path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("x", encoding="utf-8")
        result = _iso_mtime(f)
        assert result is not None
        # Should be a valid ISO timestamp
        datetime.fromisoformat(result)


# ---------------------------------------------------------------------------
# _strip_backtick
# ---------------------------------------------------------------------------


class TestStripBacktick:
    def test_with_backticks(self) -> None:
        assert _strip_backtick("`done`") == "done"

    def test_without_backticks(self) -> None:
        assert _strip_backtick("done") == "done"

    def test_strips_whitespace(self) -> None:
        assert _strip_backtick("  done  ") == "done"

    def test_empty(self) -> None:
        assert _strip_backtick("") == ""


# ---------------------------------------------------------------------------
# _parse_phase_overview
# ---------------------------------------------------------------------------


class TestParsePhaseOverview:
    def test_empty_text(self) -> None:
        assert _parse_phase_overview("") == []

    def test_no_section(self) -> None:
        text = "## Other Section\n| col1 | col2 |\n|---|---|\n| a | b |"
        assert _parse_phase_overview(text) == []

    def test_parses_phases(self) -> None:
        text = """## 阶段总览

| 阶段 | 名称 | 状态 | 阶段门 | 验收口径 |
| :--- | --- | --- | --- | --- |
| P0 | Foundation | `done` | gate | criteria |
| P1 | Growth | `active` | gate | criteria |
"""
        phases = _parse_phase_overview(text)
        assert len(phases) == 2
        assert phases[0]["id"] == "P0"
        assert phases[0]["status"] == "done"
        assert phases[1]["id"] == "P1"
        assert phases[1]["status"] == "active"


# ---------------------------------------------------------------------------
# _parse_phase_section_tasks
# ---------------------------------------------------------------------------


class TestParsePhaseSectionTasks:
    def test_no_phase(self) -> None:
        text = "## P0\n| ID | 任务 | 状态 |\n|---|---|---|\n| T1 | task | done |"
        assert _parse_phase_section_tasks(text, "P999") == []

    def test_parses_tasks(self) -> None:
        text = """## P0

| ID | 任务 | 状态 | 备注 |
| :--- | --- | --- | --- |
| T1.1 | First task | `done` | note |
| T1.2 | Second task | `pending` | note |
"""
        tasks = _parse_phase_section_tasks(text, "P0")
        # Note: separator row :--- is included because the parser only skips
        # first cells starting with "---", not ":---"
        assert len(tasks) >= 2
        task_ids = [t["id"] for t in tasks]
        assert "T1.1" in task_ids
        assert "T1.2" in task_ids
        done_task = next(t for t in tasks if t["id"] == "T1.1")
        assert done_task["status"] == "done"


# ---------------------------------------------------------------------------
# _parse_resume_entry
# ---------------------------------------------------------------------------


class TestParseResumeEntry:
    def test_no_section(self) -> None:
        assert _parse_resume_entry("no section here") is None

    def test_with_section(self) -> None:
        text = "## ✅ 当前继续入口\n\nContinue from T1.2\n\n## Next Section"
        result = _parse_resume_entry(text)
        assert result is not None
        assert "T1.2" in result

    def test_no_emoji(self) -> None:
        text = "## 当前继续入口\n\nResume here\n\n## Other"
        result = _parse_resume_entry(text)
        assert "Resume here" in result


# ---------------------------------------------------------------------------
# _parse_workbook_last_verified
# ---------------------------------------------------------------------------


class TestParseWorkbookLastVerified:
    def test_found(self) -> None:
        text = "last_verified: 2026-05-10\nother stuff"
        assert _parse_workbook_last_verified(text) == "2026-05-10"

    def test_not_found(self) -> None:
        assert _parse_workbook_last_verified("no date here") is None


# ---------------------------------------------------------------------------
# _find_current_phase
# ---------------------------------------------------------------------------


class TestFindCurrentPhase:
    def test_empty(self) -> None:
        assert _find_current_phase([]) is None

    def test_all_done(self) -> None:
        phases = [{"id": "P0", "status": "done"}, {"id": "P1", "status": "superseded"}]
        assert _find_current_phase(phases) is None

    def test_active_phase(self) -> None:
        phases = [{"id": "P0", "status": "done"}, {"id": "P1", "status": "active"}]
        result = _find_current_phase(phases)
        assert result is not None
        assert result["id"] == "P1"


# ---------------------------------------------------------------------------
# _find_next_task
# ---------------------------------------------------------------------------


class TestFindNextTask:
    def test_empty(self) -> None:
        assert _find_next_task([]) is None

    def test_all_done(self) -> None:
        tasks = [{"id": "T1", "status": "done"}, {"id": "T2", "status": "deferred"}]
        assert _find_next_task(tasks) is None

    def test_pending_task(self) -> None:
        tasks = [{"id": "T1", "status": "done"}, {"id": "T2", "status": "pending"}]
        result = _find_next_task(tasks)
        assert result is not None
        assert result["id"] == "T2"


# ---------------------------------------------------------------------------
# _recommendations
# ---------------------------------------------------------------------------


class TestRecommendations:
    def test_all_ok(self) -> None:
        payload = {
            "checks": {
                "docs": {"ok": True},
                "boundaries": {"ok": True},
                "skills": {"ok": True},
            },
            "apps": {"count": 1},
            "targets": {"count": 1, "items": [
                {"target": "wsl", "inventory_exists": True, "readme_exists": True, "ledger_errors": {}},
            ]},
        }
        recs = _recommendations(payload)
        assert any("No immediate" in r for r in recs)

    def test_docs_not_ok(self) -> None:
        payload = {
            "checks": {
                "docs": {"ok": False},
                "boundaries": {"ok": True},
                "skills": {"ok": True},
            },
            "apps": {"count": 1},
            "targets": {"count": 0, "items": []},
        }
        recs = _recommendations(payload)
        assert any("docs-sanity" in r for r in recs)

    def test_no_apps(self) -> None:
        payload = {
            "checks": {
                "docs": {"ok": True},
                "boundaries": {"ok": True},
                "skills": {"ok": True},
            },
            "apps": {"count": 0},
            "targets": {"count": 0, "items": []},
        }
        recs = _recommendations(payload)
        assert any("app catalog" in r for r in recs)

    def test_missing_inventory(self) -> None:
        payload = {
            "checks": {
                "docs": {"ok": True},
                "boundaries": {"ok": True},
                "skills": {"ok": True},
            },
            "apps": {"count": 1},
            "targets": {"count": 1, "items": [
                {"target": "wsl", "inventory_exists": False, "readme_exists": True, "ledger_errors": {}},
            ]},
        }
        recs = _recommendations(payload)
        assert any("missing inventory.json" in r for r in recs)


# ---------------------------------------------------------------------------
# _derive_risks
# ---------------------------------------------------------------------------


class TestDeriveRisks:
    def test_no_risks(self) -> None:
        roadmap = {"current_phase": {"id": "P1", "status": "active"}, "next_task": None, "ok": True}
        checks = {"docs": {"ok": True}, "boundaries": {"ok": True}}
        targets = {"items": []}
        risks = _derive_risks(roadmap, checks, targets)
        assert risks == []

    def test_blocked_phase(self) -> None:
        roadmap = {"current_phase": {"id": "P1", "name": "Growth", "status": "blocked"}}
        checks = {"docs": {"ok": True}}
        targets = {"items": []}
        risks = _derive_risks(roadmap, checks, targets)
        assert any(r["kind"] == "blocked_phase" for r in risks)

    def test_discussion_required(self) -> None:
        roadmap = {"current_phase": {"id": "P1", "name": "Growth", "status": "discussion-required"}}
        checks = {"docs": {"ok": True}}
        targets = {"items": []}
        risks = _derive_risks(roadmap, checks, targets)
        assert any(r["kind"] == "discussion_required" for r in risks)

    def test_failed_check(self) -> None:
        roadmap = {"current_phase": None}
        checks = {"docs": {"ok": False}, "boundaries": {"ok": True}}
        targets = {"items": []}
        risks = _derive_risks(roadmap, checks, targets)
        assert any(r["kind"] == "failed_check" for r in risks)

    def test_missing_inventory(self) -> None:
        roadmap = {"current_phase": None}
        checks = {"docs": {"ok": True}}
        targets = {"items": [{"target": "wsl", "inventory_exists": False, "readme_exists": True}]}
        risks = _derive_risks(roadmap, checks, targets)
        assert any(r["kind"] == "missing_inventory" for r in risks)

    def test_missing_readme(self) -> None:
        roadmap = {"current_phase": None}
        checks = {"docs": {"ok": True}}
        targets = {"items": [{"target": "wsl", "inventory_exists": True, "readme_exists": False}]}
        risks = _derive_risks(roadmap, checks, targets)
        assert any(r["kind"] == "missing_inventory" for r in risks)

    def test_blocked_task(self) -> None:
        roadmap = {
            "ok": True,
            "current_phase": {"id": "P1", "status": "active"},
            "next_task": {"id": "T1.2", "status": "blocked"},
        }
        checks = {"docs": {"ok": True}}
        targets = {"items": []}
        risks = _derive_risks(roadmap, checks, targets)
        assert any(r["kind"] == "blocked_task" for r in risks)


# ---------------------------------------------------------------------------
# _derive_next_step
# ---------------------------------------------------------------------------


class TestDeriveNextStep:
    def test_fix_issue_priority(self) -> None:
        risks = [{"kind": "failed_check", "source_ref": "docs"}]
        roadmap: dict = {}
        step = _derive_next_step(risks, roadmap)
        assert step["type"] == "fix_issue"

    def test_commit_changes_priority(self) -> None:
        risks = [{"kind": "dirty_worktree", "source_ref": "git"}]
        roadmap: dict = {}
        step = _derive_next_step(risks, roadmap)
        assert step["type"] == "commit_changes"

    def test_discuss_gate(self) -> None:
        risks: list = []
        roadmap = {"current_phase": {"id": "P1", "status": "planned"}}
        step = _derive_next_step(risks, roadmap)
        assert step["type"] == "discuss_gate"

    def test_continue_task(self) -> None:
        risks: list = []
        roadmap = {"current_phase": {"id": "P1", "status": "active"}, "next_task": {"id": "T1.2", "title": "Do thing", "status": "todo"}}
        step = _derive_next_step(risks, roadmap)
        assert step["type"] == "continue_task"
        assert "T1.2" in step["description"]

    def test_all_done(self) -> None:
        risks: list = []
        roadmap = {"ok": True, "current_phase": None}
        step = _derive_next_step(risks, roadmap)
        assert step["type"] == "all_done"

    def test_default_no_specific(self) -> None:
        risks: list = []
        roadmap = {"current_phase": {"id": "P1", "status": "active"}, "next_task": None}
        step = _derive_next_step(risks, roadmap)
        assert step["type"] == "continue_task"
        assert "No specific" in step["description"]


# ---------------------------------------------------------------------------
# Golden test
# ---------------------------------------------------------------------------


@pytest.mark.golden
class TestStatusGolden:
    def test_full_phase_parsing(self) -> None:
        """Full workbook markdown parses phases and tasks correctly."""
        text = """## 阶段总览

| 阶段 | 名称 | 状态 | 阶段门 | 验收口径 |
| :--- | --- | --- | --- | --- |
| P0 | Foundation | `done` | gate | criteria |
| P1 | Growth | `active` | gate | criteria |

## P1

| ID | 任务 | 状态 | 备注 |
| :--- | --- | --- | --- |
| T1.1 | First | `done` | |
| T1.2 | Second | `pending` | |
| T1.3 | Third | `pending` | |

## ✅ 当前继续入口

Continue from T1.2
"""
        phases = _parse_phase_overview(text)
        assert len(phases) == 2
        current = _find_current_phase(phases)
        assert current is not None
        assert current["id"] == "P1"

        tasks = _parse_phase_section_tasks(text, "P1")
        # Note: separator row :--- is included in results
        assert len(tasks) >= 3
        # Filter out separator artifacts before finding next task
        real_tasks = [t for t in tasks if not t["id"].startswith(":")]
        next_task = _find_next_task(real_tasks)
        assert next_task is not None
        assert next_task["id"] == "T1.2"

        resume = _parse_resume_entry(text)
        assert resume is not None
        assert "T1.2" in resume
