"""Tests for cleanup module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from agentplane.domain.infra.cleanup import (
    _active_virtualenv_roots,
    _dedupe_nested_paths,
    _path_kind,
    _within_repo_root,
    apply_cleanup_plan,
    build_cleanup_plan,
)

pytestmark = pytest.mark.unit


class TestWithinRepoRoot:
    """Tests for _within_repo_root function."""

    def test_path_within_repo_root(self, tmp_path: Path) -> None:
        """Test that path within repo root returns True."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        path = repo_root / "subdir" / "file.txt"
        path.parent.mkdir()
        path.touch()

        assert _within_repo_root(path, repo_root) is True

    def test_path_outside_repo_root(self, tmp_path: Path) -> None:
        """Test that path outside repo root returns False."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        path = tmp_path / "other" / "file.txt"
        path.parent.mkdir()
        path.touch()

        assert _within_repo_root(path, repo_root) is False

    def test_path_is_repo_root(self, tmp_path: Path) -> None:
        """Test that repo root itself returns True."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()

        assert _within_repo_root(repo_root, repo_root) is True


class TestPathKind:
    """Tests for _path_kind function."""

    def test_directory_returns_dir(self, tmp_path: Path) -> None:
        """Test that directory returns 'dir'."""
        path = tmp_path / "dir"
        path.mkdir()

        assert _path_kind(path) == "dir"

    def test_file_returns_file(self, tmp_path: Path) -> None:
        """Test that file returns 'file'."""
        path = tmp_path / "file.txt"
        path.touch()

        assert _path_kind(path) == "file"

    def test_missing_path_returns_missing(self, tmp_path: Path) -> None:
        """Test that missing path returns 'missing'."""
        path = tmp_path / "missing"

        assert _path_kind(path) == "missing"


class TestDedupeNestedPaths:
    """Tests for _dedupe_nested_paths function."""

    def test_removes_nested_paths(self) -> None:
        """Test that nested paths are removed."""
        paths = [
            Path("/repo/dir"),
            Path("/repo/dir/subdir"),
            Path("/repo/dir/subdir/file.txt"),
            Path("/repo/other"),
        ]

        result = _dedupe_nested_paths(paths)

        assert len(result) == 2
        assert Path("/repo/dir") in result
        assert Path("/repo/other") in result

    def test_sorts_by_depth(self) -> None:
        """Test that paths are sorted by depth."""
        paths = [
            Path("/repo/b"),
            Path("/repo/a/b"),
            Path("/repo/a"),
        ]

        result = _dedupe_nested_paths(paths)

        assert result[0] == Path("/repo/a")
        assert result[1] == Path("/repo/b")

    def test_empty_list_returns_empty(self) -> None:
        """Test that empty list returns empty."""
        assert _dedupe_nested_paths([]) == []


