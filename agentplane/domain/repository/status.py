from __future__ import annotations

import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentplane.domain.repository.docs_sanity import run_docs_sanity
from agentplane.domain.repository.privacy_scan import scan_repository_for_private_material
from agentplane.domain.repository.secret_scan import scan_repository_for_secrets
from agentplane.domain.repository.skills import check_skill_surface, list_skill_entries

LEDGER_FILES = {
    "containers": "containers.json",
    "ingress": "ingress.json",
    "apps": "apps.json",
    "app_resources": "app_resources.json",
    "automations": "automations.json",
    "cronjobs": "cronjobs.json",
    "firewall": "firewall.json",
}

WORKBOOK_PATH = "docs/maintainers/agentplane-roadmap-workbook.md"


def _read_json(path: Path) -> tuple[Any | None, str | None]:
    if not path.is_file():
        return None, "missing"
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except (OSError, json.JSONDecodeError) as exc:
        return None, str(exc)


def _count_items(payload: Any) -> int:
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict):
        if isinstance(payload.get("count"), int):
            return int(payload["count"])
        items = payload.get("items")
        if isinstance(items, list):
            return len(items)
        return len(payload)
    return 0


def _iso_mtime(path: Path) -> str | None:
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).replace(microsecond=0).isoformat()


def _repo_docs_status(repo_root: Path) -> dict[str, Any]:
    issues = run_docs_sanity(repo_root)
    errors = [issue for issue in issues if issue.severity == "error"]
    warnings = [issue for issue in issues if issue.severity == "warning"]
    return {
        "ok": not errors,
        "errors": len(errors),
        "warnings": len(warnings),
        "issues": [issue.to_dict() for issue in issues],
    }


def _repo_boundary_status(repo_root: Path) -> dict[str, Any]:
    secret_issues = scan_repository_for_secrets(repo_root)
    privacy_issues = scan_repository_for_private_material(repo_root)
    return {
        "ok": not secret_issues and not privacy_issues,
        "secret_issues": len(secret_issues),
        "privacy_issues": len(privacy_issues),
        "secrets": [issue.to_dict() for issue in secret_issues],
        "privacy": [issue.to_dict() for issue in privacy_issues],
    }


def _skills_status(repo_root: Path) -> dict[str, Any]:
    entries = list_skill_entries(repo_root)
    issues = check_skill_surface(repo_root)
    kind_counts: dict[str, int] = {}
    domain_counts: dict[str, int] = {}
    for entry in entries:
        kind = str(entry.get("kind", "unknown"))
        kind_counts[kind] = kind_counts.get(kind, 0) + 1
        for domain in entry.get("domains", []):
            domain_key = str(domain)
            domain_counts[domain_key] = domain_counts.get(domain_key, 0) + 1
    return {
        "ok": not issues,
        "count": len(entries),
        "kind_counts": dict(sorted(kind_counts.items())),
        "domain_counts": dict(sorted(domain_counts.items())),
        "issues": [issue.to_dict() for issue in issues],
    }


def _apps_status(repo_root: Path) -> dict[str, Any]:
    catalog_path = repo_root / "inventory" / "apps" / "catalog.json"
    payload, error = _read_json(catalog_path)
    apps = payload.get("apps") if isinstance(payload, dict) else None
    app_items = apps if isinstance(apps, list) else []
    return {
        "catalog_exists": catalog_path.is_file(),
        "ok": error is None and isinstance(apps, list),
        "count": len(app_items),
        "error": error,
        "updated_at": _iso_mtime(catalog_path),
    }


