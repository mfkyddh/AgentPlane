"""Tests for agentplane.domain.project.release — pure logic, no I/O beyond tmp_path."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from agentplane.domain.project.release import (
    bump_version,
    create_release_commit_and_tag,
    determine_bump_type,
    generate_changelog_entry,
    get_commits_since_tag,
    get_current_version,
    update_changelog,
    update_pyproject_version,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# bump_version
# ---------------------------------------------------------------------------


class TestBumpVersion:
    def test_patch(self) -> None:
        assert bump_version("0.3.0", "patch") == "0.3.1"

    def test_minor(self) -> None:
        assert bump_version("0.3.0", "minor") == "0.4.0"

    def test_major(self) -> None:
        assert bump_version("0.3.0", "major") == "1.0.0"

    def test_patch_from_nonzero(self) -> None:
        assert bump_version("1.2.9", "patch") == "1.2.10"

    def test_minor_resets_patch(self) -> None:
        assert bump_version("1.2.9", "minor") == "1.3.0"

    def test_invalid_type_raises(self) -> None:
        with pytest.raises(ValueError, match="invalid bump type"):
            bump_version("1.0.0", "premajor")

    def test_zero_version(self) -> None:
        assert bump_version("0.0.0", "major") == "1.0.0"


# ---------------------------------------------------------------------------
# determine_bump_type
# ---------------------------------------------------------------------------


class TestDetermineBumpType:
    def test_patch_from_fix(self) -> None:
        commits = [{"sha": "a", "subject": "fix: bug", "body": ""}]
        assert determine_bump_type(commits) == "patch"

    def test_minor_from_feat(self) -> None:
        commits = [{"sha": "a", "subject": "feat: new thing", "body": ""}]
        assert determine_bump_type(commits) == "minor"

    def test_major_from_breaking_bang(self) -> None:
        commits = [{"sha": "a", "subject": "feat!: breaking api", "body": ""}]
        assert determine_bump_type(commits) == "major"

    def test_major_from_breaking_footer(self) -> None:
        commits = [{"sha": "a", "subject": "feat: new api", "body": "BREAKING CHANGE: removed old endpoint"}]
        assert determine_bump_type(commits) == "major"

    def test_minor_over_patch(self) -> None:
        commits = [
            {"sha": "a", "subject": "fix: bug", "body": ""},
            {"sha": "b", "subject": "feat: feature", "body": ""},
        ]
        assert determine_bump_type(commits) == "minor"

    def test_major_overrides_everything(self) -> None:
        commits = [
            {"sha": "a", "subject": "feat: feature", "body": ""},
            {"sha": "b", "subject": "fix!: breaking fix", "body": ""},
        ]
        assert determine_bump_type(commits) == "major"

    def test_override_patch(self) -> None:
        commits = [{"sha": "a", "subject": "feat: new", "body": ""}]
        assert determine_bump_type(commits, override="patch") == "patch"

    def test_override_major(self) -> None:
        commits = [{"sha": "a", "subject": "fix: bug", "body": ""}]
        assert determine_bump_type(commits, override="major") == "major"

    def test_override_invalid_raises(self) -> None:
        with pytest.raises(ValueError, match="invalid bump type"):
            determine_bump_type([], override="pre")

    def test_empty_commits_defaults_patch(self) -> None:
        assert determine_bump_type([]) == "patch"

    def test_non_conventional_defaults_patch(self) -> None:
        commits = [{"sha": "a", "subject": "random commit", "body": ""}]
        assert determine_bump_type(commits) == "patch"

    def test_scope_in_subject(self) -> None:
        commits = [{"sha": "a", "subject": "feat(cli): add command", "body": ""}]
        assert determine_bump_type(commits) == "minor"

    def test_refactor_is_patch(self) -> None:
        commits = [{"sha": "a", "subject": "refactor: cleanup", "body": ""}]
        assert determine_bump_type(commits) == "patch"

    def test_perf_is_patch(self) -> None:
        commits = [{"sha": "a", "subject": "perf: faster", "body": ""}]
        assert determine_bump_type(commits) == "patch"

    def test_docs_ignored_for_bump(self) -> None:
        commits = [{"sha": "a", "subject": "docs: update readme", "body": ""}]
        assert determine_bump_type(commits) == "patch"

    def test_chore_ignored_for_bump(self) -> None:
        commits = [{"sha": "a", "subject": "chore: cleanup", "body": ""}]
        assert determine_bump_type(commits) == "patch"


# ---------------------------------------------------------------------------
# generate_changelog_entry
# ---------------------------------------------------------------------------


class TestGenerateChangelogEntry:
    def test_basic_entry(self) -> None:
        commits = [
            {"sha": "abc1234def5678", "subject": "fix: login bug", "body": ""},
            {"sha": "def5678abc1234", "subject": "feat: new page", "body": ""},
        ]
        entry = generate_changelog_entry("0.4.0", commits)
        assert "## 0.4.0" in entry
        assert "- fix: login bug (abc1234)" in entry
        assert "- feat: new page (def5678)" in entry

    def test_empty_commits(self) -> None:
        entry = generate_changelog_entry("0.4.0", [])
        assert "## 0.4.0" in entry


# ---------------------------------------------------------------------------
# update_pyproject_version (integration with tmp_path)
# ---------------------------------------------------------------------------


class TestUpdatePyprojectVersion:
    def test_replaces_version(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            '[project]\nname = "test"\nversion = "0.1.0"\n',
            encoding="utf-8",
        )
        update_pyproject_version(tmp_path, "0.2.0")
        assert 'version = "0.2.0"' in pyproject.read_text(encoding="utf-8")

    def test_only_replaces_first(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            '[project]\nversion = "0.1.0"\n\n[tool]\nversion = "other"\n',
            encoding="utf-8",
        )
        update_pyproject_version(tmp_path, "0.2.0")
        text = pyproject.read_text(encoding="utf-8")
        assert text.count('version = "0.2.0"') == 1
        assert 'version = "other"' in text


# ---------------------------------------------------------------------------
# update_changelog (integration with tmp_path)
# ---------------------------------------------------------------------------


class TestUpdateChangelog:
    def test_inserts_after_header(self, tmp_path: Path) -> None:
        changelog = tmp_path / "CHANGELOG.md"
        changelog.write_text("# Changelog\n\n## 0.1.0\nold entry\n", encoding="utf-8")
        update_changelog(tmp_path, "## 0.2.0\nnew entry\n")
        text = changelog.read_text(encoding="utf-8")
        assert text.index("## 0.2.0") < text.index("## 0.1.0")

    def test_no_header_prepends(self, tmp_path: Path) -> None:
        changelog = tmp_path / "CHANGELOG.md"
        changelog.write_text("some content\n", encoding="utf-8")
        update_changelog(tmp_path, "## 0.2.0\nnew entry\n")
        text = changelog.read_text(encoding="utf-8")
        assert text.startswith("## 0.2.0\nnew entry\nsome content\n")


# ---------------------------------------------------------------------------
# get_current_version (integration with tmp_path)
# ---------------------------------------------------------------------------


class TestGetCurrentVersion:
    def test_reads_version(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            '[project]\nname = "x"\nversion = "1.2.3"\n',
            encoding="utf-8",
        )
        assert get_current_version(tmp_path) == "1.2.3"


# ---------------------------------------------------------------------------
# Golden test — get_commits_since_tag
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestGetCommitsSinceTag:
    def test_returns_commits(self, tmp_path: Path) -> None:
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test"],
            cwd=tmp_path,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=tmp_path,
            capture_output=True,
            check=True,
        )
        (tmp_path / "a.txt").write_text("a", encoding="utf-8")
        subprocess.run(["git", "add", "a.txt"], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "feat: initial"],
            cwd=tmp_path,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "tag", "v0.1.0"],
            cwd=tmp_path,
            capture_output=True,
            check=True,
        )
        (tmp_path / "b.txt").write_text("b", encoding="utf-8")
        subprocess.run(["git", "add", "b.txt"], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "fix: bugfix"],
            cwd=tmp_path,
            capture_output=True,
            check=True,
        )

        commits = get_commits_since_tag(tmp_path)
        assert len(commits) == 1
        assert commits[0]["subject"] == "fix: bugfix"

    def test_no_tags_returns_all(self, tmp_path: Path) -> None:
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test"],
            cwd=tmp_path,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=tmp_path,
            capture_output=True,
            check=True,
        )
        (tmp_path / "a.txt").write_text("a", encoding="utf-8")
        subprocess.run(["git", "add", "a.txt"], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "feat: first"],
            cwd=tmp_path,
            capture_output=True,
            check=True,
        )

        commits = get_commits_since_tag(tmp_path)
        assert len(commits) == 1
        assert commits[0]["subject"] == "feat: first"


@pytest.mark.integration
class TestCreateReleaseCommitAndTag:
    def test_creates_commit_and_tag(self, tmp_path: Path) -> None:
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test"],
            cwd=tmp_path,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=tmp_path,
            capture_output=True,
            check=True,
        )
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nversion = "0.1.0"\n',
            encoding="utf-8",
        )
        (tmp_path / "CHANGELOG.md").write_text("# Changelog\n\n## 0.1.0\n\n- init\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "chore: init"],
            cwd=tmp_path,
            capture_output=True,
            check=True,
        )

        (tmp_path / "pyproject.toml").write_text(
            '[project]\nversion = "0.2.0"\n',
            encoding="utf-8",
        )
        (tmp_path / "CHANGELOG.md").write_text(
            "# Changelog\n\n## 0.2.0\n\n- feat: new\n\n## 0.1.0\n\n- init\n",
            encoding="utf-8",
        )

        create_release_commit_and_tag(tmp_path, "0.2.0")

        result = subprocess.run(
            ["git", "log", "-1", "--format=%s"],
            cwd=tmp_path,
            text=True,
            capture_output=True,
            check=True,
        )
        assert result.stdout.strip() == "chore(release): v0.2.0"

        result = subprocess.run(
            ["git", "tag", "-l"],
            cwd=tmp_path,
            text=True,
            capture_output=True,
            check=True,
        )
        assert "v0.2.0" in result.stdout
