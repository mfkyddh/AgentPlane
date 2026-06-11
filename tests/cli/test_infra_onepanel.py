"""Unit tests for agentplane.cli.infra_onepanel — onepanel CLI wiring.

Covers add_onepanel_parser subparser registration, handle_onepanel_command
dispatch, argument wiring for all scopes, and error handling.
"""

from __future__ import annotations

import argparse
from unittest.mock import MagicMock, patch

import pytest
from agentplane.cli.infra_onepanel import add_onepanel_parser, handle_onepanel_command

pytestmark = pytest.mark.unit

_DOMAIN_MOD = "agentplane.cli.infra_onepanel"


def _build_onepanel_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()
    add_onepanel_parser(subparsers)
    return parser


def _make_args(**kwargs: object) -> argparse.Namespace:
    return argparse.Namespace(**kwargs)


# --- add_onepanel_parser ---


class TestAddOnepanelParser:
    """Verify onepanel subparser tree structure."""

    def test_creates_onepanel_subparser(self) -> None:
        parser = _build_onepanel_parser()
        # Should parse without error
        ns = parser.parse_args(["onepanel"])
        assert hasattr(ns, "env")

    def test_env_flag_default(self) -> None:
        parser = _build_onepanel_parser()
        ns = parser.parse_args(["onepanel"])
        assert ns.env == "wsl"

    def test_env_flag_prod0_main(self) -> None:
        parser = _build_onepanel_parser()
        ns = parser.parse_args(["onepanel", "--env", "prod0-main"])
        assert ns.env == "prod0-main"

    def test_env_file_flag(self) -> None:
        parser = _build_onepanel_parser()
        ns = parser.parse_args(["onepanel", "--env-file", "/tmp/test.env"])
        assert ns.env_file == "/tmp/test.env"

    def test_json_flag(self) -> None:
        parser = _build_onepanel_parser()
        ns = parser.parse_args(["onepanel", "--json"])
        assert ns.json is True

    def test_json_flag_default_false(self) -> None:
        parser = _build_onepanel_parser()
        ns = parser.parse_args(["onepanel"])
        assert ns.json is False


class TestPanelSubparser:
    """Verify panel scope argument wiring."""

    def test_search(self) -> None:
        parser = _build_onepanel_parser()
        ns = parser.parse_args(["onepanel", "panel", "search"])
        assert ns.onepanel_scope == "panel"
        assert ns.onepanel_panel_action == "search"
        assert ns.key == ""

    def test_search_with_key(self) -> None:
        parser = _build_onepanel_parser()
        ns = parser.parse_args(["onepanel", "panel", "search", "--key", "SystemName"])
        assert ns.key == "SystemName"

    def test_plan_requires_key_and_value(self) -> None:
        parser = _build_onepanel_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["onepanel", "panel", "plan"])

    def test_plan_with_args(self) -> None:
        parser = _build_onepanel_parser()
        ns = parser.parse_args(["onepanel", "panel", "plan", "--key", "k", "--value", "v"])
        assert ns.key == "k"
        assert ns.value == "v"
        assert ns.onepanel_panel_action == "plan"
        assert callable(ns.onepanel_handler)

    def test_apply_with_execute(self) -> None:
        parser = _build_onepanel_parser()
        ns = parser.parse_args(["onepanel", "panel", "apply", "--key", "k", "--value", "v", "--execute"])
        assert ns.execute is True

    def test_refresh_ledger(self) -> None:
        parser = _build_onepanel_parser()
        ns = parser.parse_args(["onepanel", "panel", "refresh-ledger"])
        assert ns.onepanel_panel_action == "refresh-ledger"
        assert ns.repo_root == "."
        assert ns.write is False

    def test_refresh_ledger_with_write(self) -> None:
        parser = _build_onepanel_parser()
        ns = parser.parse_args(["onepanel", "panel", "refresh-ledger", "--write", "--repo-root", "/tmp"])
        assert ns.write is True
        assert ns.repo_root == "/tmp"