def _target_status(target_dir: Path) -> dict[str, Any]:
    inventory_file = target_dir / "inventory.json"
    readme_file = target_dir / "README.md"
    ledgers_dir = target_dir / "ledgers"
    inventory_payload, inventory_error = _read_json(inventory_file)
    ledger_counts: dict[str, int] = {}
    ledger_updated: dict[str, str | None] = {}
    ledger_errors: dict[str, str] = {}

    for name, filename in LEDGER_FILES.items():
        path = ledgers_dir / filename
        payload, error = _read_json(path)
        ledger_counts[name] = 0 if error else _count_items(payload)
        ledger_updated[name] = _iso_mtime(path)
        if error and error != "missing":
            ledger_errors[name] = error

    compose_services = inventory_payload.get("compose_services") if isinstance(inventory_payload, dict) else []
    docker_containers = inventory_payload.get("docker_containers") if isinstance(inventory_payload, dict) else []
    unmanaged_containers = inventory_payload.get("unmanaged_docker_containers") if isinstance(inventory_payload, dict) else []

    return {
        "target": target_dir.name,
        "inventory_exists": inventory_file.is_file(),
        "inventory_ok": inventory_error is None,
        "readme_exists": readme_file.is_file(),
        "ledgers_exists": ledgers_dir.is_dir(),
        "updated_at": _iso_mtime(inventory_file),
        "compose_services": len(compose_services) if isinstance(compose_services, list) else 0,
        "managed_containers": len(docker_containers) if isinstance(docker_containers, list) else 0,
        "unmanaged_containers": len(unmanaged_containers) if isinstance(unmanaged_containers, list) else 0,
        "ledger_counts": ledger_counts,
        "ledger_updated": ledger_updated,
        "ledger_errors": ledger_errors,
    }


def _targets_status(repo_root: Path) -> dict[str, Any]:
    root = repo_root / "inventory" / "servers"
    targets = [_target_status(path) for path in sorted(root.iterdir()) if path.is_dir()] if root.is_dir() else []
    return {
        "count": len(targets),
        "items": targets,
    }


def _recommendations(payload: dict[str, Any]) -> list[str]:
    recommendations: list[str] = []
    checks = payload["checks"]
    if not checks["docs"]["ok"]:
        recommendations.append("Fix docs-sanity errors before using the dashboard as a release signal.")
    if not checks["boundaries"]["ok"]:
        recommendations.append("Resolve secret or privacy scan issues before sharing status output.")
    if not checks["skills"]["ok"]:
        recommendations.append("Run `agentplane repo skills check` and fix public Skill catalog drift.")
    if payload["apps"]["count"] == 0:
        recommendations.append("No active app catalog entries are registered yet.")
    if payload["targets"]["count"] == 0:
        recommendations.append("No inventory targets are present under inventory/servers.")
    for target in payload["targets"]["items"]:
        if not target["inventory_exists"]:
            recommendations.append(f"{target['target']} is missing inventory.json.")
        if not target["readme_exists"]:
            recommendations.append(f"{target['target']} is missing a non-sensitive README summary.")
        if target["ledger_errors"]:
            recommendations.append(f"{target['target']} has invalid ledger JSON that should be refreshed.")
    if not recommendations:
        recommendations.append("No immediate repository status issues detected.")
    return recommendations


# ---------------------------------------------------------------------------
# Workbook (roadmap) parsing
# ---------------------------------------------------------------------------

_PHASE_STATUSES_DONE = {"done", "superseded"}
_TASK_STATUSES_DONE = {"done", "deferred"}

# Regex for markdown table rows: | col1 | col2 | ... |
_TABLE_ROW_RE = re.compile(r"^\|\s*(.+?)\s*\|(.*?)\|?$")
_BACKTICK_RE = re.compile(r"`([^`]+)`")


def _strip_backtick(s: str) -> str:
    """Remove surrounding backticks from a markdown table cell value."""
    return _BACKTICK_RE.sub(r"\1", s).strip()


def _parse_phase_overview(text: str) -> list[dict[str, str]]:
    """Parse the phase overview table from workbook markdown.

    Expected header: | 阶段 | 名称 | 状态 | 阶段门 | 验收口径 |
    Returns list of dicts with keys: id, name, status.
    """
    # Locate the phase overview section first
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
            phases.append({
                "id": _strip_backtick(first),
                "name": cells[1].strip(),
                "status": _strip_backtick(cells[2]),
            })
    return phases


def _parse_phase_section_tasks(text: str, phase_id: str) -> list[dict[str, str]]:
    """Parse all task tables within a phase section.

    A phase section may contain multiple task tables (e.g. "第一轮任务" and
    "第二轮任务"). This function collects tasks from all of them.

    Expected header: | ID | 任务 | 状态 | ... |
    Returns list of dicts with keys: id, title, status.
    """
    # Find the phase section boundaries
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
        # Detect task table by header containing "ID"
        if first == "ID":
            in_table = True
            continue
        if not in_table:
            continue
        if first.startswith("---"):
            continue
        if len(cells) >= 3:
            tasks.append({
                "id": _strip_backtick(first),
                "title": cells[1].strip(),
                "status": _strip_backtick(cells[2]),
            })
    return tasks


