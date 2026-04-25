from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml

CATALOG_RELATIVE_PATH = Path(".codex/skills/catalog.yaml")
AGENTS_SKILLS_ROOT = Path(".agents/skills")
PLUGIN_SKILLS_ROOT = Path("plugins/agentplane-control-plane/skills")


def _load_catalog(repo_root: Path) -> dict[str, Any]:
    catalog_path = repo_root / CATALOG_RELATIVE_PATH
    payload = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("skill catalog must be a mapping")
    if payload.get("version") != 1:
        raise ValueError("skill catalog version must be 1")
    if not isinstance(payload.get("skills"), list):
        raise ValueError("skill catalog skills must be a list")
    if not isinstance(payload.get("plugin_groups"), dict):
        raise ValueError("skill catalog plugin_groups must be a mapping")
    return payload


def _validate_catalog(repo_root: Path, payload: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    skills: dict[str, dict[str, Any]] = {}
    for entry in payload["skills"]:
        if entry["name"] in skills:
            raise ValueError(f"duplicate skill entry: {entry['name']}")
        source_path = repo_root / entry["source_path"]
        if not source_path.is_file():
            raise ValueError(f"missing source skill file: {source_path}")
        skills[entry["name"]] = entry

    plugin_groups: dict[str, dict[str, Any]] = {}
    assigned_skills: set[str] = set()
    for group_name, group in payload["plugin_groups"].items():
        if group_name in plugin_groups:
            raise ValueError(f"duplicate plugin group: {group_name}")
        source_skills = group.get("source_skills", [])
        if not source_skills:
            raise ValueError(f"plugin group {group_name} must declare source_skills")
        unknown = [name for name in source_skills if name not in skills]
        if unknown:
            raise ValueError(f"plugin group {group_name} references unknown skills: {', '.join(unknown)}")
        overlap = assigned_skills.intersection(source_skills)
        if overlap:
            raise ValueError(f"skills assigned to multiple plugin groups: {', '.join(sorted(overlap))}")
        assigned_skills.update(source_skills)
        expected_domains = sorted({domain for name in source_skills for domain in skills[name]["domains"]})
        if sorted(group.get("domains", [])) != expected_domains:
            raise ValueError(
                f"plugin group {group_name} domains {group.get('domains', [])!r} do not match source skill domains {expected_domains!r}"
            )
        plugin_groups[group_name] = group

    existing_group_dirs = {path.name for path in (repo_root / PLUGIN_SKILLS_ROOT).iterdir() if path.is_dir()}
    expected_group_dirs = set(plugin_groups)
    unexpected = sorted(existing_group_dirs - expected_group_dirs)
    if unexpected:
        raise ValueError(f"unexpected plugin group directories: {', '.join(unexpected)}")
    for group_name in expected_group_dirs:
        group_dir = repo_root / PLUGIN_SKILLS_ROOT / group_name
        extra_group_items = sorted(path.name for path in group_dir.iterdir() if path.name != "SKILL.md")
        if extra_group_items:
            raise ValueError(f"unexpected files in plugin group {group_name}: {', '.join(extra_group_items)}")

    return skills, plugin_groups


def _write_text(path: Path, text: str) -> bool:
    existing = path.read_text(encoding="utf-8") if path.exists() else None
    if existing == text:
        return False
    path.write_text(text, encoding="utf-8")
    return True


def _plugin_skill_name(group_name: str) -> str:
    return f"agentplane-control-plane-{group_name}"


def _plugin_title(group_name: str) -> str:
    return group_name.replace("-", " ").title()


def _plugin_description(group_name: str) -> str:
    return f"Generated plugin skill group for {group_name}; routes to AgentPlane CLI-first commands."


def _plugin_entrypoint(group_name: str) -> str:
    if group_name == "ingress":
        return "uv run python -m agentplane.cli ingress ..."
    if group_name == "containers":
        return "uv run python -m agentplane.cli service ..."
    if group_name == "apps":
        return "uv run python -m agentplane.cli app ..."
    if group_name == "infra":
        return "uv run python -m agentplane.cli infra ..."
    if group_name == "ledgers":
        return "uv run python -m agentplane.cli projection ..."
    if group_name in {"cronjobs", "firewall"}:
        return "uv run python -m agentplane.cli onepanel --env <target> ... --json"
    return "uv run python -m agentplane.cli ..."


def sync_agents_skill_pointers(repo_root: Path, skills: dict[str, dict[str, Any]]) -> list[str]:
    changed: list[str] = []
    for name, entry in sorted(skills.items()):
        if "agents_pointer" not in entry.get("projection_targets", []):
            continue
        pointer_path = repo_root / AGENTS_SKILLS_ROOT / name
        text = f"../../.codex/skills/{name}\n"
        if _write_text(pointer_path, text):
            changed.append(str(pointer_path.relative_to(repo_root)))
    return changed


def _render_plugin_skill(group: dict[str, Any]) -> str:
    group_name = group["name"]
    lines = [
        "---",
        f"name: {_plugin_skill_name(group_name)}",
        f"description: {_plugin_description(group_name)}",
        f"generated_from: {CATALOG_RELATIVE_PATH.as_posix()}",
        f"group: {group_name}",
        "domains:",
        *[f"  - {name}" for name in group["domains"]],
        "source_skills:",
        *[f"  - {name}" for name in group["source_skills"]],
        "---",
        "",
        f"# {_plugin_title(group_name)}",
        "",
        "Generated from `.codex/skills/catalog.yaml`.",
        "",
        "This plugin group is a thin distribution layer over the repository-owned skills and CLI.",
        "",
        f"- Source repo skills: {', '.join(f'`{name}`' for name in group['source_skills'])}",
        f"- Primary domains: {', '.join(f'`{name}`' for name in group['domains'])}",
        f"- Stable entrypoint: `{_plugin_entrypoint(group_name)}`",
    ]
    lines.append("")
    return "\n".join(lines)


def sync_plugin_group_skills(repo_root: Path, plugin_groups: dict[str, dict[str, Any]]) -> list[str]:
    changed: list[str] = []
    for group_name, group in sorted(plugin_groups.items()):
        skill_path = repo_root / PLUGIN_SKILLS_ROOT / group_name / "SKILL.md"
        text = _render_plugin_skill(group)
        if _write_text(skill_path, text):
            changed.append(str(skill_path.relative_to(repo_root)))
    return changed


def sync_skill_projections(repo_root: Path) -> dict[str, list[str]]:
    payload = _load_catalog(repo_root)
    skills, plugin_groups = _validate_catalog(repo_root, payload)
    pointers = sync_agents_skill_pointers(repo_root, skills)
    plugin_skill_files = sync_plugin_group_skills(repo_root, plugin_groups)
    return {
        "agents_pointers": pointers,
        "plugin_skills": plugin_skill_files,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate repo skill pointer and plugin projection layers from catalog.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    result = sync_skill_projections(args.repo_root.resolve())
    total = len(result["agents_pointers"]) + len(result["plugin_skills"])
    print(
        yaml.safe_dump(
            {
                "ok": True,
                "changed": total,
                **result,
            },
            sort_keys=False,
            allow_unicode=False,
        ).strip()
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