class TestFirewallSubparser:
    """Verify firewall scope argument wiring."""

    def test_search_defaults(self) -> None:
        parser = _build_onepanel_parser()
        ns = parser.parse_args(["onepanel", "firewall", "search"])
        assert ns.onepanel_firewall_action == "search"
        assert ns.type == "port"
        assert ns.info == ""
        assert ns.status == ""
        assert ns.strategy == ""

    def test_search_with_filters(self) -> None:
        parser = _build_onepanel_parser()
        ns = parser.parse_args(
            [
                "onepanel",
                "firewall",
                "search",
                "--type",
                "address",
                "--info",
                "test",
                "--status",
                "1",
                "--strategy",
                "accept",
            ]
        )
        assert ns.type == "address"
        assert ns.info == "test"
        assert ns.status == "1"
        assert ns.strategy == "accept"

    def test_get_default_tab(self) -> None:
        parser = _build_onepanel_parser()
        ns = parser.parse_args(["onepanel", "firewall", "get"])
        assert ns.tab == "port"

    def test_get_with_tab(self) -> None:
        parser = _build_onepanel_parser()
        ns = parser.parse_args(["onepanel", "firewall", "get", "--tab", "forward"])
        assert ns.tab == "forward"

    def test_verify(self) -> None:
        parser = _build_onepanel_parser()
        ns = parser.parse_args(["onepanel", "firewall", "verify", "--expected-active", "true"])
        assert ns.expected_active == "true"

    def test_plan_requires_operation(self) -> None:
        parser = _build_onepanel_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["onepanel", "firewall", "plan"])

    def test_plan_with_operation(self) -> None:
        parser = _build_onepanel_parser()
        ns = parser.parse_args(["onepanel", "firewall", "plan", "--operation", "start"])
        assert ns.operation == "start"
        assert ns.with_docker_restart is False
        assert callable(ns.onepanel_handler)

    def test_apply_with_docker_restart(self) -> None:
        parser = _build_onepanel_parser()
        ns = parser.parse_args(["onepanel", "firewall", "apply", "--operation", "restart", "--with-docker-restart"])
        assert ns.with_docker_restart is True

    def test_refresh_ledger(self) -> None:
        parser = _build_onepanel_parser()
        ns = parser.parse_args(["onepanel", "firewall", "refresh-ledger"])
        assert ns.onepanel_firewall_action == "refresh-ledger"


class TestCronjobSubparser:
    """Verify cronjob scope argument wiring."""

    def test_search(self) -> None:
        parser = _build_onepanel_parser()
        ns = parser.parse_args(["onepanel", "cronjob", "search", "--info", "backup"])
        assert ns.onepanel_cronjob_action == "search"
        assert ns.info == "backup"

    def test_get_requires_id(self) -> None:
        parser = _build_onepanel_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["onepanel", "cronjob", "get"])

    def test_get_with_id(self) -> None:
        parser = _build_onepanel_parser()
        ns = parser.parse_args(["onepanel", "cronjob", "get", "--id", "42"])
        assert ns.id == 42
        assert callable(ns.onepanel_handler)

    def test_plan_requires_mode_and_body(self) -> None:
        parser = _build_onepanel_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["onepanel", "cronjob", "plan"])

    def test_plan_with_args(self) -> None:
        parser = _build_onepanel_parser()
        ns = parser.parse_args(
            [
                "onepanel",
                "cronjob",
                "plan",
                "--mode",
                "create",
                "--body-json",
                '{"name":"t"}',
            ]
        )
        assert ns.mode == "create"
        assert ns.body_json == '{"name":"t"}'

    def test_verify(self) -> None:
        parser = _build_onepanel_parser()
        ns = parser.parse_args(["onepanel", "cronjob", "verify", "--id", "5", "--expected-status", "active"])
        assert ns.id == 5
        assert ns.expected_status == "active"


class TestTaskSubparser:
    """Verify task scope argument wiring."""

    def test_search_defaults(self) -> None:
        parser = _build_onepanel_parser()
        ns = parser.parse_args(["onepanel", "task", "search"])
        assert ns.onepanel_task_action == "search"
        assert ns.type == ""
        assert ns.status == ""

    def test_search_with_filters(self) -> None:
        parser = _build_onepanel_parser()
        ns = parser.parse_args(["onepanel", "task", "search", "--type", "cronjob", "--status", "Executing"])
        assert ns.type == "cronjob"
        assert ns.status == "Executing"

    def test_get(self) -> None:
        parser = _build_onepanel_parser()
        ns = parser.parse_args(["onepanel", "task", "get"])
        assert ns.onepanel_task_action == "get"
        assert callable(ns.onepanel_handler)

    def test_verify_with_expected_count(self) -> None:
        parser = _build_onepanel_parser()
        ns = parser.parse_args(["onepanel", "task", "verify", "--expected-count", "3"])
        assert ns.expected_count == 3

    def test_verify_without_expected_count(self) -> None:
        parser = _build_onepanel_parser()
        ns = parser.parse_args(["onepanel", "task", "verify"])
        assert ns.expected_count is None

    def test_refresh_ledger(self) -> None:
        parser = _build_onepanel_parser()
        ns = parser.parse_args(["onepanel", "task", "refresh-ledger"])
        assert ns.onepanel_task_action == "refresh-ledger"


