from __future__ import annotations

import html
import json
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
