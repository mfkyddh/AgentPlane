"""Unit tests for roadmap workbook parsing.

Tests _parse_phase_overview(), _parse_phase_section_tasks(),
_parse_resume_entry(), _parse_workbook_last_verified(), and
_workbook_status() against synthetic workbook Markdown.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from agentplane.domain.project.status_workbook import (
    _parse_phase_overview,
    _parse_phase_section_tasks,
    _parse_resume_entry,
    _parse_workbook_last_verified,
    _workbook_status,
)

pytestmark = pytest.mark.unit

# -- Sample data -------------------------------------------------------------

SAMPLE_WORKBOOK = """\
---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-29
superseded_by: null
audience: agent
---

# AgentPlane Roadmap Workbook

## 🗺️ 阶段总览

| 阶段 | 名称 | 状态 | 阶段门 | 验收口径 |
| --- | --- | --- | --- | --- |
| P0 | Alpha | `done` | confirmed | Alpha done |
| P1 | Beta | `active` | confirmed | Beta in progress |
| P2 | Gamma | `planned` | pending | Gamma planned |

## P0 Alpha

### 任务

| ID | 任务 | 状态 | 完成日期 | 验证或证据 | 后续影响 |
| --- | --- | --- | --- | --- | --- |
| P0-T1 | First task | `done` | 2026-04-29 | Evidence | Next |
| P0-T2 | Second task | `done` | 2026-04-29 | Evidence | Next |

## P1 Beta

### 第一轮任务

| ID | 任务 | 状态 | 完成日期 | 验证或证据 | 后续影响 |
| --- | --- | --- | --- | --- | --- |
| P1-T1 | Design model | `done` | 2026-04-29 | Done | Next |

### 第二轮任务

| ID | 任务 | 状态 | 完成日期 | 验证或证据 | 后续影响 |
| --- | --- | --- | --- | --- | --- |
| P1-T2 | Implement code | `todo` | | | Write code |
| P1-T3 | Write tests | `in-progress` | | | In progress |

## P2 Gamma

| ID | 候选任务 | 状态 |
| --- | --- | --- |
| P2-T1 | Define threat model | `todo` |

## ✅ 当前继续入口

当前阶段：P1 Beta。下一步：执行 P1-T2。
"""

ALL_DONE_WORKBOOK = """\
---
status: active
last_verified: 2026-04-20
---

# AgentPlane Roadmap Workbook

## 🗺️ 阶段总览

| 阶段 | 名称 | 状态 | 阶段门 | 验收口径 |
| --- | --- | --- | --- | --- |
| P0 | Alpha | `done` | confirmed | Done |
| P1 | Beta | `superseded` | n/a | Superseded |

## ✅ 当前继续入口

当前路线已完成。
"""

BLOCKED_WORKBOOK = """\
---
status: active
last_verified: 2026-04-20
---

# AgentPlane Roadmap Workbook

## 🗺️ 阶段总览

| 阶段 | 名称 | 状态 | 阶段门 | 验收口径 |
| --- | --- | --- | --- | --- |
| P0 | Alpha | `done` | confirmed | Done |
| P1 | Beta | `blocked` | blocked | Waiting |

## P1 Beta

| ID | 任务 | 状态 |
| --- | --- | --- |
| P1-T1 | Stuck task | `blocked` |

## ✅ 当前继续入口