# --- handle_onepanel_command ---


class TestHandleOnepanelCommand:
    """Verify command dispatch and error handling."""

    @patch(f"{_DOMAIN_MOD}.onepanel_skeleton")
    def test_skeleton_when_no_handler(self, mock_skeleton: MagicMock) -> None:
        mock_skeleton.return_value = {"status": "skeleton", "env": "wsl"}
        args = _make_args(env="wsl")
        result = handle_onepanel_command(args)
        mock_skeleton.assert_called_once_with("wsl")
        assert result["status"] == "skeleton"

    @patch(f"{_DOMAIN_MOD}.record_onepanel_operation")
    @patch(f"{_DOMAIN_MOD}.handle_panel_action")
    def test_dispatches_panel_handler(self, mock_handler: MagicMock, mock_record: MagicMock) -> None:
        mock_handler.return_value = {"scope": "panel", "action": "search"}
        mock_record.return_value = {"scope": "panel", "action": "search", "operation": {"op_id": "1"}}
        args = _make_args(env="wsl", onepanel_handler=mock_handler)
        result = handle_onepanel_command(args)
        mock_handler.assert_called_once_with(args)
        mock_record.assert_called_once_with(args, mock_handler.return_value)
        assert result["operation"]["op_id"] == "1"

    @patch(f"{_DOMAIN_MOD}.record_onepanel_operation")
    @patch(f"{_DOMAIN_MOD}.handle_firewall_action")
    def test_dispatches_firewall_handler(self, mock_handler: MagicMock, mock_record: MagicMock) -> None:
        mock_handler.return_value = {"scope": "firewall", "action": "get"}
        mock_record.return_value = {"scope": "firewall", "action": "get", "operation": {"op_id": "2"}}
        args = _make_args(env="prod0-main", onepanel_handler=mock_handler)
        result = handle_onepanel_command(args)
        mock_handler.assert_called_once_with(args)
        assert result["operation"]["op_id"] == "2"

    @patch(f"{_DOMAIN_MOD}.record_onepanel_operation")
    @patch(f"{_DOMAIN_MOD}.handle_cronjob_action")
    def test_dispatches_cronjob_handler(self, mock_handler: MagicMock, mock_record: MagicMock) -> None:
        mock_handler.return_value = {"scope": "cronjob", "action": "search"}
        mock_record.return_value = {"scope": "cronjob", "action": "search", "operation": {"op_id": "3"}}
        args = _make_args(env="wsl", onepanel_handler=mock_handler)
        handle_onepanel_command(args)
        mock_handler.assert_called_once_with(args)

    @patch(f"{_DOMAIN_MOD}.record_onepanel_operation")
    @patch(f"{_DOMAIN_MOD}.handle_task_action")
    def test_dispatches_task_handler(self, mock_handler: MagicMock, mock_record: MagicMock) -> None:
        mock_handler.return_value = {"scope": "task", "action": "get"}
        mock_record.return_value = {"scope": "task", "action": "get", "operation": {"op_id": "4"}}
        args = _make_args(env="wsl", onepanel_handler=mock_handler)
        handle_onepanel_command(args)
        mock_handler.assert_called_once_with(args)

    @patch(f"{_DOMAIN_MOD}.onepanel_skeleton")
    def test_skeleton_when_handler_not_callable(self, mock_skeleton: MagicMock) -> None:
        mock_skeleton.return_value = {"status": "skeleton", "env": "prod0-main"}
        args = _make_args(env="prod0-main", onepanel_handler="not_callable")
        handle_onepanel_command(args)
        mock_skeleton.assert_called_once_with("prod0-main")

    @patch(f"{_DOMAIN_MOD}.onepanel_skeleton")
    def test_skeleton_when_handler_is_none(self, mock_skeleton: MagicMock) -> None:
        mock_skeleton.return_value = {"status": "skeleton", "env": "wsl"}
        args = _make_args(env="wsl", onepanel_handler=None)
        handle_onepanel_command(args)
        mock_skeleton.assert_called_once_with("wsl")

    def test_writes_stderr_warning(self, capsys: pytest.CaptureFixture[str]) -> None:
        args = _make_args(env="wsl")
        with patch(f"{_DOMAIN_MOD}.onepanel_skeleton", return_value={"status": "skeleton", "env": "wsl"}):
            handle_onepanel_command(args)
        captured = capsys.readouterr()
        assert "onepanel" in captured.err