def _parse_resume_entry(text: str) -> str | None:
    """Extract the '当前继续入口' section content."""
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
    """Extract last_verified from workbook frontmatter."""
    match = re.search(r"^last_verified:\s*(.+)$", text, re.MULTILINE)
    return match.group(1).strip() if match else None


def _find_current_phase(phases: list[dict[str, str]]) -> dict[str, str] | None:
    """Find the first phase whose status is not done or superseded."""
    for phase in phases:
        if phase["status"] not in _PHASE_STATUSES_DONE:
            return phase
    return None


def _find_next_task(tasks: list[dict[str, str]]) -> dict[str, str] | None:
    """Find the first task whose status is not done or deferred."""
    for task in tasks:
        if task["status"] not in _TASK_STATUSES_DONE:
            return task
    return None


def _workbook_status(repo_root: Path) -> dict[str, Any]:
    """Parse the roadmap workbook and return roadmap projection fields.

    If the workbook file is missing or cannot be parsed, returns ok=false
    with an error message instead of fabricating status.
    """
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

    # Determine gate status from phase status
    gate = "confirmed" if current_phase["status"] in ("approved", "active") else "pending"

    # Parse tasks for the current phase
    tasks = _parse_phase_section_tasks(text, current_phase["id"])
    next_task = _find_next_task(tasks)

    # If current phase is planned/discussion-required, next_task should be null
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


# ---------------------------------------------------------------------------
# Risk and next-step derivation
# ---------------------------------------------------------------------------

_STALE_THRESHOLD_DAYS = 30


def _derive_risks(
    roadmap: dict[str, Any],
    checks: dict[str, Any],
    targets: dict[str, Any],
) -> list[dict[str, str]]:
    """Derive risks from workbook, repo status checks, and target data."""
    risks: list[dict[str, str]] = []

    # blocked_phase
    current_phase = roadmap.get("current_phase")
    if current_phase and current_phase["status"] == "blocked":
        risks.append({
            "kind": "blocked_phase",
            "severity": "high",
            "message": f"{current_phase['id']} ({current_phase['name']}) is blocked.",
            "source_ref": current_phase["id"],
        })

    # discussion_required (only for current phase)
    if current_phase and current_phase["status"] in ("planned", "discussion-required"):
        risks.append({
            "kind": "discussion_required",
            "severity": "high",
            "message": f"{current_phase['id']} ({current_phase['name']}) requires discussion before proceeding.",
            "source_ref": current_phase["id"],
        })

    # failed_check
    failed_checks: list[str] = []
    for area, data in checks.items():
        if not data.get("ok", True):
            failed_checks.append(area)
    if failed_checks:
        risks.append({
            "kind": "failed_check",
            "severity": "high",
            "message": f"Checks failed: {', '.join(failed_checks)}.",
            "source_ref": ", ".join(failed_checks),
        })

    # blocked_task (from workbook tasks)
    if roadmap.get("ok") and current_phase and current_phase["status"] in ("approved", "active"):
        next_task = roadmap.get("next_task")
        if next_task and next_task["status"] == "blocked":
            risks.append({
                "kind": "blocked_task",
                "severity": "medium",
                "message": f"Task {next_task['id']} is blocked.",
                "source_ref": next_task["id"],
            })

    # missing_inventory
    missing: list[str] = []
    for target in targets.get("items", []):
        if not target.get("inventory_exists"):
            missing.append(target["target"])
        elif not target.get("readme_exists"):
            missing.append(target["target"])
    if missing:
        risks.append({
            "kind": "missing_inventory",
            "severity": "medium",
            "message": f"Targets missing inventory or README: {', '.join(missing)}.",
            "source_ref": ", ".join(missing),
        })

    # stale_data
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
                    break  # One stale ledger per target is enough
            except (ValueError, TypeError):
                pass
    if stale:
        risks.append({
            "kind": "stale_data",
            "severity": "low",
            "message": f"Stale ledgers (> {_STALE_THRESHOLD_DAYS} days): {', '.join(stale)}.",
            "source_ref": ", ".join(stale),
        })

    return risks


