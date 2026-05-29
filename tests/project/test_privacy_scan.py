"""Tests for agentplane.domain.project.privacy_scan — pure path/content matching."""

from __future__ import annotations

from pathlib import Path

import pytest
from agentplane.domain.project.privacy_scan import (
    PRIVATE_CONTENT_PATTERNS,
    PRIVATE_PATH_PATTERNS,
    PrivacyScanIssue,
    _scan_content,
    _scan_path,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# PrivacyScanIssue
# ---------------------------------------------------------------------------


class TestPrivacyScanIssue:
    def test_to_dict(self) -> None:
        issue = PrivacyScanIssue(path="a.py", kind="private-domain", line=3, detail="d")
        assert issue.to_dict() == {
            "path": "a.py",
            "kind": "private-domain",
            "line": 3,
            "detail": "d",
        }

    def test_frozen(self) -> None:
        issue = PrivacyScanIssue(path="a.py", kind="k", line=None, detail="d")
        with pytest.raises(AttributeError):
            issue.path = "b.py"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# _scan_path — path pattern matching
# ---------------------------------------------------------------------------


class TestScanPath:
    def test_detects_private_inventory(self) -> None:
        issues = _scan_path("inventory/servers/wsl/inventory.json")
        assert len(issues) == 1
        assert issues[0].kind == "private-inventory"

    def test_detects_state_snapshot(self) -> None:
        issues = _scan_path("inventory/state-snapshot.md")
        assert len(issues) == 1
        assert issues[0].kind == "private-state-snapshot"

    def test_detects_private_runbook(self) -> None:
        issues = _scan_path("docs/runbooks/prod0-deploy.md")
        assert len(issues) == 1
        assert issues[0].kind == "private-runbook"

    def test_detects_private_compose(self) -> None:
        issues = _scan_path("infra/compose/relay-trojan/docker-compose.yaml")
        assert len(issues) == 1
        assert issues[0].kind == "private-compose-service"

    def test_detects_private_skill(self) -> None:
        issues = _scan_path(".agents/skills/tencent-dns/SKILL.md")
        assert len(issues) == 1
        assert issues[0].kind == "private-skill"

    def test_detects_private_host_helper(self) -> None:
        issues = _scan_path("agentplane/cli/prod0_commands.py")
        assert len(issues) == 1
        assert issues[0].kind == "private-host-helper"

    def test_clean_path_no_issues(self) -> None:
        issues = _scan_path("docs/core/architecture.md")
        assert issues == []

    def test_public_inventory_not_flagged(self) -> None:
        """Only inventory/servers/ is private, not inventory/ itself."""
        issues = _scan_path("inventory/README.md")
        assert issues == []


# ---------------------------------------------------------------------------
# _scan_content — content pattern matching
# ---------------------------------------------------------------------------


class TestScanContent:
    def test_detects_private_domain(self, tmp_path: Path) -> None:
        f = tmp_path / "readme.md"
        f.write_text("Visit https://app.zzzai.cloud for details\n", encoding="utf-8")
        issues = _scan_content(tmp_path, f)
        assert any(i.kind == "private-domain" for i in issues)

    def test_detects_private_ip(self, tmp_path: Path) -> None:
        f = tmp_path / "config.yaml"
        f.write_text("host: 175.178.114.100\n", encoding="utf-8")
        issues = _scan_content(tmp_path, f)
        assert any(i.kind == "private-public-ip" for i in issues)

    def test_detects_private_panel_entrance(self, tmp_path: Path) -> None:
        f = tmp_path / "docs.md"
        f.write_text("Use safe_entrance to access\n", encoding="utf-8")
        issues = _scan_content(tmp_path, f)
        assert any(i.kind == "private-panel-entrance" for i in issues)

    def test_detects_password_auth(self, tmp_path: Path) -> None:
        f = tmp_path / "inventory.json"
        f.write_text('"password_authentication": true\n', encoding="utf-8")
        issues = _scan_content(tmp_path, f)
        assert any(i.kind == "private-password-ssh" for i in issues)

    def test_detects_root_ssh(self, tmp_path: Path) -> None:
        f = tmp_path / "inventory.json"
        f.write_text('"permit_root_login": true\n', encoding="utf-8")
        issues = _scan_content(tmp_path, f)
        assert any(i.kind == "private-root-ssh" for i in issues)

    def test_clean_content_no_issues(self, tmp_path: Path) -> None:
        f = tmp_path / "readme.md"
        f.write_text("# Hello World\nThis is a clean file.\n", encoding="utf-8")
        issues = _scan_content(tmp_path, f)
        assert issues == []

    def test_binary_file_skipped(self, tmp_path: Path) -> None:
        f = tmp_path / "data.bin"
        f.write_bytes(b"\x00\x01zzzai.cloud\x02")
        issues = _scan_content(tmp_path, f)
        assert issues == []

    def test_missing_file_skipped(self, tmp_path: Path) -> None:
        issues = _scan_content(tmp_path, tmp_path / "nope.txt")
        assert issues == []

    def test_line_numbers_correct(self, tmp_path: Path) -> None:
        f = tmp_path / "test.md"
        f.write_text("line1\nline2\nVisit zzzai.cloud here\nline4\n", encoding="utf-8")
        issues = _scan_content(tmp_path, f)
        domain_issues = [i for i in issues if i.kind == "private-domain"]
        assert len(domain_issues) == 1
        assert domain_issues[0].line == 3


# ---------------------------------------------------------------------------
# Pattern constants
# ---------------------------------------------------------------------------


class TestPatterns:
    def test_path_patterns_compile(self) -> None:
        for kind, pattern in PRIVATE_PATH_PATTERNS:
            assert isinstance(kind, str)
            assert pattern.search("") is None or True

    def test_content_patterns_compile(self) -> None:
        for kind, pattern in PRIVATE_CONTENT_PATTERNS:
            assert isinstance(kind, str)
            assert pattern.search("") is None or True


# ---------------------------------------------------------------------------
# Golden test
# ---------------------------------------------------------------------------


@pytest.mark.golden
class TestPrivacyScanGolden:
    def test_path_and_content_together(self, tmp_path: Path) -> None:
        """A file matching both path and content patterns produces issues from both."""
        # Path match: inventory/servers/
        # Content match: private IP
        f = tmp_path / "inventory" / "servers" / "wsl"
        f.mkdir(parents=True)
        inv = f / "inventory.json"
        inv.write_text('{"ip": "175.178.114.100"}\n', encoding="utf-8")

        relative = inv.relative_to(tmp_path).as_posix()
        path_issues = _scan_path(relative)
        content_issues = _scan_content(tmp_path, inv)

        assert len(path_issues) >= 1
        assert len(content_issues) >= 1
        assert path_issues[0].kind == "private-inventory"
        assert content_issues[0].kind == "private-public-ip"
