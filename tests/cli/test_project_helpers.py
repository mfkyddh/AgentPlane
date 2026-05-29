"""Tests for agentplane.cli.project and agentplane.cli.app — pure helper functions."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from agentplane.cli.app import _split_remote_bash_remainder
from agentplane.cli.project import (
    _PROJECTION_SURFACE_CONTRACTS,
    _run_check,
    _run_sequence_check,
    _wrap_projection,
)

pytestmark = pytest.mark.unit


def _fake_completed_process(
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=[], returncode=returncode, stdout=stdout, stderr=stderr,
    )


# ---------------------------------------------------------------------------
# _run_check
# ---------------------------------------------------------------------------


class TestRunCheck:
    def test_success(self, tmp_path: Path) -> None:
        with patch("agentplane.cli.project.subprocess.run", return_value=_fake_completed_process(0, "ok\n")):
            result = _run_check("test", ["echo", "ok"], repo_root=tmp_path)
        assert result["ok"] is True
        assert result["name"] == "test"
        assert result["returncode"] == 0
        assert "ok" in result["stdout_tail"]

    def test_failure(self, tmp_path: Path) -> None:
        with patch("agentplane.cli.project.subprocess.run", return_value=_fake_completed_process(1, "", "err")):
            result = _run_check("test", ["bad"], repo_root=tmp_path)
        assert result["ok"] is False
        assert result["returncode"] == 1

    def test_stdout_tail_truncated(self, tmp_path: Path) -> None:
        long_output = "\n".join(f"line{i}" for i in range(50))
        with patch("agentplane.cli.project.subprocess.run", return_value=_fake_completed_process(0, long_output)):
            result = _run_check("test", ["cmd"], repo_root=tmp_path)
        assert len(result["stdout_tail"]) == 20


# ---------------------------------------------------------------------------
# _run_sequence_check
# ---------------------------------------------------------------------------


class TestRunSequenceCheck:
    def test_all_pass(self, tmp_path: Path) -> None:
        with patch("agentplane.cli.project.subprocess.run", return_value=_fake_completed_process(0, "ok")):
            result = _run_sequence_check("seq", [["cmd1"], ["cmd2"]], repo_root=tmp_path)
        assert result["ok"] is True
        assert len(result["steps"]) == 2

    def test_first_fails_stops(self, tmp_path: Path) -> None:
        with patch("agentplane.cli.project.subprocess.run", return_value=_fake_completed_process(1, "", "fail")):
            result = _run_sequence_check("seq", [["cmd1"], ["cmd2"]], repo_root=tmp_path)
        assert result["ok"] is False
        assert len(result["steps"]) == 1


# ---------------------------------------------------------------------------
# _wrap_projection
# ---------------------------------------------------------------------------


class TestWrapProjection:
    def test_runtime_env(self) -> None:
        result = _wrap_projection("runtime-env", "runtime-env.plan", {"target": "wsl"})
        assert result["command"] == "project"
        assert result["surface_contract"] == "projection"
        assert result["action"] == "runtime-env.plan"
        assert result["target"] == "wsl"

    def test_verification(self) -> None:
        result = _wrap_projection("verification", "verification.run", {"ok": True})
        assert result["surface_contract"] == "observation"

    def test_fixture(self) -> None:
        result = _wrap_projection("fixture", "fixture.apply", {})
        assert result["surface_contract"] == "projection"

    def test_ledger(self) -> None:
        result = _wrap_projection("ledger", "ledger.refresh", {})
        assert result["surface_contract"] == "projection"

    def test_unknown_surface_raises(self) -> None:
        with pytest.raises(KeyError):
            _wrap_projection("unknown", "action", {})


# ---------------------------------------------------------------------------
# _PROJECTION_SURFACE_CONTRACTS
# ---------------------------------------------------------------------------


class TestProjectionSurfaceContracts:
    def test_all_surfaces(self) -> None:
        assert set(_PROJECTION_SURFACE_CONTRACTS.keys()) == {"runtime-env", "verification", "fixture", "ledger"}

    def test_contract_values(self) -> None:
        assert _PROJECTION_SURFACE_CONTRACTS["runtime-env"] == "projection"
        assert _PROJECTION_SURFACE_CONTRACTS["verification"] == "observation"


# ---------------------------------------------------------------------------
# _split_remote_bash_remainder (cli/app.py)
# ---------------------------------------------------------------------------


class TestSplitRemoteBashRemainder:
    def test_normal_argv(self) -> None:
        prefix, remainder = _split_remote_bash_remainder(["infra", "remote", "bash", "host", "--", "ls"])
        assert prefix == ["infra", "remote", "bash", "host"]
        assert remainder == ["ls"]

    def test_no_separator(self) -> None:
        argv = ["infra", "remote", "bash", "host", "ls"]
        prefix, remainder = _split_remote_bash_remainder(argv)
        assert prefix == argv
        assert remainder == []

    def test_not_remote_bash(self) -> None:
        argv = ["infra", "host", "ls"]
        prefix, remainder = _split_remote_bash_remainder(argv)
        assert prefix == argv
        assert remainder == []

    def test_separator_at_start(self) -> None:
        argv = ["--", "infra", "remote", "bash"]
        prefix, remainder = _split_remote_bash_remainder(argv)
        assert prefix == argv
        assert remainder == []

    def test_empty_argv(self) -> None:
        prefix, remainder = _split_remote_bash_remainder([])
        assert prefix == []
        assert remainder == []


# ---------------------------------------------------------------------------
# Golden test
# ---------------------------------------------------------------------------


@pytest.mark.golden
class TestProjectHelpersGolden:
    def test_run_check_and_wrap_roundtrip(self, tmp_path: Path) -> None:
        """Run check + wrap projection end-to-end."""
        with patch("agentplane.cli.project.subprocess.run", return_value=_fake_completed_process(0, "done")):
            check = _run_check("build", ["make"], repo_root=tmp_path)
        assert check["ok"] is True

        wrapped = _wrap_projection("runtime-env", "runtime-env.apply", {"result": check})
        assert wrapped["command"] == "project"
        assert wrapped["result"]["ok"] is True
