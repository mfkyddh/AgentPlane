"""Tests for agentplane.domain.project.status — pure helper functions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

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
    _strip_backtick,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# _read_json
# ---------------------------------------------------------------------------


class TestReadJson:
    def test_valid(self, tmp_path: Path) -> None:
        f = tmp_path / "data.json"
        f.write_text('{"key": "value"}', encoding="utf-8")
        payload, error = _read_json(f)
        assert payload["key"] == "value"
        assert error is None

    def test_missing(self, tmp_path: Path) -> None:
        payload, error = _read_json(tmp_path / "missing.json")
        assert payload is None
        assert error == "missing"

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

    def test_dict_fallback(self) -> None:
        assert _count_items({"a": 1, "b": 2}) == 2

    def test_empty_list(self) -> None:
        assert _count_items([]) == 0

    def test_non_container(self) -> None:
        assert _count_items("invalid") == 0

    def test_none(self) -> None:
        assert _count_items(None) == 0


# ---------------------------------------------------------------------------
# _iso_mtime
# ---------------------------------------------------------------------------


class TestIsoMtime:
    def test_existing_file(self, tmp_path: Path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("x", encoding="utf-8")
        result = _iso_mtime(f)
        assert result is not None
        assert "T" in result

    def test_missing_file(self, tmp_path: Path) -> None:
        assert _iso_mtime(tmp_path / "missing.txt") is None


# ---------------------------------------------------------------------------
# _strip_backtick
# ---------------------------------------------------------------------------


class TestStripBacktick:
    def test_with_backticks(self) -> None:
        assert _strip_backtick("`done`") == "done"

    def test_without_backticks(self) -> None:
        assert _strip_backtick("done") == "done"

    def test_empty(self) -> None:
        assert _strip_backtick("") == ""

    def test_whitespace(self) -> None:
        assert _strip_backtick("  `active`  ") == "active"


# ---------------------------------------------------------------------------
# _parse_phase_overview
# ---------------------------------------------------------------------------


class TestParsePhaseOverview:
    def test_valid_table(self) -> None:
        text = """## 阶段总览

| 阶段 | 名称 | 状态 | 阶段门 | 验收口径 |
| --- | --- | --- | --- | --- |
| P0 | Foundation | `done` | confirmed | |
| P1 | Beta | `active` | confirmed | |
"""
        phases = _parse_phase_overview(text)
        assert len(phases) == 2
        assert phases[0]["id"] == "P0"
        assert phases[0]["status"] == "done"
        assert phases[1]["id"] == "P1"
        assert phases[1]["status"] == "active"

    def test_no_section(self) -> None:
        assert _parse_phase_overview("no section here") == []

    def test_empty_section(self) -> None:
        text = "## 阶段总览\n\n## Next Section\n"
        assert _parse_phase_overview(text) == []


# ---------------------------------------------------------------------------
# _parse_phase_section_tasks
# ---------------------------------------------------------------------------


class TestParsePhaseSectionTasks:
    def test_valid_tasks(self) -> None:
        text = """## P0

### 第一轮任务

