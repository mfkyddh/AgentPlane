"""Unit tests for agentplane.cli.app — CLI entry point.

Covers build_parser, _split_remote_bash_remainder, _emit,
and main() command dispatch with mocked handlers.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from agentplane.cli.app import _emit, _split_remote_bash_remainder, build_parser, main

pytestmark = pytest.mark.unit


class TestSplitRemoteBashRemainder:
    """Tests for the remote bash argument splitter."""

    def test_non_remote_command_passthrough(self) -> None:
        argv = ["infra", "host", "list"]
        prefix, remainder = _split_remote_bash_remainder(argv)
        assert prefix == argv
        assert remainder == []

    def test_remote_bash_with_separator(self) -> None:
        argv = ["infra", "remote", "bash", "--target", "prod0", "--", "ls", "-la"]
        prefix, remainder = _split_remote_bash_remainder(argv)
        assert prefix == ["infra", "remote", "bash", "--target", "prod0"]
        assert remainder == ["ls", "-la"]

    def test_remote_bash_without_separator(self) -> None:
        argv = ["infra", "remote", "bash", "--target", "prod0"]
        prefix, remainder = _split_remote_bash_remainder(argv)
        assert prefix == argv
        assert remainder == []

    def test_empty_argv(self) -> None:
        prefix, remainder = _split_remote_bash_remainder([])
        assert prefix == []
        assert remainder == []

    def test_separator_before_prefix(self) -> None:
        argv = ["--", "infra", "remote", "bash"]
        prefix, remainder = _split_remote_bash_remainder(argv)
        assert prefix == argv
        assert remainder == []


class TestBuildParser:
    """Verify all subcommands are registered."""

    def test_parser_has_all_subcommands(self) -> None:
        parser = build_parser()
        # Verify parser can be created without error
        assert parser is not None

    def test_parser_infra_subcommand(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["infra", "inventory", "wsl"])
        assert args.command == "infra"
        assert args.infra_action == "inventory"

    def test_parser_project_subcommand(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["project", "status"])
        assert args.command == "project"

    def test_parser_test_subcommand(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["test", "unit"])
        assert args.command == "test"

    def test_parser_web_subcommand(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["web"])
        assert args.command == "web"

    def test_parser_unknown_command_exits(self) -> None:
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["unknown"])


class TestEmit:
    """Test JSON output helper."""

    def test_emit_outputs_json(self, capsys) -> None:
        _emit({"key": "value"})
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed == {"key": "value"}

    def test_emit_handles_unicode(self, capsys) -> None:
        _emit({"name": "test"})
        captured = capsys.readouterr()
        assert "test" in captured.out


class TestMainDispatch:
    """Test main() command dispatch with mocked handlers."""

    @patch("agentplane.cli.app.handle_test_command")
    def test_main_test_command(self, mock_handler) -> None:
        mock_handler.return_value = 0
        result = main(["test", "unit"])
        assert result == 0
        mock_handler.assert_called_once()

    @patch("agentplane.cli.app.handle_project_command")
    def test_main_project_command_success(self, mock_handler) -> None:
        mock_handler.return_value = {"ok": True}
        result = main(["project", "status"])
        assert result == 0

    @patch("agentplane.cli.app.handle_project_command")
    def test_main_project_command_failure(self, mock_handler) -> None:
        mock_handler.return_value = {"ok": False}
        result = main(["project", "status"])
        assert result == 1

    @patch("agentplane.cli.app.handle_project_command")
    def test_main_project_command_value_error(self, mock_handler) -> None:
        mock_handler.side_effect = ValueError("bad input")
        result = main(["project", "status"])
        assert result == 1

    @patch("agentplane.cli.app.handle_web_command")
    def test_main_web_command(self, mock_handler) -> None:
        mock_handler.return_value = 0
        with patch("agentplane.cli.app.build_parser") as mock_build:
            mock_parser = MagicMock()
            mock_args = MagicMock()
            mock_args.command = "web"
            mock_parser.parse_args.return_value = mock_args
            mock_build.return_value = mock_parser
            result = main(["web"])
            assert result == 0

    @patch("agentplane.cli.app.handle_infra_command")
    def test_main_infra_remote_bash_ok(self, mock_handler) -> None:
        mock_handler.return_value = {"action": "remote.bash", "payload": {"ok": True}}
        with patch("agentplane.cli.app.build_parser") as mock_build:
            mock_parser = MagicMock()
            mock_args = MagicMock()
            mock_args.command = "infra"
            mock_args.infra_action = "remote"
            mock_args.infra_remote_action = "bash"
            mock_args.remote_args = []
            mock_parser.parse_args.return_value = mock_args
            mock_build.return_value = mock_parser
            result = main(["infra", "remote", "bash", "--target", "wsl"])
            assert result == 0

    @patch("agentplane.cli.app.handle_infra_command")
    def test_main_infra_remote_bash_fail(self, mock_handler) -> None:
        mock_handler.return_value = {"action": "remote.bash", "payload": {"ok": False}}
        with patch("agentplane.cli.app.build_parser") as mock_build:
            mock_parser = MagicMock()
            mock_args = MagicMock()
            mock_args.command = "infra"
            mock_args.infra_action = "remote"
            mock_args.infra_remote_action = "bash"
            mock_args.remote_args = []
            mock_parser.parse_args.return_value = mock_args
            mock_build.return_value = mock_parser
            result = main(["infra", "remote", "bash", "--target", "wsl"])
            assert result == 1

    @patch("agentplane.cli.app.handle_infra_command")
    def test_main_infra_value_error(self, mock_handler) -> None:
        mock_handler.side_effect = ValueError("bad")
        with patch("agentplane.cli.app.build_parser") as mock_build:
            mock_parser = MagicMock()
            mock_args = MagicMock()
            mock_args.command = "infra"
            mock_args.infra_action = "health"
            mock_parser.parse_args.return_value = mock_args
            mock_build.return_value = mock_parser
            result = main(["infra", "health", "--target", "wsl"])
            assert result == 1

    @patch("agentplane.cli.app.handle_service_command")
    def test_main_service_verify_ok(self, mock_handler) -> None:
        mock_handler.return_value = {"payload": {"ok": True}}
        # Need to mock args properly
        with patch("agentplane.cli.app.build_parser") as mock_build:
            mock_parser = MagicMock()
            mock_args = MagicMock()
            mock_args.command = "service"
            mock_args.service_action = "verify"
            mock_parser.parse_args.return_value = mock_args
            mock_build.return_value = mock_parser
            result = main(["service", "verify"])
            assert result == 0
