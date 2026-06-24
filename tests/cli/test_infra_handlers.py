"""Tests for agentplane.cli.infra_handlers module."""

from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


class TestWrap:
    """Tests for _wrap helper function."""

    def test_wrap_returns_correct_structure(self) -> None:
        from agentplane.cli.infra_handlers import _wrap

        result = _wrap(action="test", target="wsl", payload={"key": "value"})

        assert result["command"] == "infra"
        assert result["action"] == "test"
        assert result["target"] == "wsl"
        assert result["payload"] == {"key": "value"}


class TestWithoutPublicEnvelope:
    """Tests for _without_public_envelope helper function."""

    def test_removes_envelope_keys(self) -> None:
        from agentplane.cli.infra_handlers import _without_public_envelope

        payload = {
            "command": "infra",
            "action": "test",
            "target": "wsl",
            "env": "production",
            "repo_root": "/tmp",
            "inventory_file": "/tmp/inventory.json",
            "key": "value",
        }

        result = _without_public_envelope(payload)

        assert "command" not in result
        assert "action" not in result
        assert "target" not in result
        assert "env" not in result
        assert "repo_root" not in result
        assert "inventory_file" not in result
        assert result["key"] == "value"

    def test_returns_empty_for_empty_payload(self) -> None:
        from agentplane.cli.infra_handlers import _without_public_envelope

        result = _without_public_envelope({})

        assert result == {}


class TestHandleBootstrap:
    """Tests for _handle_bootstrap function."""

    def test_inspect_local(self, tmp_path) -> None:
        from agentplane.cli.infra_handlers import _handle_bootstrap

        args = argparse.Namespace(infra_bootstrap_action="inspect-local")

        with patch("agentplane.cli.infra_handlers.run_inspect_local") as mock:
            mock.return_value = {"ok": True, "checks": []}

            result = _handle_bootstrap(args, tmp_path)

        assert result["command"] == "infra"
        assert result["action"] == "bootstrap.inspect-local"
        assert result["target"] == "local"

    def test_init_secrets(self, tmp_path) -> None:
        from agentplane.cli.infra_handlers import _handle_bootstrap

        args = argparse.Namespace(infra_bootstrap_action="init-secrets")

        with patch("agentplane.cli.infra_handlers.init_secrets") as mock:
            mock.return_value = {"ok": True}

            result = _handle_bootstrap(args, tmp_path)

        assert result["action"] == "bootstrap.init-secrets"

    def test_verify_secrets(self, tmp_path) -> None:
        from agentplane.cli.infra_handlers import _handle_bootstrap

        args = argparse.Namespace(infra_bootstrap_action="verify-secrets")

        with patch("agentplane.cli.infra_handlers.run_verify_secrets") as mock:
            mock.return_value = {"ok": True}

            result = _handle_bootstrap(args, tmp_path)

        assert result["action"] == "bootstrap.verify-secrets"

    def test_doctor(self, tmp_path) -> None:
        from agentplane.cli.infra_handlers import _handle_bootstrap

        args = argparse.Namespace(infra_bootstrap_action="doctor")

        with patch("agentplane.cli.infra_handlers.run_doctor") as mock:
            mock.return_value = {"ok": True}

            result = _handle_bootstrap(args, tmp_path)

        assert result["action"] == "bootstrap.doctor"

    def test_raises_on_unsupported_action(self, tmp_path) -> None:
        from agentplane.cli.infra_handlers import _handle_bootstrap

        args = argparse.Namespace(infra_bootstrap_action="unsupported")

        with pytest.raises(ValueError, match="Unsupported bootstrap action"):
            _handle_bootstrap(args, tmp_path)


class TestHandleInfraCommand:
    """Tests for handle_infra_command function."""

    def test_local_action(self) -> None:
        from agentplane.cli.infra_handlers import handle_infra_command

        args = argparse.Namespace(infra_action="local")

        with patch("agentplane.cli.infra_handlers.handle_local_infra_command") as mock:
            mock.return_value = ("local.test", {"ok": True})

            result = handle_infra_command(args)

        assert result["command"] == "infra"
        assert result["action"] == "local.test"
        assert result["target"] == "local"

    def test_inventory_action(self, tmp_path) -> None:
        from agentplane.cli.infra_handlers import handle_infra_command

        args = argparse.Namespace(
            infra_action="inventory",
            target="wsl",
            write=False,
            repo_root=str(tmp_path),
        )

        with patch("agentplane.cli.infra_handlers.generate_inventory_snapshot") as mock:
            mock.return_value = {
                "payload": {"hostname": "test"},
                "inventory_file": "/tmp/inventory.json",
                "backend_type": "wsl",
            }

            with patch("agentplane.cli.infra_handlers._normalize_repo_root") as mock_norm:
                mock_norm.return_value = tmp_path

                result = handle_infra_command(args)

        assert result["action"] == "inventory"
        assert result["target"] == "wsl"

    def test_audit_action(self, tmp_path) -> None:
        from agentplane.cli.infra_handlers import handle_infra_command

        args = argparse.Namespace(
            infra_action="audit",
            target="wsl",
            write=False,
            repo_root=str(tmp_path),
        )

        with patch("agentplane.cli.infra_handlers.audit_filesystem") as mock:
            mock.return_value = {"ok": True, "checks": [], "violations": [], "path_check_mode": "strict"}

            with patch("agentplane.cli.infra_handlers._normalize_repo_root") as mock_norm:
                mock_norm.return_value = tmp_path

                result = handle_infra_command(args)

        assert result["action"] == "audit"
        assert result["target"] == "wsl"

    def test_health_action(self, tmp_path) -> None:
        from agentplane.cli.infra_handlers import handle_infra_command

        args = argparse.Namespace(
            infra_action="health",
            target="wsl",
            repo_root=str(tmp_path),
        )

        with patch("agentplane.cli.infra_handlers.check_infra_health") as mock:
            mock.return_value = {"ok": True, "checks": []}

            with patch("agentplane.cli.infra_handlers._normalize_repo_root") as mock_norm:
                mock_norm.return_value = tmp_path

                result = handle_infra_command(args)

        assert result["action"] == "health"
        assert result["target"] == "wsl"

    def test_bootstrap_action(self, tmp_path) -> None:
        from agentplane.cli.infra_handlers import handle_infra_command

        args = argparse.Namespace(
            infra_action="bootstrap",
            infra_bootstrap_action="inspect-local",
            repo_root=str(tmp_path),
        )

        with patch("agentplane.cli.infra_handlers.run_inspect_local") as mock:
            mock.return_value = {"ok": True, "checks": []}

            with patch("agentplane.cli.infra_handlers._normalize_repo_root") as mock_norm:
                mock_norm.return_value = tmp_path

                result = handle_infra_command(args)

        assert result["action"] == "bootstrap.inspect-local"
        assert result["target"] == "local"
