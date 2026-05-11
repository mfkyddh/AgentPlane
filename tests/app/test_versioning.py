"""Tests for agentplane.domain.app.versioning — version detection and fork sequencing."""

from __future__ import annotations

import json
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import MagicMock

import pytest

from agentplane.domain.app.versioning import (
    detect_git_short_sha,
    detect_upstream_version,
    next_fork_sequence,
)

pytestmark = pytest.mark.unit


def _mock_run(returncode: int = 0, stdout: str = "") -> MagicMock:
    mock = MagicMock()
    mock.return_value = CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")
    return mock


# ---------------------------------------------------------------------------
# detect_upstream_version
# ---------------------------------------------------------------------------


class TestDetectUpstreamVersion:
    def test_version_file_backend_cmd(self, tmp_path: Path) -> None:
        vf = tmp_path / "backend" / "cmd" / "server" / "VERSION"
        vf.parent.mkdir(parents=True)
        vf.write_text("1.2.3\n", encoding="utf-8")
        run = _mock_run()
        assert detect_upstream_version(tmp_path, run) == "1.2.3"

    def test_version_file_root(self, tmp_path: Path) -> None:
        vf = tmp_path / "VERSION"
        vf.write_text("2.0.0\n", encoding="utf-8")
        run = _mock_run()
        assert detect_upstream_version(tmp_path, run) == "2.0.0"

    def test_backend_cmd_takes_precedence(self, tmp_path: Path) -> None:
        (tmp_path / "backend" / "cmd" / "server").mkdir(parents=True)
        (tmp_path / "backend" / "cmd" / "server" / "VERSION").write_text("3.0.0", encoding="utf-8")
        (tmp_path / "VERSION").write_text("4.0.0", encoding="utf-8")
        run = _mock_run()
        assert detect_upstream_version(tmp_path, run) == "3.0.0"

    def test_package_json_fallback(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text(json.dumps({"version": "5.1.0"}), encoding="utf-8")
        run = _mock_run()
        assert detect_upstream_version(tmp_path, run) == "5.1.0"

    def test_pyproject_toml_fallback(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "test"\nversion = "6.0.0"\n',
            encoding="utf-8",
        )
        run = _mock_run()
        assert detect_upstream_version(tmp_path, run) == "6.0.0"

    def test_git_describe_fallback(self, tmp_path: Path) -> None:
        run = _mock_run(returncode=0, stdout="v7.0.0\n")
        assert detect_upstream_version(tmp_path, run) == "v7.0.0"

    def test_all_fail_raises(self, tmp_path: Path) -> None:
        run = _mock_run(returncode=128, stdout="")
        with pytest.raises(ValueError, match="无法从"):
            detect_upstream_version(tmp_path, run)

    def test_empty_version_file_skipped(self, tmp_path: Path) -> None:
        vf = tmp_path / "VERSION"
        vf.write_text("  \n", encoding="utf-8")
        run = _mock_run(returncode=0, stdout="v1.0.0\n")
        assert detect_upstream_version(tmp_path, run) == "v1.0.0"

    def test_pyproject_invalid_toml_raises(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("not valid toml [[[", encoding="utf-8")
        run = _mock_run(returncode=1, stdout="")
        with pytest.raises(ValueError, match="无法解析"):
            detect_upstream_version(tmp_path, run)

    def test_package_json_no_version_skips(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text(json.dumps({"name": "test"}), encoding="utf-8")
        run = _mock_run(returncode=0, stdout="v1.0.0\n")
        assert detect_upstream_version(tmp_path, run) == "v1.0.0"


# ---------------------------------------------------------------------------
# detect_git_short_sha
# ---------------------------------------------------------------------------


class TestDetectGitShortSha:
    def test_success(self, tmp_path: Path) -> None:
        run = _mock_run(returncode=0, stdout="abc1234\n")
        assert detect_git_short_sha(tmp_path, run) == "abc1234"

    def test_failure_raises(self, tmp_path: Path) -> None:
        run = _mock_run(returncode=128, stdout="")
        with pytest.raises(ValueError, match="无法从"):
            detect_git_short_sha(tmp_path, run)

    def test_empty_output_raises(self, tmp_path: Path) -> None:
        run = _mock_run(returncode=0, stdout="  \n")
        with pytest.raises(ValueError, match="无法从"):
            detect_git_short_sha(tmp_path, run)


# ---------------------------------------------------------------------------
# next_fork_sequence
# ---------------------------------------------------------------------------


class TestNextForkSequence:
    def test_no_ledger_returns_1(self, tmp_path: Path) -> None:
        assert next_fork_sequence(tmp_path, app_id="myapp", upstream_version="1.0", build_date="20260101") == 1

    def test_empty_ledger_returns_1(self, tmp_path: Path) -> None:
        ledger = tmp_path / "tmp" / "operation-ledger"
        ledger.mkdir(parents=True)
        (ledger / "ops.jsonl").write_text("", encoding="utf-8")
        assert next_fork_sequence(tmp_path, app_id="myapp", upstream_version="1.0", build_date="20260101") == 1

    def test_increments_from_existing(self, tmp_path: Path) -> None:
        ledger = tmp_path / "tmp" / "operation-ledger"
        ledger.mkdir(parents=True)
        entry = {
            "command": "app",
            "action": "build-artifact",
            "app_id": "myapp",
            "upstream_version": "1.0",
            "fork_version_date": "20260101",
            "fork_sequence": 3,
        }
        (ledger / "ops.jsonl").write_text(json.dumps(entry) + "\n", encoding="utf-8")
        assert next_fork_sequence(tmp_path, app_id="myapp", upstream_version="1.0", build_date="20260101") == 4

    def test_ignores_different_app(self, tmp_path: Path) -> None:
        ledger = tmp_path / "tmp" / "operation-ledger"
        ledger.mkdir(parents=True)
        entry = {
            "command": "app",
            "action": "build-artifact",
            "app_id": "other",
            "upstream_version": "1.0",
            "fork_version_date": "20260101",
            "fork_sequence": 5,
        }
        (ledger / "ops.jsonl").write_text(json.dumps(entry) + "\n", encoding="utf-8")
        assert next_fork_sequence(tmp_path, app_id="myapp", upstream_version="1.0", build_date="20260101") == 1

    def test_ignores_dry_run(self, tmp_path: Path) -> None:
        ledger = tmp_path / "tmp" / "operation-ledger"
        ledger.mkdir(parents=True)
        entry = {
            "command": "app",
            "action": "build-artifact",
            "app_id": "myapp",
            "upstream_version": "1.0",
            "fork_version_date": "20260101",
            "fork_sequence": 10,
            "dry_run": True,
        }
        (ledger / "ops.jsonl").write_text(json.dumps(entry) + "\n", encoding="utf-8")
        assert next_fork_sequence(tmp_path, app_id="myapp", upstream_version="1.0", build_date="20260101") == 1

    def test_ignores_planned_result(self, tmp_path: Path) -> None:
        ledger = tmp_path / "tmp" / "operation-ledger"
        ledger.mkdir(parents=True)
        entry = {
            "command": "app",
            "action": "build-artifact",
            "app_id": "myapp",
            "upstream_version": "1.0",
            "fork_version_date": "20260101",
            "fork_sequence": 10,
            "result": "planned",
        }
        (ledger / "ops.jsonl").write_text(json.dumps(entry) + "\n", encoding="utf-8")
        assert next_fork_sequence(tmp_path, app_id="myapp", upstream_version="1.0", build_date="20260101") == 1

    def test_ignores_corrupt_json(self, tmp_path: Path) -> None:
        ledger = tmp_path / "tmp" / "operation-ledger"
        ledger.mkdir(parents=True)
        (ledger / "ops.jsonl").write_text("not-json\n", encoding="utf-8")
        assert next_fork_sequence(tmp_path, app_id="myapp", upstream_version="1.0", build_date="20260101") == 1

    def test_ignores_non_dict_json(self, tmp_path: Path) -> None:
        ledger = tmp_path / "tmp" / "operation-ledger"
        ledger.mkdir(parents=True)
        (ledger / "ops.jsonl").write_text('"just a string"\n', encoding="utf-8")
        assert next_fork_sequence(tmp_path, app_id="myapp", upstream_version="1.0", build_date="20260101") == 1

    def test_multiple_entries_picks_max(self, tmp_path: Path) -> None:
        ledger = tmp_path / "tmp" / "operation-ledger"
        ledger.mkdir(parents=True)
        entries = [
            {"command": "app", "action": "build-artifact", "app_id": "myapp",
             "upstream_version": "1.0", "fork_version_date": "20260101", "fork_sequence": 1},
            {"command": "app", "action": "build-artifact", "app_id": "myapp",
             "upstream_version": "1.0", "fork_version_date": "20260101", "fork_sequence": 5},
        ]
        (ledger / "ops.jsonl").write_text(
            "\n".join(json.dumps(e) for e in entries) + "\n",
            encoding="utf-8",
        )
        assert next_fork_sequence(tmp_path, app_id="myapp", upstream_version="1.0", build_date="20260101") == 6


# ---------------------------------------------------------------------------
# Golden test
# ---------------------------------------------------------------------------


@pytest.mark.golden
class TestVersioningGolden:
    def test_detect_upstream_all_strategies(self, tmp_path: Path) -> None:
        """VERSION file takes precedence over package.json and pyproject.toml."""
        (tmp_path / "backend" / "cmd" / "server").mkdir(parents=True)
        (tmp_path / "backend" / "cmd" / "server" / "VERSION").write_text("10.0.0", encoding="utf-8")
        (tmp_path / "package.json").write_text(json.dumps({"version": "9.0.0"}), encoding="utf-8")
        (tmp_path / "pyproject.toml").write_text('[project]\nversion = "8.0.0"\n', encoding="utf-8")
        run = _mock_run()
        assert detect_upstream_version(tmp_path, run) == "10.0.0"