P1 阶段阻塞。
"""


def _write_workbook(content: str, root: Path | None = None) -> Path:
    """Write *content* to a temp workbook and return the repo root."""
    if root is None:
        root = Path(tempfile.mkdtemp())
    wb_dir = root / "docs" / "maintainers"
    wb_dir.mkdir(parents=True)
    (wb_dir / "agentplane-roadmap-workbook.md").write_text(content, encoding="utf-8")
    return root


# -- _parse_phase_overview ---------------------------------------------------


class TestParsePhaseOverview:
    def test_extracts_phases_from_overview_table(self) -> None:
        phases = _parse_phase_overview(SAMPLE_WORKBOOK)
        assert len(phases) == 3
        assert phases[0] == {"id": "P0", "name": "Alpha", "status": "done"}
        assert phases[1] == {"id": "P1", "name": "Beta", "status": "active"}
        assert phases[2] == {"id": "P2", "name": "Gamma", "status": "planned"}

    def test_returns_empty_when_no_overview_section(self) -> None:
        assert _parse_phase_overview("# No overview here\n") == []

    def test_handles_all_done_phases(self) -> None:
        phases = _parse_phase_overview(ALL_DONE_WORKBOOK)
        assert len(phases) == 2
        assert phases[0]["status"] == "done"
        assert phases[1]["status"] == "superseded"


# -- _parse_phase_section_tasks ----------------------------------------------


class TestParsePhaseSectionTasks:
    def test_collects_tasks_from_multiple_tables(self) -> None:
        tasks = _parse_phase_section_tasks(SAMPLE_WORKBOOK, "P1")
        assert len(tasks) == 3
        assert tasks[0]["id"] == "P1-T1" and tasks[0]["status"] == "done"
        assert tasks[1]["id"] == "P1-T2" and tasks[1]["status"] == "todo"
        assert tasks[2]["id"] == "P1-T3" and tasks[2]["status"] == "in-progress"

    def test_returns_empty_for_unknown_phase(self) -> None:
        assert _parse_phase_section_tasks(SAMPLE_WORKBOOK, "P99") == []

    def test_parses_tasks_with_backtick_status(self) -> None:
        tasks = _parse_phase_section_tasks(SAMPLE_WORKBOOK, "P0")
        assert len(tasks) == 2
        assert tasks[0]["status"] == "done"


# -- _parse_resume_entry -----------------------------------------------------


class TestParseResumeEntry:
    def test_extracts_resume_entry_content(self) -> None:
        entry = _parse_resume_entry(SAMPLE_WORKBOOK)
        assert entry is not None
        assert "P1 Beta" in entry
        assert "P1-T2" in entry

    def test_returns_none_when_no_resume_section(self) -> None:
        assert _parse_resume_entry("# No resume section\n") is None


# -- _parse_workbook_last_verified -------------------------------------------


class TestParseWorkbookLastVerified:
    def test_extracts_last_verified_from_frontmatter(self) -> None:
        assert _parse_workbook_last_verified(SAMPLE_WORKBOOK) == "2026-04-29"

    def test_returns_none_when_no_frontmatter(self) -> None:
        assert _parse_workbook_last_verified("# No frontmatter\n") is None


# -- _workbook_status (integration) ------------------------------------------


class TestWorkbookStatus:
    def test_returns_ok_with_current_phase_and_next_task(self, tmp_path: Path) -> None:
        result = _workbook_status(_write_workbook(SAMPLE_WORKBOOK, tmp_path))
        assert result["ok"] is True
        assert result["current_phase"]["id"] == "P1"
        assert result["current_phase"]["name"] == "Beta"
        assert result["current_phase"]["status"] == "active"
        assert result["current_phase"]["gate"] == "confirmed"
        assert result["next_task"]["id"] == "P1-T2"
        assert result["next_task"]["status"] == "todo"
        assert result["resume_entry"] is not None
        assert result["source"]["path"] == "docs/maintainers/agentplane-roadmap-workbook.md"
        assert result["source"]["last_verified"] == "2026-04-29"

    def test_returns_null_next_task_for_planned_phase(self, tmp_path: Path) -> None:
        planned_wb = """\
---
status: active
last_verified: 2026-04-29
---

# Workbook

## 🗺️ 阶段总览

| 阶段 | 名称 | 状态 | 阶段门 | 验收口径 |
| --- | --- | --- | --- | --- |
| P0 | Done | `done` | confirmed | Done |
| P1 | Planned | `planned` | pending | Not started |

## P1 Planned

| ID | 任务 | 状态 |
| --- | --- | --- |
| P1-T1 | Task | `todo` |

## ✅ 当前继续入口

P1 待讨论。
"""
        result = _workbook_status(_write_workbook(planned_wb, tmp_path))
        assert result["ok"] is True
        assert result["current_phase"]["status"] == "planned"
        assert result["current_phase"]["gate"] == "pending"
        assert result["next_task"] is None

    def test_returns_null_current_phase_when_all_done(self, tmp_path: Path) -> None:
        result = _workbook_status(_write_workbook(ALL_DONE_WORKBOOK, tmp_path))
        assert result["ok"] is True
        assert result["current_phase"] is None
        assert result["next_task"] is None

    def test_returns_error_when_workbook_missing(self, tmp_path: Path) -> None:
        result = _workbook_status(tmp_path)
        assert result["ok"] is False
        assert "not found" in result["error"].lower()

    def test_returns_error_when_no_phase_table(self, tmp_path: Path) -> None:
        result = _workbook_status(_write_workbook("---\nstatus: active\n---\n\n# No phases here\n", tmp_path))
        assert result["ok"] is False
        assert "no phase overview" in result["error"].lower()

    def test_blocked_phase_shows_gate_pending(self, tmp_path: Path) -> None:
        result = _workbook_status(_write_workbook(BLOCKED_WORKBOOK, tmp_path))
        assert result["ok"] is True
        assert result["current_phase"]["status"] == "blocked"
        assert result["current_phase"]["gate"] == "pending"
        assert result["next_task"]["status"] == "blocked"
