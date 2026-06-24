"""Unit tests for agentplane.cli.service module."""

from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


class TestWrap:
    """Tests for _wrap helper function."""

    def test_wrap_returns_correct_structure(self) -> None:
        from agentplane.cli.service import _wrap

        result = _wrap("search", "wsl", {"items": []})

        assert result["command"] == "service"
        assert result["action"] == "search"
        assert result["target"] == "wsl"
        assert result["payload"] == {"items": []}


class TestHandleServiceCommand:
    """Tests for handle_service_command function."""

    def test_search_action(self, tmp_path) -> None:
        from agentplane.cli.service import handle_service_command

        args = argparse.Namespace(
            service_action="search",
            target="wsl",
            repo_root=str(tmp_path),
        )

        with patch("agentplane.cli.service.search_services") as mock:
            mock.return_value = {"items": []}

            with patch("agentplane.cli.service._normalize_repo_root") as mock_norm:
                mock_norm.return_value = tmp_path

                result = handle_service_command(args)

        assert result["command"] == "service"
        assert result["action"] == "search"
        assert result["target"] == "wsl"

    def test_get_action(self, tmp_path) -> None:
        from agentplane.cli.service import handle_service_command

        args = argparse.Namespace(
            service_action="get",
            target="wsl",
            name="postgres",
            repo_root=str(tmp_path),
        )

        with patch("agentplane.cli.service.get_service") as mock:
            mock.return_value = {"name": "postgres", "status": "running"}

            with patch("agentplane.cli.service._normalize_repo_root") as mock_norm:
                mock_norm.return_value = tmp_path

                result = handle_service_command(args)

        assert result["command"] == "service"
        assert result["action"] == "get"
        assert result["payload"]["name"] == "postgres"

    def test_verify_action(self, tmp_path) -> None:
        from agentplane.cli.service import handle_service_command

        args = argparse.Namespace(
            service_action="verify",
            target="wsl",
            name="postgres",
            repo_root=str(tmp_path),
        )

        with patch("agentplane.cli.service.verify_service") as mock:
            mock.return_value = {"ok": True, "checks": []}

            with patch("agentplane.cli.service._normalize_repo_root") as mock_norm:
                mock_norm.return_value = tmp_path

                result = handle_service_command(args)

        assert result["command"] == "service"
        assert result["action"] == "verify"
        assert result["payload"]["ok"] is True

    def test_plan_action(self, tmp_path) -> None:
        from agentplane.cli.service import handle_service_command

        args = argparse.Namespace(
            service_action="plan",
            target="wsl",
            name="postgres",
            operation="restart",
            repo_root=str(tmp_path),
        )

        with patch("agentplane.cli.service.plan_service_operation") as mock:
            mock.return_value = {"ok": True, "operation": "restart"}

            with patch("agentplane.cli.service._normalize_repo_root") as mock_norm:
                mock_norm.return_value = tmp_path

                result = handle_service_command(args)

        assert result["command"] == "service"
        assert result["action"] == "plan"
        assert result["payload"]["operation"] == "restart"

    def test_apply_action(self, tmp_path) -> None:
        from agentplane.cli.service import handle_service_command

        args = argparse.Namespace(
            service_action="apply",
            target="wsl",
            name="postgres",
            operation="restart",
            execute=False,
            repo_root=str(tmp_path),
        )

        with patch("agentplane.cli.service.apply_service_operation") as mock:
            mock.return_value = {"ok": True, "operation": "restart"}

            with patch("agentplane.cli.service._normalize_repo_root") as mock_norm:
                mock_norm.return_value = tmp_path

                result = handle_service_command(args)

        assert result["command"] == "service"
        assert result["action"] == "apply"
        assert result["payload"]["operation"] == "restart"

    def test_refresh_ledger_action(self, tmp_path) -> None:
        from agentplane.cli.service import handle_service_command

        args = argparse.Namespace(
            service_action="refresh-ledger",
            target="wsl",
            write=False,
            repo_root=str(tmp_path),
        )

        with patch("agentplane.cli.service.refresh_service_ledger") as mock:
            mock.return_value = {"ok": True, "refreshed": 0}

            with patch("agentplane.cli.service._normalize_repo_root") as mock_norm:
                mock_norm.return_value = tmp_path

                result = handle_service_command(args)

        assert result["command"] == "service"
        assert result["action"] == "refresh-ledger"
        assert result["payload"]["ok"] is True

    def test_materialize_action(self, tmp_path) -> None:
        from agentplane.cli.service import handle_service_command

        args = argparse.Namespace(
            service_action="materialize",
            target="wsl",
            name="mihomo",
            artifact="client-config",
            source="default",
            output=str(tmp_path / "output.json"),
            password="test-password",
            node_name="",
            server="",
            port=None,
            sni="",
            merge_template=None,
            repo_root=str(tmp_path),
        )

        with patch("agentplane.cli.service.materialize_service") as mock:
            mock.return_value = {"ok": True, "output": str(tmp_path / "output.json")}

            with patch("agentplane.cli.service._normalize_repo_root") as mock_norm:
                mock_norm.return_value = tmp_path

                result = handle_service_command(args)

        assert result["command"] == "service"
        assert result["action"] == "materialize"
        assert result["payload"]["ok"] is True

    def test_public_endpoint_verify_action(self, tmp_path) -> None:
        from agentplane.cli.service import handle_service_command

        args = argparse.Namespace(
            service_action="public-endpoint",
            service_public_endpoint_action="verify",
            target="wsl",
            name="mihomo",
            cloudflare_env_file=str(tmp_path / ".env"),
            repo_root=str(tmp_path),
        )

        with patch("agentplane.cli.service.verify_service_public_endpoint") as mock:
            mock.return_value = {"ok": True, "checks": []}

            with patch("agentplane.cli.service._normalize_repo_root") as mock_norm:
                mock_norm.return_value = tmp_path

                result = handle_service_command(args)

        assert result["command"] == "service"
        assert result["action"] == "public-endpoint.verify"
        assert result["payload"]["ok"] is True
