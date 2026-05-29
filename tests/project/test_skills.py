"""Tests for agentplane.domain.project.skills — pure helper functions."""

from __future__ import annotations

from pathlib import Path

import pytest
from agentplane.domain.project.skills import (
    SkillIssue,
    _catalog_file,
    _extract_commands_from_skill,
    _load_skill_frontmatter,
    _relative,
    _skills_root,
    _validate_cli_commands,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# SkillIssue
# ---------------------------------------------------------------------------


class TestSkillIssue:
    def test_to_dict(self) -> None:
        issue = SkillIssue(path="a/b", kind="missing", detail="no file")
        d = issue.to_dict()
        assert d == {"path": "a/b", "kind": "missing", "detail": "no file"}

    def test_frozen(self) -> None:
        issue = SkillIssue(path="x", kind="y", detail="z")
        with pytest.raises(AttributeError):
            issue.path = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# _skills_root / _catalog_file / _relative
# ---------------------------------------------------------------------------


class TestPathHelpers:
    def test_skills_root(self, tmp_path: Path) -> None:
        assert _skills_root(tmp_path) == tmp_path / ".agents" / "skills"

    def test_catalog_file(self, tmp_path: Path) -> None:
        assert _catalog_file(tmp_path) == tmp_path / ".agents" / "skills" / "catalog.yaml"

    def test_relative(self, tmp_path: Path) -> None:
        full = tmp_path / ".agents" / "skills" / "my-skill" / "SKILL.md"
        assert _relative(tmp_path, full) == ".agents/skills/my-skill/SKILL.md"


# ---------------------------------------------------------------------------
# _load_skill_frontmatter
# ---------------------------------------------------------------------------


class TestLoadSkillFrontmatter:
    def test_valid(self, tmp_path: Path) -> None:
        f = tmp_path / "SKILL.md"
        f.write_text("---\nname: test-skill\nkind: canonical\n---\nBody here", encoding="utf-8")
        result = _load_skill_frontmatter(f)
        assert result["name"] == "test-skill"
        assert result["kind"] == "canonical"

    def test_missing_frontmatter(self, tmp_path: Path) -> None:
        f = tmp_path / "SKILL.md"
        f.write_text("No frontmatter here", encoding="utf-8")
        with pytest.raises(ValueError, match="missing skill frontmatter"):
            _load_skill_frontmatter(f)

    def test_non_mapping_frontmatter(self, tmp_path: Path) -> None:
        f = tmp_path / "SKILL.md"
        f.write_text("---\n- item1\n- item2\n---\nBody", encoding="utf-8")
        with pytest.raises(ValueError, match="must be a mapping"):
            _load_skill_frontmatter(f)

    def test_empty_frontmatter(self, tmp_path: Path) -> None:
        f = tmp_path / "SKILL.md"
        f.write_text("---\n\n---\nBody", encoding="utf-8")
        # yaml.safe_load of empty string returns None, not dict
        with pytest.raises(ValueError, match="must be a mapping"):
            _load_skill_frontmatter(f)


# ---------------------------------------------------------------------------
# _extract_commands_from_skill
# ---------------------------------------------------------------------------


class TestExtractCommandsFromSkill:
    def test_extracts_from_code_block(self) -> None:
        text = """## Overview

Some text.

## Commands

```bash
agentplane infra list
agentplane app status --app myapp
```

## Rules

No rules.
"""
        commands = _extract_commands_from_skill(text)
        assert "agentplane infra list" in commands
        assert "agentplane app status --app myapp" in commands

    def test_no_commands_section(self) -> None:
        text = "## Overview\nJust text.\n## Rules\nNo rules."
        assert _extract_commands_from_skill(text) == []

    def test_skips_comments(self) -> None:
        text = """## Commands

```bash
agentplane infra list
# this is a comment
agentplane app deploy
```
"""
        commands = _extract_commands_from_skill(text)
        assert len(commands) == 2
        assert "# this is a comment" not in commands

    def test_inline_comment_stripped(self) -> None:
        text = """## Commands

```bash
agentplane infra list  # with inline comment
```
"""
        commands = _extract_commands_from_skill(text)
        assert commands == ["agentplane infra list"]


# ---------------------------------------------------------------------------
# _validate_cli_commands
# ---------------------------------------------------------------------------


class TestValidateCliCommands:
    def test_valid_prefix(self) -> None:
        issues = _validate_cli_commands(["agentplane infra list"], "skill.md")
        assert issues == []

    def test_invalid_prefix(self) -> None:
        issues = _validate_cli_commands(["agentplane unknown cmd"], "skill.md")
        assert len(issues) == 1
        assert issues[0].kind == "invalid-cli-command"

    def test_non_agentplane_skipped(self) -> None:
        issues = _validate_cli_commands(["docker compose up", "make test"], "skill.md")
        assert issues == []

    def test_all_valid_prefixes(self) -> None:
        cmds = [
            "agentplane infra list",
            "agentplane service status",
            "agentplane ingress plan",
            "agentplane app deploy",
            "agentplane project status",
            "agentplane test run",
        ]
        issues = _validate_cli_commands(cmds, "skill.md")
        assert issues == []

    def test_empty_list(self) -> None:
        assert _validate_cli_commands([], "skill.md") == []


# ---------------------------------------------------------------------------
# Golden test
# ---------------------------------------------------------------------------


@pytest.mark.golden
class TestSkillsGolden:
    def test_full_skill_parsing(self, tmp_path: Path) -> None:
        """Full SKILL.md with frontmatter and commands parses correctly."""
        skill_md = """---
name: test-skill
kind: canonical
description: A test skill
---

## Overview

Test skill overview.

## Commands

```bash
agentplane infra list
agentplane app deploy --app test
```

## Rules

- Follow conventions

## Downstream Docs

See docs/
"""
        f = tmp_path / "SKILL.md"
        f.write_text(skill_md, encoding="utf-8")
        fm = _load_skill_frontmatter(f)
        assert fm["name"] == "test-skill"
        assert fm["kind"] == "canonical"

        commands = _extract_commands_from_skill(skill_md)
        assert len(commands) == 2
        assert commands[0] == "agentplane infra list"

        issues = _validate_cli_commands(commands, "test-skill/SKILL.md")
        assert issues == []