| ID | 任务 | 状态 |
| --- | --- | --- |
| T0.1 | Setup | `done` |
| T0.2 | Config | `todo` |
"""
        tasks = _parse_phase_section_tasks(text, "P0")
        assert len(tasks) == 2
        assert tasks[0]["id"] == "T0.1"
        assert tasks[0]["status"] == "done"
        assert tasks[1]["id"] == "T0.2"

    def test_missing_phase(self) -> None:
        assert _parse_phase_section_tasks("## P0\n", "P99") == []

    def test_no_tasks(self) -> None:
        text = "## P0\n\nNo table here.\n"
        assert _parse_phase_section_tasks(text, "P0") == []


# ---------------------------------------------------------------------------
# _parse_resume_entry
# ---------------------------------------------------------------------------


class TestParseResumeEntry:
    def test_with_content(self) -> None:
        text = "## 当前继续入口\n\nSome content here.\n\n## Next\n"
        result = _parse_resume_entry(text)
        assert result is not None
        assert "Some content" in result

    def test_missing_section(self) -> None:
        assert _parse_resume_entry("no section") is None

    def test_empty_section(self) -> None:
        text = "## 当前继续入口\n\n## Next\n"
        result = _parse_resume_entry(text)
        assert result is not None


# ---------------------------------------------------------------------------
# _parse_workbook_last_verified
# ---------------------------------------------------------------------------


class TestParseWorkbookLastVerified:
    def test_found(self) -> None:
        text = "---\nlast_verified: 2026-05-10\n---\n"
        assert _parse_workbook_last_verified(text) == "2026-05-10"

    def test_not_found(self) -> None:
        assert _parse_workbook_last_verified("no frontmatter") is None


# ---------------------------------------------------------------------------
# _find_current_phase
# ---------------------------------------------------------------------------


class TestFindCurrentPhase:
    def test_first_active(self) -> None:
        phases = [{"id": "P0", "status": "done"}, {"id": "P1", "status": "active"}]
        result = _find_current_phase(phases)
        assert result["id"] == "P1"

    def test_all_done(self) -> None:
        phases = [{"id": "P0", "status": "done"}, {"id": "P1", "status": "superseded"}]
        assert _find_current_phase(phases) is None

    def test_empty(self) -> None:
        assert _find_current_phase([]) is None

    def test_planned(self) -> None:
        phases = [{"id": "P0", "status": "done"}, {"id": "P1", "status": "planned"}]
        result = _find_current_phase(phases)
        assert result["id"] == "P1"


# ---------------------------------------------------------------------------
# _find_next_task
# ---------------------------------------------------------------------------


class TestFindNextTask:
    def test_first_todo(self) -> None:
        tasks = [{"id": "T1", "status": "done"}, {"id": "T2", "status": "todo"}]
        result = _find_next_task(tasks)
        assert result["id"] == "T2"

    def test_in_progress(self) -> None:
        tasks = [{"id": "T1", "status": "in-progress"}]
        result = _find_next_task(tasks)
        assert result["id"] == "T1"

    def test_all_done(self) -> None:
        tasks = [{"id": "T1", "status": "done"}, {"id": "T2", "status": "deferred"}]
        assert _find_next_task(tasks) is None

    def test_empty(self) -> None:
        assert _find_next_task([]) is None


# ---------------------------------------------------------------------------
# _derive_risks
# ---------------------------------------------------------------------------


class TestDeriveRisks:
    def test_blocked_phase(self) -> None:
        roadmap: dict[str, Any] = {"ok": True, "current_phase": {"id": "P1", "name": "Beta", "status": "blocked"}, "next_task": None}
        checks: dict[str, Any] = {"docs": {"ok": True}, "boundaries": {"ok": True}, "skills": {"ok": True}}
        targets: dict[str, Any] = {"items": []}
        risks = _derive_risks(roadmap, checks, targets)
        assert any(r["kind"] == "blocked_phase" for r in risks)

    def test_failed_check(self) -> None:
        roadmap: dict[str, Any] = {"ok": True, "current_phase": None, "next_task": None}
        checks: dict[str, Any] = {"docs": {"ok": False}, "boundaries": {"ok": True}}
        targets: dict[str, Any] = {"items": []}
        risks = _derive_risks(roadmap, checks, targets)
        assert any(r["kind"] == "failed_check" for r in risks)

    def test_missing_inventory(self) -> None:
        roadmap: dict[str, Any] = {"ok": True, "current_phase": None, "next_task": None}
        checks: dict[str, Any] = {"docs": {"ok": True}, "boundaries": {"ok": True}, "skills": {"ok": True}}
        targets: dict[str, Any] = {"items": [{"target": "wsl", "inventory_exists": False}]}
        risks = _derive_risks(roadmap, checks, targets)
        assert any(r["kind"] == "missing_inventory" for r in risks)

    def test_no_risks(self) -> None:
        roadmap: dict[str, Any] = {"ok": True, "current_phase": None, "next_task": None}
        checks: dict[str, Any] = {"docs": {"ok": True}, "boundaries": {"ok": True}, "skills": {"ok": True}}
        targets: dict[str, Any] = {"items": []}
        risks = _derive_risks(roadmap, checks, targets)
        assert len(risks) == 0


# ---------------------------------------------------------------------------
# _derive_next_step
# ---------------------------------------------------------------------------


class TestDeriveNextStep:
    def test_fix_issue(self) -> None:
        risks: list[dict[str, str]] = [{"kind": "failed_check", "severity": "high", "message": "x", "source_ref": "docs"}]
        roadmap: dict[str, Any] = {"current_phase": None, "next_task": None}
        step = _derive_next_step(risks, roadmap)
        assert step["type"] == "fix_issue"

    def test_discuss_gate(self) -> None:
        roadmap: dict[str, Any] = {"current_phase": {"id": "P1", "status": "planned"}, "next_task": None}
        step = _derive_next_step([], roadmap)
        assert step["type"] == "discuss_gate"

    def test_continue_task(self) -> None:
        roadmap: dict[str, Any] = {"current_phase": {"id": "P1", "status": "active"}, "next_task": {"id": "T1", "title": "Work", "status": "todo"}}
        step = _derive_next_step([], roadmap)
        assert step["type"] == "continue_task"

    def test_all_done(self) -> None:
        roadmap: dict[str, Any] = {"ok": True, "current_phase": None, "next_task": None}
        step = _derive_next_step([], roadmap)
        assert step["type"] == "all_done"

    def test_blocked_task(self) -> None:
        roadmap: dict[str, Any] = {"current_phase": {"id": "P1", "status": "active"}, "next_task": {"id": "T1", "title": "Work", "status": "blocked"}}
        risks: list[dict[str, str]] = [{"kind": "blocked_task", "severity": "medium", "message": "x", "source_ref": "T1"}]
        step = _derive_next_step(risks, roadmap)
        assert step["type"] == "continue_task"


# ---------------------------------------------------------------------------
# Golden test
# ---------------------------------------------------------------------------


@pytest.mark.golden
class TestStatusHelpersGolden:
    def test_full_workbook_parse(self) -> None:
        """Full workbook with phases, tasks, resume entry, and frontmatter."""
        text = """---