def _check_dirty_worktree(repo_root: Path) -> bool:
    """Check if the git working tree has uncommitted changes."""
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
    """Derive the recommended next action based on risks and roadmap state."""
    risk_kinds = {r["kind"] for r in risks}

    # Priority 1: fix_issue
    if "failed_check" in risk_kinds:
        source = next(r["source_ref"] for r in risks if r["kind"] == "failed_check")
        return {
            "type": "fix_issue",
            "description": "Fix failing checks before continuing.",
            "target_ref": source,
        }

    # Priority 2: commit_changes
    if "dirty_worktree" in risk_kinds:
        return {
            "type": "commit_changes",
            "description": "Commit or handle uncommitted changes in the working tree.",
            "target_ref": "git",
        }

    # Priority 3: discuss_gate
    current_phase = roadmap.get("current_phase")
    if current_phase and current_phase["status"] in ("planned", "discussion-required"):
        return {
            "type": "discuss_gate",
            "description": f"{current_phase['id']} phase gate needs discussion: confirm direction, technology, and scope.",
            "target_ref": current_phase["id"],
        }

    # Priority 4: continue_task
    next_task = roadmap.get("next_task")
    if next_task and next_task["status"] in ("todo", "in-progress"):
        return {
            "type": "continue_task",
            "description": f"Execute {next_task['id']}: {next_task['title']}.",
            "target_ref": next_task["id"],
        }

    # Priority 5: all_done
    if roadmap.get("ok") and roadmap.get("current_phase") is None:
        return {
            "type": "all_done",
            "description": "All roadmap phases are complete. Consider adding new phases or closing the roadmap.",
            "target_ref": "roadmap",
        }

    # Default: no specific recommendation
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

    # Derive risks and next step
    risks = _derive_risks(payload["roadmap"], payload["checks"], payload["targets"])
    if _check_dirty_worktree(root):
        risks.append({
            "kind": "dirty_worktree",
            "severity": "medium",
            "message": "Uncommitted changes in the working tree.",
            "source_ref": "git",
        })
    # Sort risks by severity (high > medium > low)
    severity_order = {"high": 0, "medium": 1, "low": 2}
    risks.sort(key=lambda r: severity_order.get(r["severity"], 3))
    payload["risks"] = risks
    payload["next_step"] = _derive_next_step(risks, payload["roadmap"])

    return payload


def _card(title: str, value: object, note: str = "") -> str:
    return (
        '<section class="card">'
        f"<span>{html.escape(title)}</span>"
        f"<strong>{html.escape(str(value))}</strong>"
        f"<small>{html.escape(note)}</small>"
        "</section>"
    )


def _target_rows(targets: list[dict[str, Any]]) -> str:
    rows: list[str] = []
    for target in targets:
        ledgers = target["ledger_counts"]
        rows.append(
            "<tr>"
            f"<td>{html.escape(target['target'])}</td>"
            f"<td>{'yes' if target['inventory_ok'] else 'no'}</td>"
            f"<td>{target['compose_services']}</td>"
            f"<td>{target['managed_containers']}</td>"
            f"<td>{ledgers.get('ingress', 0)}</td>"
            f"<td>{ledgers.get('automations', 0)}</td>"
            f"<td>{html.escape(str(target.get('updated_at') or 'n/a'))}</td>"
            "</tr>"
        )
    return "\n".join(rows) or '<tr><td colspan="7">No targets found</td></tr>'


