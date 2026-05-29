"""Tests for agentplane.domain.project.docs_sanity — pure helper functions."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest
from agentplane.domain.project.docs_sanity import (
    CONCLUSION_RE,
    DocsSanityIssue,
    _check_agents_redirect,
    _check_archive_status,
    _check_audience_terminology,
    _check_conclusion_line,
    _check_frontmatter,
    _check_readme_length,
    _is_archive_or_history,
    _is_external_link,
    _line_for_offset,
    _local_link_path,
    _relative_parts_under_docs,
    _strip_code_blocks,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# DocsSanityIssue
# ---------------------------------------------------------------------------


class TestDocsSanityIssue:
    def test_to_dict(self) -> None:
        issue = DocsSanityIssue(path="a.md", kind="missing-frontmatter", line=1, detail="d")
        assert issue.to_dict() == {
            "path": "a.md",
            "kind": "missing-frontmatter",
            "line": 1,
            "detail": "d",
            "severity": "error",
        }

    def test_custom_severity(self) -> None:
        issue = DocsSanityIssue(path="a.md", kind="k", line=None, detail="d", severity="warning")
        assert issue.to_dict()["severity"] == "warning"

    def test_frozen(self) -> None:
        issue = DocsSanityIssue(path="a.md", kind="k", line=1, detail="d")
        with pytest.raises(AttributeError):
            issue.path = "b.md"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# _line_for_offset
# ---------------------------------------------------------------------------


class TestLineForOffset:
    def test_first_line(self) -> None:
        assert _line_for_offset("hello world", 0) == 1

    def test_after_newline(self) -> None:
        assert _line_for_offset("line1\nline2", 6) == 2

    def test_multiple_newlines(self) -> None:
        assert _line_for_offset("a\nb\nc\nd", 5) == 3


# ---------------------------------------------------------------------------
# _is_external_link
# ---------------------------------------------------------------------------


class TestIsExternalLink:
    def test_http(self) -> None:
        assert _is_external_link("https://example.com") is True

    def test_mailto(self) -> None:
        assert _is_external_link("mailto:user@example.com") is True

    def test_anchor(self) -> None:
        assert _is_external_link("#section") is True

    def test_local_path(self) -> None:
        assert _is_external_link("docs/architecture.md") is False

    def test_relative(self) -> None:
        assert _is_external_link("./file.md") is False


# ---------------------------------------------------------------------------
# _local_link_path
# ---------------------------------------------------------------------------


class TestLocalLinkPath:
    def test_plain_path(self) -> None:
        assert _local_link_path("docs/architecture.md") == "docs/architecture.md"

    def test_strips_anchor(self) -> None:
        assert _local_link_path("docs/architecture.md#section") == "docs/architecture.md"

    def test_anchor_only(self) -> None:
        assert _local_link_path("#section") == ""


# ---------------------------------------------------------------------------
# _relative_parts_under_docs
# ---------------------------------------------------------------------------


class TestRelativePartsUnderDocs:
    def test_under_docs(self, tmp_path: Path) -> None:
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        f = docs_dir / "architecture" / "design.md"
        f.parent.mkdir(parents=True)
        f.touch()
        parts = _relative_parts_under_docs(f, tmp_path)
        assert parts is not None
        assert "architecture" in parts

    def test_not_under_docs(self, tmp_path: Path) -> None:
        f = tmp_path / "README.md"
        f.touch()
        assert _relative_parts_under_docs(f, tmp_path) is None

    def test_directly_under_docs(self, tmp_path: Path) -> None:
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        f = docs_dir / "README.md"
        f.touch()
        parts = _relative_parts_under_docs(f, tmp_path)
        assert parts is not None
        # README.md itself is excluded from parts
        assert "README.md" not in parts


# ---------------------------------------------------------------------------
# _is_archive_or_history
# ---------------------------------------------------------------------------


class TestIsArchiveOrHistory:
    def test_archive(self) -> None:
        assert _is_archive_or_history("docs/archive/old.md") is True

    def test_history(self) -> None:
        assert _is_archive_or_history("docs/history/v1.md") is True

    def test_normal(self) -> None:
        assert _is_archive_or_history("docs/architecture/design.md") is False


# ---------------------------------------------------------------------------
# _strip_code_blocks
# ---------------------------------------------------------------------------


class TestStripCodeBlocks:
    def test_removes_fenced_blocks(self) -> None:
        text = "before\n```python\ncode here\n```\nafter"
        result = _strip_code_blocks(text)
        assert "code here" not in result
        assert "before" in result
        assert "after" in result

    def test_removes_inline_code(self) -> None:
        text = "use `run_command` to run"
        result = _strip_code_blocks(text)
        assert "run_command" not in result
        assert "use" in result

    def test_no_code_blocks(self) -> None:
        text = "plain text here"
        assert _strip_code_blocks(text) == text


# ---------------------------------------------------------------------------
# _check_frontmatter
# ---------------------------------------------------------------------------


class TestCheckFrontmatter:
    def test_archive_skipped(self) -> None:
        issues = _check_frontmatter("docs/archive/old.md", "content", {"archive"})
        assert issues == []

    def test_no_doc_parts_skipped(self) -> None:
        issues = _check_frontmatter("docs/other/file.md", "content", None)
        assert issues == []

    def test_no_required_dirs_skipped(self) -> None:
        issues = _check_frontmatter("docs/other/file.md", "content", {"other"})
        assert issues == []

    def test_missing_frontmatter(self) -> None:
        issues = _check_frontmatter("docs/reference/file.md", "content", {"reference"})
        assert len(issues) == 1
        assert issues[0].kind == "missing-frontmatter"

    def test_incomplete_frontmatter(self) -> None:
        text = "---\nstatus: active\n---\nContent"
        issues = _check_frontmatter("docs/reference/file.md", text, {"reference"})
        kinds = {i.kind for i in issues}
        assert "incomplete-frontmatter" in kinds

    def test_complete_frontmatter(self) -> None:
        today = date.today().isoformat()
        text = f"---\nstatus: active\nowner: test\nlast_verified: {today}\nsuperseded_by: none\naudience: both\n---\nContent"
        issues = _check_frontmatter("docs/reference/file.md", text, {"reference"})
        assert not any(i.kind == "incomplete-frontmatter" for i in issues)

    def test_stale_last_verified(self) -> None:
        old_date = (date.today() - timedelta(days=60)).isoformat()
        text = f"---\nstatus: active\nowner: test\nlast_verified: {old_date}\nsuperseded_by: none\naudience: both\n---\nContent"
        issues = _check_frontmatter("docs/reference/file.md", text, {"reference"})
        assert any(i.kind == "stale-last-verified" for i in issues)


# ---------------------------------------------------------------------------
# _check_readme_length
# ---------------------------------------------------------------------------


class TestCheckReadmeLength:
    def test_no_readme(self, tmp_path: Path) -> None:
        assert _check_readme_length(tmp_path) == []

    def test_short_readme(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text("short\n", encoding="utf-8")
        assert _check_readme_length(tmp_path) == []

    def test_long_readme(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text("x\n" * 200, encoding="utf-8")
        issues = _check_readme_length(tmp_path)
        assert len(issues) == 1
        assert issues[0].kind == "readme-too-long"


# ---------------------------------------------------------------------------
# _check_audience_terminology
# ---------------------------------------------------------------------------


class TestCheckAudienceTerminology:
    def test_no_audience_skipped(self) -> None:
        issues = _check_audience_terminology("docs/file.md", "some content")
        assert issues == []

    def test_both_audience_skipped(self) -> None:
        text = "audience: both\n真源 content"
        issues = _check_audience_terminology("docs/file.md", text)
        assert issues == []

    def test_human_audience_flagged(self) -> None:
        text = "audience: human\nThis references 真源 stuff"
        issues = _check_audience_terminology("docs/file.md", text)
        assert any(i.kind == "ai-term-in-human-doc" for i in issues)

    def test_agent_audience_skipped(self) -> None:
        text = "audience: agent\n真源 content"
        issues = _check_audience_terminology("docs/file.md", text)
        assert issues == []


# ---------------------------------------------------------------------------
# _check_agents_redirect
# ---------------------------------------------------------------------------


class TestCheckAgentsRedirect:
    def test_non_agents_md_skipped(self) -> None:
        assert _check_agents_redirect("README.md", "content") == []

    def test_agents_md_missing_redirect(self) -> None:
        issues = _check_agents_redirect("AGENTS.md", "some content without redirect")
        assert len(issues) == 1
        assert issues[0].kind == "missing-agents-human-redirect"

    def test_agents_md_has_redirect(self) -> None:
        issues = _check_agents_redirect("AGENTS.md", "see docs/getting-started/getting-started.md")
        assert issues == []


# ---------------------------------------------------------------------------
# _check_archive_status
# ---------------------------------------------------------------------------


class TestCheckArchiveStatus:
    def test_non_archive_skipped(self) -> None:
        issues = _check_archive_status("docs/file.md", "status: active")
        assert issues == []

    def test_archive_active_flagged(self) -> None:
        text = "---\nstatus: active\n---\ncontent"
        issues = _check_archive_status("docs/archive/old.md", text)
        assert len(issues) == 1
        assert issues[0].kind == "archive-doc-active"

    def test_archive_archived_ok(self) -> None:
        text = "---\nstatus: archived\n---\ncontent"
        issues = _check_archive_status("docs/archive/old.md", text)
        assert issues == []

    def test_archive_no_frontmatter_ok(self) -> None:
        issues = _check_archive_status("docs/archive/old.md", "just content")
        assert issues == []


# ---------------------------------------------------------------------------
# _check_conclusion_line
# ---------------------------------------------------------------------------


class TestCheckConclusionLine:
    def test_archive_skipped(self) -> None:
        issues = _check_conclusion_line("docs/archive/old.md", "content", {"archive"})
        assert issues == []

    def test_no_doc_parts_skipped(self) -> None:
        issues = _check_conclusion_line("docs/file.md", "content", None)
        assert issues == []

    def test_no_required_dirs_skipped(self) -> None:
        issues = _check_conclusion_line("docs/file.md", "content", {"other"})
        assert issues == []

    def test_docs_readme_skipped(self) -> None:
        issues = _check_conclusion_line("docs/README.md", "content", {"reference"})
        assert issues == []

    def test_has_conclusion_ok(self) -> None:
        issues = _check_conclusion_line("docs/reference/file.md", "结论：this is fine", {"reference"})
        assert issues == []

    def test_missing_conclusion(self) -> None:
        issues = _check_conclusion_line("docs/reference/file.md", "no conclusion here", {"reference"})
        assert len(issues) == 1
        assert issues[0].kind == "missing-conclusion"


# ---------------------------------------------------------------------------
# CONCLUSION_RE
# ---------------------------------------------------------------------------


class TestConclusionRegex:
    def test_chinese_colon(self) -> None:
        assert CONCLUSION_RE.search("结论：something") is not None

    def test_ascii_colon(self) -> None:
        assert CONCLUSION_RE.search("结论:something") is not None

    def test_no_match(self) -> None:
        assert CONCLUSION_RE.search("no match") is None


# ---------------------------------------------------------------------------
# Golden test
# ---------------------------------------------------------------------------


@pytest.mark.golden
class TestDocsSanityGolden:
    def test_check_frontmatter_full(self, tmp_path: Path) -> None:
        """Full frontmatter with fresh date produces no issues."""
        today = date.today().isoformat()
        text = f"---\nstatus: active\nowner: team\nlast_verified: {today}\nsuperseded_by: none\naudience: both\n---\nContent here."
        issues = _check_frontmatter("docs/reference/design.md", text, {"reference"})
        assert issues == []

    def test_all_archive_paths(self) -> None:
        """Both archive and history paths are detected."""
        assert _is_archive_or_history("docs/archive/old.md") is True
        assert _is_archive_or_history("docs/history/v1.md") is True
        assert _is_archive_or_history("docs/reference/file.md") is False
