"""Unit tests for agentplane.cli.test_runner.

Covers _marker_expr, handle_test_command argument building,
tier-to-pytest-args mapping, parallel worker defaults, and edge cases.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from agentplane.cli.test_runner import (
    DEFAULT_EXCLUDES,
    _marker_expr,
    _repo_root,
    add_test_parser,
    handle_test_command,
)

pytestmark = pytest.mark.unit


def _ns(**kwargs) -> argparse.Namespace:
    defaults = {"tier": "fast", "workers": None, "tb": "short"}
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


# ---------------------------------------------------------------------------
# _marker_expr
# ---------------------------------------------------------------------------


class TestMarkerExpr:
    def test_unit_marker(self) -> None:
        expr = _marker_expr("unit")
        assert expr.startswith("(unit)")
        for marker in DEFAULT_EXCLUDES:
            assert f"not {marker}" in expr

    def test_integration_marker(self) -> None:
        expr = _marker_expr("integration")
        assert expr.startswith("(integration)")

    def test_e2e_marker(self) -> None:
        expr = _marker_expr("e2e")
        assert expr.startswith("(e2e)")

    def test_compound_marker(self) -> None:
        expr = _marker_expr("unit or integration")
        assert "(unit or integration)" in expr

    def test_all_excludes_present(self) -> None:
        expr = _marker_expr("unit")
        parts = expr.split(" and ")
        # First part is the include, rest are excludes
        exclude_parts = parts[1:]
        assert len(exclude_parts) == len(DEFAULT_EXCLUDES)
        for marker in DEFAULT_EXCLUDES:
            assert f"not {marker}" in expr

    def test_excludes_order_matches_constant(self) -> None:
        expr = _marker_expr("unit")
        for marker in DEFAULT_EXCLUDES:
            assert f"not {marker}" in expr


# ---------------------------------------------------------------------------
# handle_test_command — unit tier
# ---------------------------------------------------------------------------


def _find_marker(cmd: list[str]) -> str:
    """Find the pytest marker expression in a command list.

    Skips ``python -m`` (first ``-m``) and returns the value of the
    second ``-m`` which is the pytest marker.
    """
    first = cmd.index("-m")
    second = cmd.index("-m", first + 1)
    return cmd[second + 1]


class TestHandleTestCommandUnit:
    @patch("agentplane.cli.test_runner.subprocess.run", return_value=MagicMock(returncode=0))
    @patch("agentplane.cli.test_runner._repo_root", return_value=Path("/repo"))
    def test_unit_default_workers(self, mock_root, mock_run) -> None:
        handle_test_command(_ns(tier="unit", workers=None))
        cmd = mock_run.call_args[0][0]
        assert _find_marker(cmd).startswith("(unit)")
        assert "-n" in cmd
        assert "auto" in cmd

    @patch("agentplane.cli.test_runner.subprocess.run", return_value=MagicMock(returncode=0))
    @patch("agentplane.cli.test_runner._repo_root", return_value=Path("/repo"))
    def test_unit_explicit_workers(self, mock_root, mock_run) -> None:
        handle_test_command(_ns(tier="unit", workers=4))
        cmd = mock_run.call_args[0][0]
        assert "-n" in cmd
        n_idx = cmd.index("-n") + 1
        assert cmd[n_idx] == "4"


# ---------------------------------------------------------------------------
# handle_test_command — integration tier
# ---------------------------------------------------------------------------


class TestHandleTestCommandIntegration:
    @patch("agentplane.cli.test_runner.subprocess.run", return_value=MagicMock(returncode=0))
    @patch("agentplane.cli.test_runner._repo_root", return_value=Path("/repo"))
    def test_integration_default_workers(self, mock_root, mock_run) -> None:
        handle_test_command(_ns(tier="integration", workers=None))
        cmd = mock_run.call_args[0][0]
        assert _find_marker(cmd).startswith("(integration)")
        assert "-n" in cmd
        assert "auto" in cmd
        assert "--dist" in cmd
        assert "loadfile" in cmd

    @patch("agentplane.cli.test_runner.subprocess.run", return_value=MagicMock(returncode=0))
    @patch("agentplane.cli.test_runner._repo_root", return_value=Path("/repo"))
    def test_integration_explicit_workers_no_dist(self, mock_root, mock_run) -> None:
        handle_test_command(_ns(tier="integration", workers=2))
        cmd = mock_run.call_args[0][0]
        assert "-n" in cmd
        assert "2" in cmd
        assert "--dist" not in cmd


# ---------------------------------------------------------------------------
# handle_test_command — fast tier
# ---------------------------------------------------------------------------


class TestHandleTestCommandFast:
    @patch("agentplane.cli.test_runner.subprocess.run", return_value=MagicMock(returncode=0))
    @patch("agentplane.cli.test_runner._repo_root", return_value=Path("/repo"))
    def test_fast_includes_coverage(self, mock_root, mock_run) -> None:
        handle_test_command(_ns(tier="fast", workers=None))
        cmd = mock_run.call_args[0][0]
        assert "--cov" in cmd
        assert "--cov-report=term-missing" in cmd

    @patch("agentplane.cli.test_runner.subprocess.run", return_value=MagicMock(returncode=0))
    @patch("agentplane.cli.test_runner._repo_root", return_value=Path("/repo"))
    def test_fast_compound_marker(self, mock_root, mock_run) -> None:
        handle_test_command(_ns(tier="fast"))
        cmd = mock_run.call_args[0][0]
        assert "unit or integration" in _find_marker(cmd)

    @patch("agentplane.cli.test_runner.subprocess.run", return_value=MagicMock(returncode=0))
    @patch("agentplane.cli.test_runner._repo_root", return_value=Path("/repo"))
    def test_fast_default_workers_uses_loadfile(self, mock_root, mock_run) -> None:
        handle_test_command(_ns(tier="fast", workers=None))
        cmd = mock_run.call_args[0][0]
        assert "--dist" in cmd
        assert "loadfile" in cmd

    @patch("agentplane.cli.test_runner.subprocess.run", return_value=MagicMock(returncode=0))
    @patch("agentplane.cli.test_runner._repo_root", return_value=Path("/repo"))
    def test_fast_explicit_workers_no_dist(self, mock_root, mock_run) -> None:
        handle_test_command(_ns(tier="fast", workers=8))
        cmd = mock_run.call_args[0][0]
        assert "8" in cmd
        assert "--dist" not in cmd


# ---------------------------------------------------------------------------
# handle_test_command — e2e tier
# ---------------------------------------------------------------------------


class TestHandleTestCommandE2E:
    @patch("agentplane.cli.test_runner.subprocess.run", return_value=MagicMock(returncode=0))
    @patch("agentplane.cli.test_runner._repo_root", return_value=Path("/repo"))
    def test_e2e_default_workers_is_4(self, mock_root, mock_run) -> None:
        handle_test_command(_ns(tier="e2e", workers=None))
        cmd = mock_run.call_args[0][0]
        assert "-n" in cmd
        n_idx = cmd.index("-n") + 1
        assert cmd[n_idx] == "4"

    @patch("agentplane.cli.test_runner.subprocess.run", return_value=MagicMock(returncode=0))
    @patch("agentplane.cli.test_runner._repo_root", return_value=Path("/repo"))
    def test_e2e_explicit_workers(self, mock_root, mock_run) -> None:
        handle_test_command(_ns(tier="e2e", workers=2))
        cmd = mock_run.call_args[0][0]
        n_idx = cmd.index("-n") + 1
        assert cmd[n_idx] == "2"

    @patch("agentplane.cli.test_runner.subprocess.run", return_value=MagicMock(returncode=0))
    @patch("agentplane.cli.test_runner._repo_root", return_value=Path("/repo"))
    def test_e2e_marker(self, mock_root, mock_run) -> None:
        handle_test_command(_ns(tier="e2e"))
        cmd = mock_run.call_args[0][0]
        assert _find_marker(cmd).startswith("(e2e)")


# ---------------------------------------------------------------------------
# handle_test_command — full tier (compound)
# ---------------------------------------------------------------------------


class TestHandleTestCommandFull:
    @patch("agentplane.cli.test_runner.subprocess.run")
    @patch("agentplane.cli.test_runner._repo_root", return_value=Path("/repo"))
    def test_full_runs_fast_then_e2e(self, mock_root, mock_run) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        handle_test_command(_ns(tier="full"))
        assert mock_run.call_count == 2
        fast_cmd = mock_run.call_args_list[0][0][0]
        e2e_cmd = mock_run.call_args_list[1][0][0]
        assert "unit or integration" in str(fast_cmd)
        assert "(e2e)" in str(e2e_cmd)

    @patch("agentplane.cli.test_runner.subprocess.run")
    @patch("agentplane.cli.test_runner._repo_root", return_value=Path("/repo"))
    def test_full_skips_e2e_on_fast_failure(self, mock_root, mock_run) -> None:
        mock_run.return_value = MagicMock(returncode=1)
        result = handle_test_command(_ns(tier="full"))
        assert result == 1
        assert mock_run.call_count == 1

    @patch("agentplane.cli.test_runner.subprocess.run")
    @patch("agentplane.cli.test_runner._repo_root", return_value=Path("/repo"))
    def test_full_returns_e2e_rc(self, mock_root, mock_run) -> None:
        mock_run.side_effect = [
            MagicMock(returncode=0),
            MagicMock(returncode=2),
        ]
        result = handle_test_command(_ns(tier="full"))
        assert result == 2

    @patch("agentplane.cli.test_runner.subprocess.run")
    @patch("agentplane.cli.test_runner._repo_root", return_value=Path("/repo"))
    def test_full_e2e_workers_default_4(self, mock_root, mock_run) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        handle_test_command(_ns(tier="full", workers=None))
        e2e_cmd = mock_run.call_args_list[1][0][0]
        n_idx = e2e_cmd.index("-n") + 1
        assert e2e_cmd[n_idx] == "4"

    @patch("agentplane.cli.test_runner.subprocess.run")
    @patch("agentplane.cli.test_runner._repo_root", return_value=Path("/repo"))
    def test_full_e2e_workers_explicit(self, mock_root, mock_run) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        handle_test_command(_ns(tier="full", workers=6))
        e2e_cmd = mock_run.call_args_list[1][0][0]
        n_idx = e2e_cmd.index("-n") + 1
        assert e2e_cmd[n_idx] == "6"


# ---------------------------------------------------------------------------
# handle_test_command — common args
# ---------------------------------------------------------------------------


class TestHandleTestCommandCommon:
    @patch("agentplane.cli.test_runner.subprocess.run", return_value=MagicMock(returncode=0))
    @patch("agentplane.cli.test_runner._repo_root", return_value=Path("/repo"))
    def test_tb_flag_passed(self, mock_root, mock_run) -> None:
        handle_test_command(_ns(tier="unit", tb="long"))
        cmd = mock_run.call_args[0][0]
        assert "--tb=long" in cmd

    @patch("agentplane.cli.test_runner.subprocess.run", return_value=MagicMock(returncode=0))
    @patch("agentplane.cli.test_runner._repo_root", return_value=Path("/repo"))
    def test_q_flag_always_present(self, mock_root, mock_run) -> None:
        handle_test_command(_ns(tier="unit"))
        cmd = mock_run.call_args[0][0]
        assert "-q" in cmd

    @patch("agentplane.cli.test_runner.subprocess.run", return_value=MagicMock(returncode=0))
    @patch("agentplane.cli.test_runner._repo_root", return_value=Path("/repo"))
    def test_cwd_set_to_repo_root(self, mock_root, mock_run) -> None:
        handle_test_command(_ns(tier="unit"))
        assert mock_run.call_args[1]["cwd"] == str(Path("/repo"))

    @patch("agentplane.cli.test_runner.subprocess.run", return_value=MagicMock(returncode=0))
    @patch("agentplane.cli.test_runner._repo_root", return_value=Path("/repo"))
    def test_uses_sys_executable(self, mock_root, mock_run) -> None:
        handle_test_command(_ns(tier="unit"))
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == sys.executable

    @patch("agentplane.cli.test_runner.subprocess.run", return_value=MagicMock(returncode=0))
    @patch("agentplane.cli.test_runner._repo_root", return_value=Path("/repo"))
    def test_returns_exit_code(self, mock_root, mock_run) -> None:
        mock_run.return_value = MagicMock(returncode=42)
        result = handle_test_command(_ns(tier="unit"))
        assert result == 42


# ---------------------------------------------------------------------------
# _repo_root
# ---------------------------------------------------------------------------


class TestRepoRoot:
    def test_finds_root(self) -> None:
        root = _repo_root()
        assert (root / "pyproject.toml").is_file()

    def test_returns_path(self) -> None:
        assert isinstance(_repo_root(), Path)


# ---------------------------------------------------------------------------
# add_test_parser
# ---------------------------------------------------------------------------


class TestAddTestParser:
    def test_parser_registered(self) -> None:
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers()
        add_test_parser(sub)
        args = parser.parse_args(["test", "unit"])
        assert args.tier == "unit"

    def test_default_tier_is_fast(self) -> None:
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers()
        add_test_parser(sub)
        args = parser.parse_args(["test"])
        assert args.tier == "fast"

    def test_default_tb_is_short(self) -> None:
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers()
        add_test_parser(sub)
        args = parser.parse_args(["test"])
        assert args.tb == "short"

    def test_workers_default_none(self) -> None:
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers()
        add_test_parser(sub)
        args = parser.parse_args(["test"])
        assert args.workers is None

    def test_workers_flag(self) -> None:
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers()
        add_test_parser(sub)
        args = parser.parse_args(["test", "-n", "8"])
        assert args.workers == 8

    def test_all_tier_choices_accepted(self) -> None:
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers()
        add_test_parser(sub)
        for tier in ("fast", "full", "e2e", "unit", "integration"):
            args = parser.parse_args(["test", tier])
            assert args.tier == tier

    def test_func_set_to_handle(self) -> None:
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers()
        add_test_parser(sub)
        args = parser.parse_args(["test"])
        assert args.func is handle_test_command
