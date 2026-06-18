"""Unit tests for onepanel_transition module."""

from __future__ import annotations

import argparse
from unittest.mock import MagicMock, patch

import pytest
from agentplane.providers.onepanel_transition import (
    _find_installed_app_id,
    _handle_app,
    _handle_project,
    build_parser,
    main,
)

pytestmark = pytest.mark.unit


class TestFindInstalledAppId:
    """Tests for _find_installed_app_id function."""

    def test_returns_install_id_when_provided(self) -> None:
        """Test that returns install_id when provided."""
        executor = MagicMock()

        result = _find_installed_app_id(executor, install_id=123, name="")

        assert result == 123

    def test_raises_when_no_install_id_and_no_name(self) -> None:
        """Test that raises when no install_id and no name."""
        executor = MagicMock()

        with pytest.raises(ValueError, match="app transition requires --install-id or --name"):
            _find_installed_app_id(executor, install_id=None, name="")

    def test_searches_by_name_when_no_install_id(self) -> None:
        """Test that searches by name when no install_id."""
        executor = MagicMock()

        with patch("agentplane.providers.onepanel_transition.search_installed_apps") as mock_search:
            mock_search.return_value = {
                "items": [
                    {"name": "test-app", "id": 456},
                    {"name": "other-app", "id": 789},
                ]
            }

            result = _find_installed_app_id(executor, install_id=None, name="test-app")

        assert result == 456
        mock_search.assert_called_once_with(executor, name="test-app")

    def test_raises_when_app_not_found(self) -> None:
        """Test that raises when app not found."""
        executor = MagicMock()

        with patch("agentplane.providers.onepanel_transition.search_installed_apps") as mock_search:
            mock_search.return_value = {
                "items": [
                    {"name": "other-app", "id": 789},
                ]
            }

            with pytest.raises(ValueError, match="installed app not found: missing-app"):
                _find_installed_app_id(executor, install_id=None, name="missing-app")

    def test_handles_empty_items(self) -> None:
        """Test that handles empty items."""
        executor = MagicMock()

        with patch("agentplane.providers.onepanel_transition.search_installed_apps") as mock_search:
            mock_search.return_value = {"items": []}

            with pytest.raises(ValueError, match="installed app not found: test-app"):
                _find_installed_app_id(executor, install_id=None, name="test-app")

    def test_handles_non_dict_payload(self) -> None:
        """Test that handles non-dict payload."""
        executor = MagicMock()

        with patch("agentplane.providers.onepanel_transition.search_installed_apps") as mock_search:
            mock_search.return_value = "invalid"

            with pytest.raises(ValueError, match="installed app not found: test-app"):
                _find_installed_app_id(executor, install_id=None, name="test-app")


class TestHandleApp:
    """Tests for _handle_app function."""

    def test_handles_app_operation(self) -> None:
        """Test that handles app operation."""
        args = argparse.Namespace(
            target="prod0-main",
            install_id=123,
            name="test-app",
            operate="start",
        )

        with patch("agentplane.providers.onepanel_transition.onepanel_target_executor") as mock_executor_cls:
            with patch("agentplane.providers.onepanel_transition.plan_installed_app_operation") as mock_plan:
                mock_executor = MagicMock()
                mock_executor_cls.return_value = mock_executor
                mock_executor.api_request.return_value = {"ok": True}

                mock_plan.return_value = MagicMock(path="/api/app/123/start", body={"action": "start"})

                result = _handle_app(args)

        assert result["scope"] == "app"
        assert result["action"] == "start"
        assert result["install_id"] == 123
        assert result["result"] == {"ok": True}


class TestHandleProject:
    """Tests for _handle_project function."""

    def test_handles_project_operation(self) -> None:
        """Test that handles project operation."""
        args = argparse.Namespace(
            target="prod0-main",
            name="test-project",
            operate="up",
        )

        with patch("agentplane.providers.onepanel_transition.onepanel_target_executor") as mock_executor_cls:
            with patch("agentplane.providers.onepanel_transition.plan_compose_project_operation") as mock_plan:
                mock_executor = MagicMock()
                mock_executor_cls.return_value = mock_executor
                mock_executor.api_request.return_value = {"ok": True}

                mock_plan.return_value = MagicMock(path="/api/project/up", body={"name": "test-project"})

                result = _handle_project(args)

        assert result["scope"] == "project"
        assert result["action"] == "up"
        assert result["name"] == "test-project"
        assert result["result"] == {"ok": True}


class TestBuildParser:
    """Tests for build_parser function."""

    def test_builds_parser_with_app_subcommand(self) -> None:
        """Test that builds parser with app subcommand."""
        parser = build_parser()

        args = parser.parse_args(["--target", "prod0-main", "app", "--operate", "start", "--install-id", "123"])

        assert args.target == "prod0-main"
        assert args.scope == "app"
        assert args.operate == "start"
        assert args.install_id == 123

    def test_builds_parser_with_project_subcommand(self) -> None:
        """Test that builds parser with project subcommand."""
        parser = build_parser()

        args = parser.parse_args(["--target", "prod0-main", "project", "--operate", "up", "--name", "test-project"])

        assert args.target == "prod0-main"
        assert args.scope == "project"
        assert args.operate == "up"
        assert args.name == "test-project"

    def test_requires_target(self) -> None:
        """Test that requires target."""
        parser = build_parser()

        with pytest.raises(SystemExit):
            parser.parse_args(["app", "--operate", "start"])

    def test_requires_scope(self) -> None:
        """Test that requires scope."""
        parser = build_parser()

        with pytest.raises(SystemExit):
            parser.parse_args(["--target", "prod0-main"])

    def test_requires_operate(self) -> None:
        """Test that requires operate."""
        parser = build_parser()

        with pytest.raises(SystemExit):
            parser.parse_args(["--target", "prod0-main", "app"])


class TestMain:
    """Tests for main function."""

    def test_returns_zero_on_success(self) -> None:
        """Test that returns zero on success."""
        with patch("agentplane.providers.onepanel_transition._handle_app") as mock_handle:
            mock_handle.return_value = {"scope": "app", "action": "start"}

            result = main(["--target", "prod0-main", "app", "--operate", "start", "--install-id", "123"])

        assert result == 0

    def test_prints_json_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test that prints JSON output."""
        with patch("agentplane.providers.onepanel_transition._handle_app") as mock_handle:
            mock_handle.return_value = {"scope": "app", "action": "start"}

            main(["--target", "prod0-main", "app", "--operate", "start", "--install-id", "123"])

        captured = capsys.readouterr()
        assert '"scope": "app"' in captured.out
        assert '"action": "start"' in captured.out