last_verified: 2026-05-10
---

## 阶段总览

| 阶段 | 名称 | 状态 | 阶段门 | 验收口径 |
| --- | --- | --- | --- | --- |
| P0 | Foundation | `done` | confirmed | |
| P1 | Beta | `active` | confirmed | |

## P1

### 第一轮任务

| ID | 任务 | 状态 |
| --- | --- | --- |
| T1.1 | Tests | `done` |
| T1.2 | Docs | `todo` |
| T1.3 | WebUI | `blocked` |

## 当前继续入口

Next: T1.2 Docs
"""
        phases = _parse_phase_overview(text)
        assert len(phases) == 2
        assert phases[1]["status"] == "active"

        current = _find_current_phase(phases)
        assert current["id"] == "P1"

        tasks = _parse_phase_section_tasks(text, "P1")
        assert len(tasks) == 3

        next_task = _find_next_task(tasks)
        assert next_task["id"] == "T1.2"

        resume = _parse_resume_entry(text)
        assert "T1.2" in resume

        last_verified = _parse_workbook_last_verified(text)
        assert last_verified == "2026-05-10"

    def test_full_risks_and_next_step(self) -> None:
        """Risks and next step derivation from a complex state."""
        roadmap: dict[str, Any] = {
            "ok": True,
            "current_phase": {"id": "P1", "name": "Beta", "status": "active", "gate": "confirmed"},
            "next_task": {"id": "T1.2", "title": "Docs", "status": "blocked"},
        }
        checks: dict[str, Any] = {"docs": {"ok": False}, "boundaries": {"ok": True}, "skills": {"ok": True}}
        targets: dict[str, Any] = {"items": [{"target": "wsl", "inventory_exists": True, "readme_exists": False, "ledger_updated": {}}]}
        risks = _derive_risks(roadmap, checks, targets)
        assert len(risks) >= 2  # failed_check + missing_inventory + blocked_task

        next_step = _derive_next_step(risks, roadmap)
        assert next_step["type"] == "fix_issue"  # failed_check has highest priority
