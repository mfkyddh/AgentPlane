from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from agentplane.domain.project.status_checks import WORKBOOK_PATH

_PHASE_STATUSES_DONE = {"done", "superseded"}
_TASK_STATUSES_DONE = {"done", "deferred"}

_TABLE_ROW_RE = re.compile(r"^\|\s*(.+?)\s*\|(.*?)\|?$")
_BACKTICK_RE = re.compile(r"`([^`]+)`")


def _strip_backtick(s: str) -> str:
    return _BACKTICK_RE.sub(r"\1", s).strip()


def _parse_phase_overview(text: str) -> list[dict[str, str]]:
    section_lines: list[str] = []
    in_section = False
    for line in text.splitlines():
        stripped = line.strip()
        if "阶段总览" in stripped and stripped.startswith("##"):
            in_section = True
            continue
        if in_section and stripped.startswith("## ") and "阶段总览" not in stripped:
            break
        if in_section:
            section_lines.append(line)

    phases: list[dict[str, str]] = []
    in_table = False
    for line in section_lines:
        line = line.strip()
        if not line.startswith("|"):
            if in_table:
                break
            continue
        cells = [c.strip() for c in line.split("|")[1:-1]]
        if not cells:
            continue
        first = cells[0].strip()
        if first in ("阶段", "---", ":---"):
            in_table = True
            continue
        if not in_table:
            continue
        if first.startswith("---"):
            continue
        if len(cells) >= 3:
            phases.append(
                {
                    "id": _strip_backtick(first),
                    "name": cells[1].strip(),
                    "status": _strip_backtick(cells[2]),
                }
            )
    return phases


def _parse_phase_section_tasks(text: str, phase_id: str) -> list[dict[str, str]]:
    section_start = None
    section_end = None
    for i, line in enumerate(text.splitlines()):
        stripped = line.strip()
        if stripped.startswith("## "):
            section_id = stripped[3:].split()[0] if stripped[3:].split() else ""
            if section_id == phase_id:
                section_start = i
                continue
            if section_start is not None:
                section_end = i
                break

    if section_start is None:
        return []

    section_text = "\n".join(text.splitlines()[section_start:section_end])

    tasks: list[dict[str, str]] = []
    in_table = False
    for line in section_text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            in_table = False
            continue
        cells = [c.strip() for c in line.split("|")[1:-1]]
        if not cells:
            continue
        first = cells[0].strip()
        if first == "ID":
            in_table = True
            continue
        if not in_table:
            continue
        if first.startswith("---"):
            continue
        if len(cells) >= 3:
            tasks.append(
                {
                    "id": _strip_backtick(first),
                    "title": cells[1].strip(),
                    "status": _strip_backtick(cells[2]),
                }
            )
    return tasks


def _parse_resume_entry(text: str) -> str | None:
    in_section = False
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## ✅ 当前继续入口") or stripped.startswith("## 当前继续入口"):
            in_section = True
            continue
        if in_section and stripped.startswith("## ") and "继续入口" not in stripped:
            break
        if in_section:
            lines.append(line)
    return "\n".join(lines).strip() if lines else None


def _parse_workbook_last_verified(text: str) -> str | None:
    match = re.search(r"^last_verified:\s*(.+)$", text, re.MULTILINE)
    return match.group(1).strip() if match else None


def _find_current_phase(phases: list[dict[str, str]]) -> dict[str, str] | None:
    for phase in phases:
        if phase["status"] not in _PHASE_STATUSES_DONE:
            return phase
    return None


def _find_next_task(tasks: list[dict[str, str]]) -> dict[str, str] | None:
    for task in tasks:
        if task["status"] not in _TASK_STATUSES_DONE:
            return task
    return None


def _workbook_status(repo_root: Path) -> dict[str, Any]:
    workbook_path = repo_root / WORKBOOK_PATH
    if not workbook_path.is_file():
        return {"ok": False, "error": f"Workbook not found: {WORKBOOK_PATH}"}

    try:
        text = workbook_path.read_text(encoding="utf-8")
    except OSError as exc:
        return {"ok": False, "error": f"Cannot read workbook: {exc}"}

    last_verified = _parse_workbook_last_verified(text)
    phases = _parse_phase_overview(text)
    if not phases:
        return {"ok": False, "error": "No phase overview table found in workbook"}

    current_phase = _find_current_phase(phases)

    if current_phase is None:
        return {
            "ok": True,
            "current_phase": None,
            "next_task": None,
            "resume_entry": _parse_resume_entry(text),
            "source": {
                "path": WORKBOOK_PATH,
                "last_verified": last_verified,
            },
        }

    gate = "confirmed" if current_phase["status"] in ("approved", "active") else "pending"

    tasks = _parse_phase_section_tasks(text, current_phase["id"])
    next_task = _find_next_task(tasks)

    if current_phase["status"] in ("planned", "discussion-required"):
        next_task_payload = None
    elif next_task:
        next_task_payload = {
            "id": next_task["id"],
            "title": next_task["title"],
            "status": next_task["status"],
        }
    else:
        next_task_payload = None

    return {
        "ok": True,
        "current_phase": {
            "id": current_phase["id"],
            "name": current_phase["name"],
            "status": current_phase["status"],
            "gate": gate,
        },
        "next_task": next_task_payload,
        "resume_entry": _parse_resume_entry(text),
        "source": {
            "path": WORKBOOK_PATH,
            "last_verified": last_verified,
        },
    }