class TestActiveVirtualenvRoots:
    """Tests for _active_virtualenv_roots function."""

    def test_finds_venv_from_executable(self, tmp_path: Path) -> None:
        """Test that finds venv from sys.executable."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        venv_dir = repo_root / ".venv"
        venv_dir.mkdir()
        bin_dir = venv_dir / "bin"
        bin_dir.mkdir()
        executable = bin_dir / "python"
        executable.touch()

        with patch("agentplane.domain.infra.cleanup.sys") as mock_sys:
            mock_sys.executable = str(executable)
            with patch("agentplane.domain.infra.cleanup.os.environ", {}):
                result = _active_virtualenv_roots(repo_root)

        assert venv_dir in result

    def test_finds_venv_from_virtual_env_env(self, tmp_path: Path) -> None:
        """Test that finds venv from VIRTUAL_ENV environment variable."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        venv_dir = repo_root / ".venv"
        venv_dir.mkdir()

        with patch("agentplane.domain.infra.cleanup.sys") as mock_sys:
            mock_sys.executable = "/nonexistent/python"
            with patch("agentplane.domain.infra.cleanup.os.environ", {"VIRTUAL_ENV": str(venv_dir)}):
                result = _active_virtualenv_roots(repo_root)

        assert venv_dir in result

    def test_returns_empty_when_no_venv(self, tmp_path: Path) -> None:
        """Test that returns empty set when no venv found."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()

        with patch("agentplane.domain.infra.cleanup.sys") as mock_sys:
            mock_sys.executable = "/nonexistent/python"
            with patch("agentplane.domain.infra.cleanup.os.environ", {}):
                result = _active_virtualenv_roots(repo_root)

        assert len(result) == 0


class TestBuildCleanupPlan:
    """Tests for build_cleanup_plan function."""

    def test_wsl_target_returns_temp_actions(self, tmp_path: Path) -> None:
        """Test that wsl target returns temp cleanup actions."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        temp_dir = repo_root / "tmp"
        temp_dir.mkdir()

        result = build_cleanup_plan(repo_root, "wsl")

        assert result["command"] == "cleanup plan"
        assert result["env"] == "wsl"
        assert result["action_count"] > 0
        assert any(action["type"] == "remove_temp_path" for action in result["actions"])

    def test_prod0_target_returns_sub2api_action(self, tmp_path: Path) -> None:
        """Test that prod0-main target returns sub2api action."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()

        result = build_cleanup_plan(repo_root, "prod0-main")

        assert result["command"] == "cleanup plan"
        assert result["env"] == "prod0-main"
        assert len(result["actions"]) == 1
        assert result["actions"][0]["type"] == "normalize_sub2api_paths"

    def test_unsupported_target_raises_error(self, tmp_path: Path) -> None:
        """Test that unsupported target raises ValueError."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()

        with pytest.raises(ValueError, match="Unsupported cleanup env"):
            build_cleanup_plan(repo_root, "unsupported")

    def test_wsl_target_removes_legacy_compose(self, tmp_path: Path) -> None:
        """Test that wsl target removes legacy docker-compose.yml."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        compose_root = repo_root / "infra" / "compose"
        compose_root.mkdir(parents=True)
        service_dir = compose_root / "test-service"
        service_dir.mkdir()
        legacy_compose = service_dir / "docker-compose.yml"
        legacy_compose.touch()
        legacy_env = service_dir / ".env"
        legacy_env.touch()

        result = build_cleanup_plan(repo_root, "wsl")

        assert any(action["type"] == "remove_legacy_compose" for action in result["actions"])
        assert any(action["type"] == "remove_legacy_env" for action in result["actions"])


class TestApplyCleanupPlan:
    """Tests for apply_cleanup_plan function."""

    def test_removes_temp_paths(self, tmp_path: Path) -> None:
        """Test that removes temp paths."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        temp_dir = repo_root / "tmp"
        temp_dir.mkdir()
        temp_file = temp_dir / "file.txt"
        temp_file.touch()

        result = apply_cleanup_plan(repo_root, "wsl")

        assert result["removed_count"] > 0
        assert not temp_dir.exists()

    def test_skips_non_remove_temp_path_actions(self, tmp_path: Path) -> None:
        """Test that skips non-remove_temp_path actions."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()

        result = apply_cleanup_plan(repo_root, "prod0-main")

        assert result["skipped_count"] == 1
        assert result["skipped"][0]["type"] == "normalize_sub2api_paths"

    def test_skips_missing_paths(self, tmp_path: Path) -> None:
        """Test that skips missing paths."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        temp_dir = repo_root / "tmp"
        temp_dir.mkdir()

        # Build plan first to get the path
        plan = build_cleanup_plan(repo_root, "wsl")

        # Remove the directory after building plan but before applying
        temp_dir.rmdir()

        # Mock build_cleanup_plan to return the plan with the now-missing path
        with patch("agentplane.domain.infra.cleanup.build_cleanup_plan", return_value=plan):
            result = apply_cleanup_plan(repo_root, "wsl")

        assert result["missing_count"] > 0

    def test_skips_paths_outside_repo_root(self, tmp_path: Path) -> None:
        """Test that skips paths outside repo root."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()

        # Mock _within_repo_root to return False
        with patch("agentplane.domain.infra.cleanup._within_repo_root", return_value=False):
            result = apply_cleanup_plan(repo_root, "wsl")

        # All actions should be skipped
        assert result["skipped_count"] == result["planned_count"]

    def test_skips_active_virtualenv(self, tmp_path: Path) -> None:
        """Test that skips active virtualenv."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        venv_dir = repo_root / ".venv"
        venv_dir.mkdir()

        # Mock _active_virtualenv_roots to return the venv
        with patch("agentplane.domain.infra.cleanup._active_virtualenv_roots", return_value={venv_dir}):
            result = apply_cleanup_plan(repo_root, "wsl")

        # Should skip the venv
        assert any("虚拟环境" in skip["reason"] for skip in result["skipped"])
