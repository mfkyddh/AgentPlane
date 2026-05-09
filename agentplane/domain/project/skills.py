from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

REQUIRED_SKILL_SECTIONS = ("## Overview", "## Commands", "## Rules", "## Downstream Docs")

# Known CLI command prefixes that are valid formal surfaces
VALID_CLI_PREFIXES = (
    "agentplane infra",
    "agentplane service",
    "agentplane ingress",
    "agentplane app",
    "agentplane project",
    "agentplane infra",
    "agentplane service",
    "agentplane ingress",
    "agentplane app",
    "agentplane test",
)


@dataclass(frozen=True)
class SkillIssue:
    path: str
    kind: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {
            "path": self.path,
            "kind": self.kind,
            "detail": self.detail,
        }


def _skills_root(repo_root: Path) -> Path:
    return repo_root / ".agents" / "skills"


def _catalog_file(repo_root: Path) -> Path:
    return _skills_root(repo_root) / "catalog.yaml"


def _relative(repo_root: Path, path: Path) -> str:
    return path.relative_to(repo_root).as_posix()


def _git_tracked_skill_paths(repo_root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", ".agents/skills/*/SKILL.md"],
        cwd=repo_root,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    return sorted(repo_root / line for line in result.stdout.splitlines() if line.strip())


def _load_skill_frontmatter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError("missing skill frontmatter")
    payload = yaml.safe_load(parts[1])
    if not isinstance(payload, dict):
        raise ValueError("skill frontmatter must be a mapping")
    return payload


def load_skill_catalog(repo_root: Path) -> dict[str, Any]:
    path = _catalog_file(repo_root)
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("skill catalog must be a mapping")
    skills = payload.get("skills")
    if not isinstance(skills, list):
        raise ValueError("skill catalog must contain a skills list")
    return payload


def list_skill_entries(repo_root: Path) -> list[dict[str, Any]]:
    catalog = load_skill_catalog(repo_root)
    entries: list[dict[str, Any]] = []
    for item in catalog["skills"]:
        if not isinstance(item, dict):
            continue
        entry = dict(item)
        source_path = str(entry.get("source_path", ""))
        skill_path = repo_root / source_path
        entry["exists"] = skill_path.is_file()
        entry["directory"] = skill_path.parent.name if source_path else ""
        entries.append(entry)
    return entries


def export_skill_surface(repo_root: Path) -> dict[str, Any]:
    entries = list_skill_entries(repo_root)
    return {
        "version": load_skill_catalog(repo_root).get("version"),
        "skills": entries,
    }


def write_skill_export(repo_root: Path, output: Path) -> Path:
    payload = export_skill_surface(repo_root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def _extract_commands_from_skill(text: str) -> list[str]:
    """Extract CLI commands from the ## Commands section of a skill file."""
    commands: list[str] = []
    in_commands_section = False
    in_code_block = False

    for line in text.splitlines():
        if line.strip() == "## Commands":
            in_commands_section = True
            continue
        if in_commands_section and line.startswith("## "):
            break
        if in_commands_section and line.strip() == "```bash":
            in_code_block = True
            continue
        if in_commands_section and in_code_block and line.strip() == "```":
            in_code_block = False
            continue
        if in_commands_section and in_code_block:
            cmd = line.strip()
            if cmd and not cmd.startswith("#"):
                # Take only the command part (before any comment)
                cmd = cmd.split("#")[0].strip()
                if cmd:
                    commands.append(cmd)

    return commands


def _validate_cli_commands(commands: list[str], skill_path: str) -> list[SkillIssue]:
    """Validate that commands in skill follow valid CLI structure."""
    issues: list[SkillIssue] = []

    for cmd in commands:
        # Skip commands that are not agentplane commands
        if not cmd.startswith("agentplane "):
            continue

        # Check if command starts with a valid prefix
        has_valid_prefix = any(cmd.startswith(prefix) for prefix in VALID_CLI_PREFIXES)
        if not has_valid_prefix:
            issues.append(
                SkillIssue(
                    path=skill_path,
                    kind="invalid-cli-command",
                    detail=f"command does not match any valid CLI prefix: {cmd}",
                )
            )

    return issues


def check_skill_surface(repo_root: Path) -> list[SkillIssue]:
    root = repo_root.resolve()
    issues: list[SkillIssue] = []
    catalog_path = _catalog_file(root)
    try:
        catalog = load_skill_catalog(root)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        return [
            SkillIssue(
                path=_relative(root, catalog_path) if catalog_path.exists() else ".agents/skills/catalog.yaml",
                kind="invalid-catalog",
                detail=str(exc),
            )
        ]

    entries = [entry for entry in catalog["skills"] if isinstance(entry, dict)]
    names = [str(entry.get("name", "")) for entry in entries]
    duplicate_names = sorted({name for name in names if names.count(name) > 1})
    for name in duplicate_names:
        issues.append(
            SkillIssue(path=_relative(root, catalog_path), kind="duplicate-skill", detail=f"duplicate skill: {name}")
        )

    catalog_by_name = {str(entry.get("name")): entry for entry in entries if entry.get("name")}
    tracked_paths = _git_tracked_skill_paths(root)
    tracked_names = {path.parent.name for path in tracked_paths}
    catalog_names = set(catalog_by_name)

    for name in sorted(tracked_names - catalog_names):
        issues.append(
            SkillIssue(
                path=f".agents/skills/{name}/SKILL.md",
                kind="missing-catalog-entry",
                detail="tracked skill is not registered in catalog.yaml",
            )
        )
    for name in sorted(catalog_names - tracked_names):
        source_path = str(catalog_by_name[name].get("source_path", f".agents/skills/{name}/SKILL.md"))
        issues.append(
            SkillIssue(
                path=source_path,
                kind="untracked-catalog-entry",
                detail="catalog entry does not point to a tracked public skill",
            )
        )

    for entry in entries:
        name = str(entry.get("name", ""))
        source_path = str(entry.get("source_path", ""))
        skill_path = root / source_path
        if not source_path:
            issues.append(
                SkillIssue(
                    path=_relative(root, catalog_path), kind="missing-source-path", detail=f"{name} has no source_path"
                )
            )
            continue
        if skill_path.parent.name != name:
            issues.append(
                SkillIssue(
                    path=source_path, kind="path-name-mismatch", detail=f"path directory must match skill name: {name}"
                )
            )
        if not skill_path.is_file():
            issues.append(
                SkillIssue(path=source_path, kind="missing-skill-file", detail="catalog source_path does not exist")
            )
            continue

        text = skill_path.read_text(encoding="utf-8")
        try:
            frontmatter = _load_skill_frontmatter(skill_path)
        except ValueError as exc:
            issues.append(SkillIssue(path=source_path, kind="invalid-frontmatter", detail=str(exc)))
            continue

        frontmatter_name = str(frontmatter.get("name", ""))
        if frontmatter_name != name:
            issues.append(
                SkillIssue(
                    path=source_path,
                    kind="frontmatter-name-mismatch",
                    detail=f"expected {name}, got {frontmatter_name}",
                )
            )
        if str(entry.get("frontmatter_name", "")) != frontmatter_name:
            issues.append(
                SkillIssue(
                    path=source_path,
                    kind="catalog-frontmatter-mismatch",
                    detail=f"catalog frontmatter_name must equal skill frontmatter name: {frontmatter_name}",
                )
            )

        for section in REQUIRED_SKILL_SECTIONS:
            if section not in text:
                issues.append(
                    SkillIssue(path=source_path, kind="missing-section", detail=f"missing required section: {section}")
                )

        kind = str(entry.get("kind", ""))
        has_cli_routing = "uv run python -m agentplane.cli" in text or "\nagentplane " in text
        if kind == "canonical" and not has_cli_routing:
            issues.append(
                SkillIssue(
                    path=source_path,
                    kind="canonical-without-cli",
                    detail="canonical skill must route through AgentPlane CLI",
                )
            )
        if kind == "workflow" and "docker compose" in text and "Prefer a formal AgentPlane CLI workflow" not in text:
            issues.append(
                SkillIssue(
                    path=source_path,
                    kind="workflow-raw-command-without-boundary",
                    detail="workflow skills using raw shell or compose must explain the formal CLI boundary",
                )
            )

        # Validate CLI commands in skill
        commands = _extract_commands_from_skill(text)
        if kind == "canonical" and not commands:
            issues.append(
                SkillIssue(
                    path=source_path,
                    kind="empty-commands-section",
                    detail="canonical skill must list at least one CLI command in ## Commands section",
                )
            )
        command_issues = _validate_cli_commands(commands, source_path)
        issues.extend(command_issues)

    return issues


def skill_sync_report(repo_root: Path) -> dict[str, Any]:
    root = repo_root.resolve()
    entries = list_skill_entries(root)
    tracked_names = {path.parent.name for path in _git_tracked_skill_paths(root)}
    catalog_names = {str(entry["name"]) for entry in entries if entry.get("name")}
    issues = check_skill_surface(root)
    return {
        "catalog_only": sorted(catalog_names - tracked_names),
        "tracked_only": sorted(tracked_names - catalog_names),
        "would_write": False,
        "reason": "catalog sync is dry-run only; domains, aliases, and entrypoints remain maintainer-authored",
        "ok": not issues,
        "issues": [issue.to_dict() for issue in issues],
    }
