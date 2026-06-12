from __future__ import annotations

import html
from pathlib import Path
from typing import Any


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


def _render_roadmap_section(roadmap: dict[str, Any]) -> str:
    if not roadmap.get("ok"):
        error_msg = html.escape(roadmap.get("error", "Unknown error"))
        return (
            '<section class="panel">'
            "<h2>Roadmap</h2>"
            f'<p style="color:var(--muted)">Roadmap unavailable: {error_msg}</p>'
            "</section>"
        )

    current_phase = roadmap.get("current_phase")
    if current_phase is None:
        return '<section class="panel"><h2>Roadmap</h2><p style="color:var(--ok)">All phases complete.</p></section>'

    phase_status = current_phase["status"]
    next_task = roadmap.get("next_task")
    source = roadmap.get("source", {})

    next_task_html = ""
    if next_task:
        next_task_html = (
            f"<tr><td>Next Task</td>"
            f"<td><code>{html.escape(next_task['id'])}</code> {html.escape(next_task['title'])}</td>"
            f'<td><span class="badge {html.escape(next_task["status"])}">{html.escape(next_task["status"])}</span></td></tr>'
        )

    return (
        '<section class="panel">'
        "<h2>Roadmap</h2>"
        "<table>"
        "<thead><tr><th>Field</th><th>Value</th><th>Status</th></tr></thead>"
        "<tbody>"
        f"<tr><td>Current Phase</td>"
        f"<td><strong>{html.escape(current_phase['id'])}</strong> {html.escape(current_phase['name'])}</td>"
        f'<td><span class="badge {html.escape(phase_status)}">{html.escape(phase_status)}</span></td></tr>'
        f'<tr><td>Gate</td><td colspan="2">{html.escape(current_phase["gate"])}</td></tr>'
        f"{next_task_html}"
        f'<tr><td>Source</td><td colspan="2"><code>{html.escape(source.get("path", ""))}</code> (verified {html.escape(source.get("last_verified", "n/a"))})</td></tr>'
        "</tbody>"
        "</table>"
        "</section>"
    )


def _render_risks_section(risks: list[dict[str, str]]) -> str:
    if not risks:
        return '<section class="panel"><h2>Risks</h2><p style="color:var(--ok)">No risks detected.</p></section>'

    rows: list[str] = []
    for risk in risks:
        rows.append(
            f"<tr>"
            f'<td><span class="badge {html.escape(risk["severity"])}">{html.escape(risk["severity"])}</span></td>'
            f"<td>{html.escape(risk['kind'])}</td>"
            f"<td>{html.escape(risk['message'])}</td>"
            f"<td><code>{html.escape(risk['source_ref'])}</code></td>"
            f"</tr>"
        )

    return (
        '<section class="panel">'
        "<h2>Risks</h2>"
        "<table>"
        "<thead><tr><th>Severity</th><th>Type</th><th>Message</th><th>Source</th></tr></thead>"
        "<tbody>" + "\n".join(rows) + "</tbody>"
        "</table>"
        "</section>"
    )


def _render_next_step_section(next_step: dict[str, str]) -> str:
    if not next_step:
        return ""

    step_type = html.escape(next_step.get("type", ""))
    description = html.escape(next_step.get("description", ""))
    target_ref = html.escape(next_step.get("target_ref", ""))

    return (
        '<div class="next-step">'
        f"<h2>Next Step: {step_type}</h2>"
        f"<p>{description}</p>"
        f"<p><small>Ref: <code>{target_ref}</code></small></p>"
        "</div>"
    )


def render_status_html(payload: dict[str, Any]) -> str:
    checks = payload["checks"]
    summary = payload["summary"]
    recommendations = "\n".join(f"<li>{html.escape(item)}</li>" for item in payload["recommendations"])
    target_rows = _target_rows(payload["targets"]["items"])
    skills = checks["skills"]
    skill_domains = ", ".join(f"{key}: {value}" for key, value in skills["domain_counts"].items()) or "none"
    status_class = "ok" if payload["ok"] else "warn"
    status_text = "Healthy" if payload["ok"] else "Needs attention"

    roadmap = payload.get("roadmap", {})
    roadmap_html = _render_roadmap_section(roadmap)

    risks = payload.get("risks", [])
    risks_html = _render_risks_section(risks)

    next_step = payload.get("next_step", {})
    next_step_html = _render_next_step_section(next_step)

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
      --high: #dc2626;
      --medium: #d97706;
      --low: #6b7280;
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
    .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; color: white; }}
    .badge.high {{ background: var(--high); }}
    .badge.medium {{ background: var(--medium); }}
    .badge.low {{ background: var(--low); }}
    .badge.active {{ background: var(--ok); }}
    .badge.planned {{ background: #6366f1; }}
    .badge.blocked {{ background: var(--high); }}
    .next-step {{ padding: 14px 18px; background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; margin: 16px 0; }}
    .next-step h2 {{ margin: 0 0 8px; font-size: 16px; color: var(--ok); }}
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
          <tr><td>Docs</td><td>{"ok" if checks["docs"]["ok"] else "review"}</td><td>{checks["docs"]["errors"]} errors, {checks["docs"]["warnings"]} warnings</td></tr>
          <tr><td>Secrets & Privacy</td><td>{"ok" if checks["boundaries"]["ok"] else "review"}</td><td>{checks["boundaries"]["secret_issues"]} secret issues, {checks["boundaries"]["privacy_issues"]} privacy issues</td></tr>
          <tr><td>Skills</td><td>{"ok" if checks["skills"]["ok"] else "review"}</td><td>{checks["skills"]["count"]} public skills</td></tr>
        </tbody>
      </table>
    </section>
    {roadmap_html}
    {risks_html}
    {next_step_html}
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
      <p>Generated at <code>{html.escape(payload["generated_at"])}</code> from <code>{html.escape(payload["repo_root"])}</code>.</p>
    </section>
  </main>
</body>
</html>
"""


def write_status_html(payload: dict[str, Any], output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_status_html(payload), encoding="utf-8")
    return output