def render_status_html(payload: dict[str, Any]) -> str:
    checks = payload["checks"]
    summary = payload["summary"]
    recommendations = "\n".join(f"<li>{html.escape(item)}</li>" for item in payload["recommendations"])
    target_rows = _target_rows(payload["targets"]["items"])
    skills = checks["skills"]
    skill_domains = ", ".join(f"{key}: {value}" for key, value in skills["domain_counts"].items()) or "none"
    status_class = "ok" if payload["ok"] else "warn"
    status_text = "Healthy" if payload["ok"] else "Needs attention"

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AgentPlane Status</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #17202a;
      --muted: #667085;
      --line: #d7dde5;
      --surface: #f6f8fb;
      --ok: #0f766e;
      --warn: #b45309;
      --panel: #ffffff;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: Inter, Segoe UI, Arial, sans-serif; color: var(--ink); background: var(--surface); }}
    header {{ padding: 28px 32px; background: #102a43; color: white; }}
    header h1 {{ margin: 0 0 8px; font-size: 28px; letter-spacing: 0; }}
    header p {{ margin: 0; color: #d9e2ec; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 24px; }}
    .status {{ display: inline-flex; align-items: center; gap: 8px; margin-top: 18px; padding: 6px 10px; border-radius: 6px; background: rgba(255,255,255,.12); }}
    .dot {{ width: 10px; height: 10px; border-radius: 50%; background: var(--ok); }}
    .status.warn .dot {{ background: var(--warn); }}
    .grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; margin: 20px 0; }}
    .card, .panel {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; }}
    .card {{ padding: 16px; }}
    .card span {{ display: block; color: var(--muted); font-size: 13px; }}
    .card strong {{ display: block; margin-top: 8px; font-size: 30px; }}
    .card small {{ display: block; margin-top: 8px; color: var(--muted); }}
    .panel {{ padding: 18px; margin: 16px 0; }}
    .panel h2 {{ margin: 0 0 14px; font-size: 18px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ padding: 10px; border-top: 1px solid var(--line); text-align: left; font-size: 14px; }}
    th {{ color: var(--muted); font-weight: 600; }}
    ul {{ margin: 0; padding-left: 20px; }}
    li {{ margin: 8px 0; }}
    code {{ background: #eef2f6; padding: 2px 5px; border-radius: 4px; }}
    @media (max-width: 780px) {{ .grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} main {{ padding: 16px; }} }}
  </style>
</head>
<body>
  <header>
    <h1>AgentPlane Status</h1>
    <p>Static control-plane summary generated from local repository state.</p>
    <div class="status {status_class}"><span class="dot"></span><span>{html.escape(status_text)}</span></div>
  </header>
  <main>
    <div class="grid">
      {_card("Repo Checks", "OK" if summary["repo_checks_ok"] else "Review", "docs, boundaries, skills")}
      {_card("Public Skills", summary["public_skills"], skill_domains)}
      {_card("Targets", summary["targets"], "inventory/servers")}
      {_card("Apps", summary["apps"], "inventory/apps/catalog.json")}
    </div>
    <section class="panel">
      <h2>Checks</h2>
      <table>
        <thead><tr><th>Area</th><th>Status</th><th>Details</th></tr></thead>
        <tbody>
          <tr><td>Docs</td><td>{'ok' if checks['docs']['ok'] else 'review'}</td><td>{checks['docs']['errors']} errors, {checks['docs']['warnings']} warnings</td></tr>
          <tr><td>Secrets & Privacy</td><td>{'ok' if checks['boundaries']['ok'] else 'review'}</td><td>{checks['boundaries']['secret_issues']} secret issues, {checks['boundaries']['privacy_issues']} privacy issues</td></tr>
          <tr><td>Skills</td><td>{'ok' if checks['skills']['ok'] else 'review'}</td><td>{checks['skills']['count']} public skills</td></tr>
        </tbody>
      </table>
    </section>
    <section class="panel">
      <h2>Targets</h2>
      <table>
        <thead><tr><th>Target</th><th>Inventory</th><th>Compose</th><th>Containers</th><th>Ingress</th><th>Automations</th><th>Updated</th></tr></thead>
        <tbody>
          {target_rows}
        </tbody>
      </table>
    </section>
    <section class="panel">
      <h2>Next Actions</h2>
      <ul>{recommendations}</ul>
    </section>
    <section class="panel">
      <h2>Source</h2>
      <p>Generated at <code>{html.escape(payload['generated_at'])}</code> from <code>{html.escape(payload['repo_root'])}</code>.</p>
    </section>
  </main>
</body>
</html>
"""


def write_status_html(payload: dict[str, Any], output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_status_html(payload), encoding="utf-8")
    return output
