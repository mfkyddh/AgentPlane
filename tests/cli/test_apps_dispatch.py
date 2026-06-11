"""Unit tests for agentplane.cli.apps — delivery dispatch routing.

Covers handle_app_command routing to delivery surface actions,
_ensure_formal_delivery_action_contract validation, and error handling
for invalid actions.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import patch

import pytest
from agentplane.cli.apps import (
    DELIVERY_EXECUTION_MODE_ACTIONS,
    DELIVERY_LIFECYCLE_ACTIONS,
    DELIVERY_WRITE_ACTIONS,
    _ensure_formal_delivery_action_contract,
    handle_app_command,
)
from agentplane.domain.app import delivery_handlers

pytestmark = pytest.mark.unit

TARGET = "prod0-main"
APP = "sub2api"


def _ns(**kwargs) -> argparse.Namespace:
    defaults = {
        "repo_root": ".",
        "app_surface": "delivery",
        "app_delivery_action": "deploy",
        "target": TARGET,
        "app": APP,
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


# ---------------------------------------------------------------------------
# _ensure_formal_delivery_action_contract
# ---------------------------------------------------------------------------


class TestEnsureFormalDeliveryActionContract:
    def test_skips_non_formal_action(self) -> None:
        args = _ns(app_delivery_action="not-a-real-action")
        _ensure_formal_delivery_action_contract(args)

    @pytest.mark.parametrize("action", DELIVERY_EXECUTION_MODE_ACTIONS)
    def test_execution_mode_requires_exactly_one_flag(self, action: str) -> None:
        args = _ns(app_delivery_action=action, dry_run=False, execute=False)
        with pytest.raises(ValueError, match="显式二选一"):
            _ensure_formal_delivery_action_contract(args)

    @pytest.mark.parametrize("action", DELIVERY_EXECUTION_MODE_ACTIONS)
    def test_execution_mode_rejects_both_flags(self, action: str) -> None:
        args = _ns(app_delivery_action=action, dry_run=True, execute=True)
        with pytest.raises(ValueError, match="显式二选一"):
            _ensure_formal_delivery_action_contract(args)

    @pytest.mark.parametrize("action", DELIVERY_EXECUTION_MODE_ACTIONS)
    def test_execution_mode_accepts_dry_run(self, action: str) -> None:
        args = _ns(app_delivery_action=action, dry_run=True, execute=False)
        _ensure_formal_delivery_action_contract(args)

    @pytest.mark.parametrize("action", DELIVERY_EXECUTION_MODE_ACTIONS)
    def test_execution_mode_accepts_execute(self, action: str) -> None:
        args = _ns(app_delivery_action=action, dry_run=False, execute=True)
        _ensure_formal_delivery_action_contract(args)

    @pytest.mark.parametrize("action", DELIVERY_WRITE_ACTIONS)
    def test_write_actions_require_write_flag(self, action: str) -> None:
        args = _ns(app_delivery_action=action, write=False)
        with pytest.raises(ValueError, match="--write"):
            _ensure_formal_delivery_action_contract(args)

    @pytest.mark.parametrize("action", DELIVERY_WRITE_ACTIONS)
    def test_write_actions_accept_write_flag(self, action: str) -> None:
        args = _ns(app_delivery_action=action, write=True)
        _ensure_formal_delivery_action_contract(args)

    @pytest.mark.parametrize("action", DELIVERY_LIFECYCLE_ACTIONS)
    def test_lifecycle_requires_exactly_one_flag(self, action: str) -> None:
        args = _ns(app_delivery_action=action, dry_run=False, write=False)
        with pytest.raises(ValueError, match="显式二选一"):
            _ensure_formal_delivery_action_contract(args)

    @pytest.mark.parametrize("action", DELIVERY_LIFECYCLE_ACTIONS)
    def test_lifecycle_rejects_both_flags(self, action: str) -> None:
        args = _ns(app_delivery_action=action, dry_run=True, write=True)
        with pytest.raises(ValueError, match="显式二选一"):
            _ensure_formal_delivery_action_contract(args)

    @pytest.mark.parametrize("action", DELIVERY_LIFECYCLE_ACTIONS)
    def test_lifecycle_accepts_dry_run(self, action: str) -> None:
        args = _ns(app_delivery_action=action, dry_run=True, write=False)
        _ensure_formal_delivery_action_contract(args)

    @pytest.mark.parametrize("action", DELIVERY_LIFECYCLE_ACTIONS)
    def test_lifecycle_accepts_write(self, action: str) -> None:
        args = _ns(app_delivery_action=action, dry_run=False, write=True)
        _ensure_formal_delivery_action_contract(args)


# ---------------------------------------------------------------------------
# handle_app_command — delivery surface routing
# ---------------------------------------------------------------------------


class TestDeliveryRouting:
    @patch("agentplane.cli.apps._ensure_formal_delivery_action_contract")
    @patch("agentplane.cli.apps._normalize_repo_root", return_value=Path("/repo"))
    def test_deploy_dry_run(self, _root, _contract) -> None:
        with patch.object(delivery_handlers, "deploy_for_app", return_value={"ok": True}) as mock:
            args = _ns(app_delivery_action="deploy", dry_run=True, execute=False, image_ref=None)
            result = handle_app_command(args)
        mock.assert_called_once_with(
            Path("/repo"), target=TARGET, app=APP, image_ref=None,
            dry_run=True, execute=False, app_repo_root=None,
        )
        assert result == {"ok": True}

    @patch("agentplane.cli.apps._ensure_formal_delivery_action_contract")
    @patch("agentplane.cli.apps._normalize_repo_root", return_value=Path("/repo"))
    def test_deploy_execute(self, _root, _contract) -> None:
        with patch.object(delivery_handlers, "deploy_for_app", return_value={"ok": True}) as mock:
            args = _ns(app_delivery_action="deploy", dry_run=False, execute=True, image_ref="img:v1")
            handle_app_command(args)
        mock.assert_called_once_with(
            Path("/repo"), target=TARGET, app=APP, image_ref="img:v1",
            dry_run=False, execute=True, app_repo_root=None,
        )

    @patch("agentplane.cli.apps._ensure_formal_delivery_action_contract")
    @patch("agentplane.cli.apps._normalize_repo_root", return_value=Path("/repo"))
    def test_verify(self, _root, _contract) -> None:
        with patch.object(delivery_handlers, "verify_delivery_for_app", return_value={"ok": True}) as mock:
            args = _ns(app_delivery_action="verify", dry_run=True, execute=False)
            handle_app_command(args)
        mock.assert_called_once_with(
            Path("/repo"), target=TARGET, app=APP, dry_run=True, execute=False, app_repo_root=None,
        )

    @patch("agentplane.cli.apps._ensure_formal_delivery_action_contract")
    @patch("agentplane.cli.apps._normalize_repo_root", return_value=Path("/repo"))
    def test_rollback(self, _root, _contract) -> None:
        with patch.object(delivery_handlers, "rollback_for_app", return_value={"ok": True}) as mock:
            args = _ns(app_delivery_action="rollback", dry_run=False, execute=True)
            handle_app_command(args)
        mock.assert_called_once_with(
            Path("/repo"), target=TARGET, app=APP, dry_run=False, execute=True, app_repo_root=None,
        )

    @patch("agentplane.cli.apps._ensure_formal_delivery_action_contract")
    @patch("agentplane.cli.apps._normalize_repo_root", return_value=Path("/repo"))
    def test_onboard_dry_run(self, _root, _contract) -> None:
        with patch.object(delivery_handlers, "onboard_for_app", return_value={"ok": True}) as mock:
            args = _ns(
                app_delivery_action="onboard", dry_run=True, write=False,
                app_repo_root="/ar", repo_name="rn", contract_path="c.yaml",
            )
            result = handle_app_command(args)
        mock.assert_called_once_with(
            Path("/repo"), target=TARGET, app=APP,
            dry_run=True, write=False, app_repo_root="/ar",
            repo_name="rn", contract_path="c.yaml",
        )
        assert result == {"ok": True}

    @patch("agentplane.cli.apps._ensure_formal_delivery_action_contract")
    @patch("agentplane.cli.apps._normalize_repo_root", return_value=Path("/repo"))
    def test_offboard_write(self, _root, _contract) -> None:
        with patch.object(delivery_handlers, "offboard_for_app", return_value={"ok": True}) as mock:
            args = _ns(app_delivery_action="offboard", dry_run=False, write=True)
            handle_app_command(args)
        mock.assert_called_once_with(
            Path("/repo"), target=TARGET, app=APP, dry_run=False, write=True,
        )

    @patch("agentplane.cli.apps._ensure_formal_delivery_action_contract")
    @patch("agentplane.cli.apps._normalize_repo_root", return_value=Path("/repo"))
    def test_validate_contract_standalone(self, _root, _contract) -> None:
        with patch.object(delivery_handlers, "validate_contract_standalone_for_app", return_value={"ok": True}) as mock:
            args = _ns(
                app_delivery_action="validate-contract", standalone=True,
                contract_path="/tmp/contract.yaml",
            )
            result = handle_app_command(args)
        mock.assert_called_once_with(
            Path("/tmp/contract.yaml"), repo_root=Path("/repo"),
        )
        assert result == {"ok": True}

    @patch("agentplane.cli.apps._ensure_formal_delivery_action_contract")
    @patch("agentplane.cli.apps._normalize_repo_root", return_value=Path("/repo"))
    def test_validate_contract_standalone_missing_path_raises(self, _root, _contract) -> None:
        args = _ns(app_delivery_action="validate-contract", standalone=True, contract_path=None)
        with pytest.raises(ValueError, match="--contract-path"):
            handle_app_command(args)

    @patch("agentplane.cli.apps._ensure_formal_delivery_action_contract")
    @patch("agentplane.cli.apps._normalize_repo_root", return_value=Path("/repo"))
    def test_validate_contract_normal(self, _root, _contract) -> None:
        with patch.object(delivery_handlers, "validate_contract_for_app", return_value={"ok": True}) as mock:
            args = _ns(app_delivery_action="validate-contract", standalone=False, contract_path=None)
            handle_app_command(args)
        mock.assert_called_once_with(
            Path("/repo"), target=TARGET, app=APP, app_repo_root=None,
        )

    @patch("agentplane.cli.apps._ensure_formal_delivery_action_contract")
    @patch("agentplane.cli.apps._normalize_repo_root", return_value=Path("/repo"))
    def test_render_runtime(self, _root, _contract) -> None:
        with patch.object(delivery_handlers, "render_runtime_for_app", return_value={"ok": True}) as mock:
            args = _ns(app_delivery_action="render-runtime", image_ref="img:v2")
            handle_app_command(args)
        mock.assert_called_once_with(
            Path("/repo"), target=TARGET, app=APP, image_ref="img:v2", app_repo_root=None,
        )

    @patch("agentplane.cli.apps._ensure_formal_delivery_action_contract")
    @patch("agentplane.cli.apps._normalize_repo_root", return_value=Path("/repo"))
    def test_inventory_refresh(self, _root, _contract) -> None:
        with patch.object(delivery_handlers, "inventory_refresh_for_app", return_value={"ok": True}) as mock:
            args = _ns(app_delivery_action="inventory-refresh", write=True)
            handle_app_command(args)
        mock.assert_called_once_with(
            Path("/repo"), target=TARGET, app=APP, write=True, app_repo_root=None,
        )

    @patch("agentplane.cli.apps._ensure_formal_delivery_action_contract")
    @patch("agentplane.cli.apps._normalize_repo_root", return_value=Path("/repo"))
    def test_doc_sync(self, _root, _contract) -> None:
        with patch.object(delivery_handlers, "doc_sync_for_app", return_value={"ok": True}) as mock:
            args = _ns(app_delivery_action="doc-sync", write=True)
            handle_app_command(args)
        mock.assert_called_once_with(
            Path("/repo"), target=TARGET, app=APP, write=True, app_repo_root=None,
        )

    @patch("agentplane.cli.apps._ensure_formal_delivery_action_contract")
    @patch("agentplane.cli.apps._normalize_repo_root", return_value=Path("/repo"))
    def test_build_artifact(self, _root, _contract) -> None:
        with patch.object(delivery_handlers, "build_artifact_for_app", return_value={"ok": True}) as mock:
            args = _ns(
                app_delivery_action="build-artifact", image_tag="v1",
                auto_version=True, dry_run=True,
            )
            handle_app_command(args)
        mock.assert_called_once_with(
            Path("/repo"), target=TARGET, app=APP, image_tag="v1",
            auto_version=True, dry_run=True, app_repo_root=None,
        )

    @patch("agentplane.cli.apps._ensure_formal_delivery_action_contract")
    @patch("agentplane.cli.apps._normalize_repo_root", return_value=Path("/repo"))
    def test_package_runtime(self, _root, _contract) -> None:
        with patch.object(delivery_handlers, "package_runtime_for_app", return_value={"ok": True}) as mock:
            args = _ns(
                app_delivery_action="package-runtime", image_tag="v1",
                auto_version=False, dry_run=True,
            )
            handle_app_command(args)
        mock.assert_called_once_with(
            Path("/repo"), target=TARGET, app=APP, image_tag="v1",
            auto_version=False, dry_run=True, app_repo_root=None,
        )

    @patch("agentplane.cli.apps._ensure_formal_delivery_action_contract")
    @patch("agentplane.cli.apps._normalize_repo_root", return_value=Path("/repo"))
    def test_ship_image(self, _root, _contract) -> None:
        with patch.object(delivery_handlers, "ship_image_for_app", return_value={"ok": True}) as mock:
            args = _ns(
                app_delivery_action="ship-image", image_ref="reg/img:v1",
                archive_dir="tmp", dry_run=True,
            )
            handle_app_command(args)
        mock.assert_called_once_with(
            Path("/repo"), target=TARGET, app=APP, image_ref="reg/img:v1",
            archive_dir=Path("tmp"), dry_run=True, app_repo_root=None,
        )


# ---------------------------------------------------------------------------
# handle_app_command — error cases
# ---------------------------------------------------------------------------


class TestHandleAppCommandErrors:
    def test_unsupported_surface_raises(self) -> None:
        args = _ns(app_surface="bogus")
        with pytest.raises(ValueError, match="Unsupported app surface"):
            handle_app_command(args)

    def test_unsupported_delivery_action_raises(self) -> None:
        args = _ns(app_delivery_action="nope")
        with pytest.raises(ValueError, match="Unsupported app delivery action"):
            handle_app_command(args)

    @patch("agentplane.cli.apps._ensure_formal_delivery_action_contract")
    def test_contract_violation_propagates(self, mock_contract) -> None:
        mock_contract.side_effect = ValueError("bad flags")
        args = _ns(app_delivery_action="deploy", dry_run=True, execute=False)
        with pytest.raises(ValueError, match="bad flags"):
            handle_app_command(args)
