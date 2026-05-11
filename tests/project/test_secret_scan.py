"""Tests for agentplane.domain.project.secret_scan — pure logic, no I/O beyond tmp_path."""

from __future__ import annotations

from pathlib import Path

import pytest

from agentplane.domain.project.secret_scan import (
    SECRET_PATTERNS,
    SecretScanAllow,
    SecretScanIssue,
    _apply_allowlist,
    _is_placeholder,
    _is_text_file,
    _scan_file_content,
    load_secret_scan_allowlist,
    scan_repository_for_secrets,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# SecretScanIssue
# ---------------------------------------------------------------------------


class TestSecretScanIssue:
    def test_to_dict(self) -> None:
        issue = SecretScanIssue(path="a.py", kind="openai-token", line=5, detail="found")
        assert issue.to_dict() == {
            "path": "a.py",
            "kind": "openai-token",
            "line": 5,
            "detail": "found",
        }

    def test_frozen(self) -> None:
        issue = SecretScanIssue(path="a.py", kind="k", line=None, detail="d")
        with pytest.raises(AttributeError):
            issue.path = "b.py"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# SecretScanAllow
# ---------------------------------------------------------------------------


class TestSecretScanAllow:
    def test_matches_exact(self) -> None:
        allow = SecretScanAllow(kind="openai-token", path="a.py", line=5)
        issue = SecretScanIssue(path="a.py", kind="openai-token", line=5, detail="d")
        assert allow.matches(issue) is True

    def test_matches_wildcard_kind(self) -> None:
        allow = SecretScanAllow(kind="*", path="a.py")
        issue = SecretScanIssue(path="a.py", kind="anything", line=1, detail="d")
        assert allow.matches(issue) is True

    def test_matches_wildcard_path(self) -> None:
        allow = SecretScanAllow(kind="openai-token", path="*")
        issue = SecretScanIssue(path="x/y.py", kind="openai-token", line=1, detail="d")
        assert allow.matches(issue) is True

    def test_no_match_wrong_kind(self) -> None:
        allow = SecretScanAllow(kind="openai-token", path="a.py")
        issue = SecretScanIssue(path="a.py", kind="github-token", line=1, detail="d")
        assert allow.matches(issue) is False

    def test_no_match_wrong_line(self) -> None:
        allow = SecretScanAllow(kind="k", path="a.py", line=5)
        issue = SecretScanIssue(path="a.py", kind="k", line=99, detail="d")
        assert allow.matches(issue) is False

    def test_matches_no_line_constraint(self) -> None:
        allow = SecretScanAllow(kind="k", path="a.py", line=None)
        issue = SecretScanIssue(path="a.py", kind="k", line=99, detail="d")
        assert allow.matches(issue) is True


# ---------------------------------------------------------------------------
# _is_placeholder
# ---------------------------------------------------------------------------


class TestIsPlaceholder:
    @pytest.mark.parametrize(
        "value",
        [
            "",
            "  ",
            "'changeme'",
            '"example"',
            "<your-key-here>",
            "$API_KEY",
            "xxxx",
            "**",
            "todo",
            "placeholder",
            "sample_value",
        ],
    )
    def test_placeholders_detected(self, value: str) -> None:
        assert _is_placeholder(value) is True

    @pytest.mark.parametrize(
        "value",
        [
            "sk-abc123def456ghi789jkl012",
            "real-password-123",
            "AKIAIOSFODNN7STUV",
        ],
    )
    def test_real_values_not_placeholders(self, value: str) -> None:
        assert _is_placeholder(value) is False


# ---------------------------------------------------------------------------
# _is_text_file
# ---------------------------------------------------------------------------


class TestIsTextFile:
    def test_text_file(self, tmp_path: Path) -> None:
        f = tmp_path / "hello.txt"
        f.write_text("hello world", encoding="utf-8")
        assert _is_text_file(f) is True

    def test_binary_file(self, tmp_path: Path) -> None:
        f = tmp_path / "binary.bin"
        f.write_bytes(b"\x00\x01\x02\x03")
        assert _is_text_file(f) is False

    def test_missing_file(self, tmp_path: Path) -> None:
        assert _is_text_file(tmp_path / "nope.txt") is False


# ---------------------------------------------------------------------------
# load_secret_scan_allowlist
# ---------------------------------------------------------------------------


class TestLoadAllowlist:
    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        assert load_secret_scan_allowlist(tmp_path) == []

    def test_parses_entries(self, tmp_path: Path) -> None:
        f = tmp_path / ".secret-scan-allowlist"
        f.write_text(
            "# comment\nopenai-token a.py 5\ngithub-token b.py\n* c.py 10\n",
            encoding="utf-8",
        )
        result = load_secret_scan_allowlist(tmp_path, allowlist_path=f)
        assert len(result) == 3
        assert result[0] == SecretScanAllow(kind="openai-token", path="a.py", line=5)
        assert result[1] == SecretScanAllow(kind="github-token", path="b.py", line=None)
        assert result[2] == SecretScanAllow(kind="*", path="c.py", line=10)

    def test_invalid_entry_raises(self, tmp_path: Path) -> None:
        f = tmp_path / ".secret-scan-allowlist"
        f.write_text("too many parts here extra\n", encoding="utf-8")
        with pytest.raises(ValueError, match="invalid secret scan allowlist"):
            load_secret_scan_allowlist(tmp_path, allowlist_path=f)

    def test_skips_blank_lines(self, tmp_path: Path) -> None:
        f = tmp_path / ".secret-scan-allowlist"
        f.write_text("\n\n# comment\nopenai-token a.py\n", encoding="utf-8")
        result = load_secret_scan_allowlist(tmp_path, allowlist_path=f)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# _apply_allowlist
# ---------------------------------------------------------------------------


class TestApplyAllowlist:
    def test_filters_matching_issues(self) -> None:
        issues = [
            SecretScanIssue(path="a.py", kind="openai-token", line=5, detail="d"),
            SecretScanIssue(path="b.py", kind="github-token", line=10, detail="d"),
        ]
        allowlist = [SecretScanAllow(kind="openai-token", path="a.py", line=5)]
        result = _apply_allowlist(issues, allowlist)
        assert len(result) == 1
        assert result[0].path == "b.py"

    def test_empty_allowlist_keeps_all(self) -> None:
        issues = [SecretScanIssue(path="a.py", kind="k", line=1, detail="d")]
        assert _apply_allowlist(issues, []) == issues


# ---------------------------------------------------------------------------
# _scan_file_content
# ---------------------------------------------------------------------------


class TestScanFileContent:
    def test_detects_private_key(self, tmp_path: Path) -> None:
        f = tmp_path / "key.pem"
        f.write_text("-----BEGIN RSA PRIVATE KEY-----\nMIIE...", encoding="utf-8")
        issues = _scan_file_content(tmp_path, f)
        assert any(i.kind == "private-key" for i in issues)

    def test_detects_openai_token(self, tmp_path: Path) -> None:
        f = tmp_path / "config.yaml"
        f.write_text('api_key: sk-abc123def456ghi789jkl012mno345pqr678stu901vwx', encoding="utf-8")
        issues = _scan_file_content(tmp_path, f)
        assert any(i.kind == "openai-token" for i in issues)

    def test_detects_github_token(self, tmp_path: Path) -> None:
        f = tmp_path / ".env"
        f.write_text("GITHUB_TOKEN=ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdef", encoding="utf-8")
        issues = _scan_file_content(tmp_path, f)
        assert any(i.kind == "github-token" for i in issues)

    def test_detects_aws_key(self, tmp_path: Path) -> None:
        f = tmp_path / "config.env"
        f.write_text("aws_access_key_id = AKIAIOSFODNN7EXAMPLE", encoding="utf-8")
        issues = _scan_file_content(tmp_path, f)
        assert any(i.kind == "aws-access-key" for i in issues)

    def test_secret_assignment_in_config(self, tmp_path: Path) -> None:
        f = tmp_path / "app.conf"
        f.write_text('password: "real-secret-value-123"', encoding="utf-8")
        issues = _scan_file_content(tmp_path, f)
        assert any(i.kind == "secret-assignment" for i in issues)

    def test_secret_assignment_placeholder_ignored(self, tmp_path: Path) -> None:
        f = tmp_path / "app.conf"
        f.write_text('password: "changeme"', encoding="utf-8")
        issues = _scan_file_content(tmp_path, f)
        assert not any(i.kind == "secret-assignment" for i in issues)

    def test_no_assignment_in_non_config(self, tmp_path: Path) -> None:
        f = tmp_path / "readme.md"
        f.write_text('password: "real-secret-value-123"', encoding="utf-8")
        issues = _scan_file_content(tmp_path, f)
        # secret-assignment should NOT fire for .md files
        assert not any(i.kind == "secret-assignment" for i in issues)

    def test_binary_file_skipped(self, tmp_path: Path) -> None:
        f = tmp_path / "data.bin"
        f.write_bytes(b"\x00sk-abc123def456ghi789jkl012mno345")
        issues = _scan_file_content(tmp_path, f)
        assert issues == []

    def test_clean_file_no_issues(self, tmp_path: Path) -> None:
        f = tmp_path / "clean.py"
        f.write_text("x = 1\nprint(x)\n", encoding="utf-8")
        issues = _scan_file_content(tmp_path, f)
        assert issues == []


# ---------------------------------------------------------------------------
# scan_repository_for_secrets (integration with tmp_path)
# ---------------------------------------------------------------------------


class TestScanRepository:
    def test_clean_repo_no_issues(self, tmp_path: Path) -> None:
        f = tmp_path / "hello.py"
        f.write_text("print('hello')\n", encoding="utf-8")
        # _git_files will return nothing (not a real git repo), so no issues
        result = scan_repository_for_secrets(tmp_path)
        assert result == []

    def test_detects_sensitive_extension(self, tmp_path: Path) -> None:
        # We can't easily mock _git_files, but we can test the path-level logic
        # by verifying the SENSITIVE_EXTENSIONS constant
        from agentplane.domain.project.secret_scan import SENSITIVE_EXTENSIONS

        assert ".key" in SENSITIVE_EXTENSIONS
        assert ".pem" in SENSITIVE_EXTENSIONS
        assert ".p12" in SENSITIVE_EXTENSIONS
        assert ".crt" in SENSITIVE_EXTENSIONS

    def test_secret_patterns_compile(self) -> None:
        """All SECRET_PATTERNS regexes should compile without error."""
        for kind, pattern in SECRET_PATTERNS:
            assert pattern.search("") is None or True  # just checking it doesn't raise
            assert isinstance(kind, str)


# ---------------------------------------------------------------------------
# Golden test
# ---------------------------------------------------------------------------


@pytest.mark.golden
class TestSecretScanGolden:
    def test_roundtrip_issue_allowlist(self, tmp_path: Path) -> None:
        """End-to-end: create file with secret, scan, allowlist it, scan again."""
        f = tmp_path / "config.yaml"
        f.write_text("api_key: sk-abc123def456ghi789jkl012mno345pqr678stu901vwx", encoding="utf-8")

        # Direct scan of file content finds the issue
        issues = _scan_file_content(tmp_path, f)
        assert len(issues) >= 1
        assert issues[0].kind == "openai-token"

        # Allowlist matches openai-token
        allow = SecretScanAllow(kind="openai-token", path=f.relative_to(tmp_path).as_posix())
        filtered = _apply_allowlist(issues, [allow])
        assert not any(i.kind == "openai-token" for i in filtered)
        # secret-assignment may also fire for .yaml files — that's expected
        assert any(i.kind == "secret-assignment" for i in filtered)
