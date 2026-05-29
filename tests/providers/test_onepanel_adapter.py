"""Unit tests for OnePanelAdapter delegation.

Verifies that each ProviderProtocol method on OnePanelAdapter correctly
delegates to the corresponding OnePanelProviderGateway method.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from agentplane.providers.onepanel_adapter import OnePanelAdapter
from agentplane.providers.protocol import ProviderProtocol

pytestmark = pytest.mark.unit


class TestAdapterSatisfiesProtocol:
    """Structural compatibility check."""

    def test_adapter_is_protocol_compatible(self) -> None:
        adapter = OnePanelAdapter()
        proto: ProviderProtocol = adapter  # type: ignore[assignment]
        assert proto is adapter


class TestAdapterDelegation:
    """Each method delegates to the correct gateway method."""

    def test_get_target(self, adapter, mock_gateway) -> None:
        mock_gateway.onepanel_target_executor.return_value = "fake-tgt"
        result = adapter.get_target("my-host")
        mock_gateway.onepanel_target_executor.assert_called_once_with("my-host")
        assert result == "fake-tgt"

    def test_refresh_ledgers(self, adapter, mock_gateway) -> None:
        mock_gateway.refresh_onepanel_ledgers.return_value = {"target": "t"}
        result = adapter.refresh_ledgers(Path("."), "t", write=False)
        mock_gateway.refresh_onepanel_ledgers.assert_called_once_with(Path("."), "t", write=False)
        assert result == {"target": "t"}

    def test_refresh_app_resource_ledgers(self, adapter, mock_gateway) -> None:
        mock_gateway.refresh_app_resource_ledgers.return_value = {"target": "t"}
        result = adapter.refresh_app_resource_ledgers(Path("."), "t", write=True)
        mock_gateway.refresh_app_resource_ledgers.assert_called_once_with(Path("."), "t", write=True)
        assert result == {"target": "t"}

    def test_search_websites(self, adapter, mock_gateway) -> None:
        mock_gateway.search_onepanel_websites.return_value = {"total": 0, "items": []}
        tgt = MagicMock()
        result = adapter.search_websites(tgt, name="test")
        mock_gateway.search_onepanel_websites.assert_called_once_with(tgt, name="test")
        assert result == {"total": 0, "items": []}

    def test_get_website(self, adapter, mock_gateway) -> None:
        mock_gateway.get_onepanel_website.return_value = {"id": 1}
        tgt = MagicMock()
        result = adapter.get_website(tgt, website_id=1)
        mock_gateway.get_onepanel_website.assert_called_once_with(tgt, website_id=1)
        assert result == {"id": 1}

    def test_get_website_ssl(self, adapter, mock_gateway) -> None:
        mock_gateway.get_onepanel_website_ssl.return_value = {"id": 2}
        tgt = MagicMock()
        result = adapter.get_website_ssl(tgt, ssl_id=2)
        mock_gateway.get_onepanel_website_ssl.assert_called_once_with(tgt, ssl_id=2)
        assert result == {"id": 2}

    def test_plan_website_create(self, adapter, mock_gateway) -> None:
        mock_gateway.plan_onepanel_website_create.return_value = {"alias": "test"}
        result = adapter.plan_website_create(
            alias="test", domain="test.local", proxy="http://localhost:8080",
            remark="test", ipv6=False,
        )
        mock_gateway.plan_onepanel_website_create.assert_called_once_with(
            alias="test", domain="test.local", proxy="http://localhost:8080",
            remark="test", ipv6=False,
        )
        assert result == {"alias": "test"}

    def test_search_installed_apps(self, adapter, mock_gateway) -> None:
        mock_gateway.search_onepanel_installed_apps.return_value = {"total": 0}
        tgt = MagicMock()
        result = adapter.search_installed_apps(tgt, name="nginx")
        mock_gateway.search_onepanel_installed_apps.assert_called_once_with(tgt, name="nginx")
        assert result == {"total": 0}

    def test_get_installed_app(self, adapter, mock_gateway) -> None:
        mock_gateway.get_onepanel_installed_app.return_value = {"id": 5}
        tgt = MagicMock()
        result = adapter.get_installed_app(tgt, install_id=5)
        mock_gateway.get_onepanel_installed_app.assert_called_once_with(tgt, install_id=5)
        assert result == {"id": 5}

    def test_search_databases(self, adapter, mock_gateway) -> None:
        mock_gateway.search_onepanel_databases.return_value = {"total": 0}
        tgt = MagicMock()
        result = adapter.search_databases(tgt, db_type="postgresql")
        mock_gateway.search_onepanel_databases.assert_called_once_with(tgt, db_type="postgresql")
        assert result == {"total": 0}

    def test_app_lifecycle_step(self, adapter, mock_gateway) -> None:
        mock_gateway.onepanel_app_lifecycle_step.return_value = (["echo", "ok"], "echo ok")
        result = adapter.app_lifecycle_step(
            Path("."), target="t", operate="start", rollback_entry={"install_id": 1},
        )
        mock_gateway.onepanel_app_lifecycle_step.assert_called_once_with(
            Path("."), target="t", operate="start", rollback_entry={"install_id": 1},
        )
        assert result == (["echo", "ok"], "echo ok")

    def test_project_lifecycle_step(self, adapter, mock_gateway) -> None:
        mock_gateway.onepanel_project_lifecycle_step.return_value = (["echo", "p"], "echo p")
        result = adapter.project_lifecycle_step(
            Path("."), target="t", operate="stop", rollback_entry={"project_name": "proj"},
        )
        mock_gateway.onepanel_project_lifecycle_step.assert_called_once_with(
            Path("."), target="t", operate="stop", rollback_entry={"project_name": "proj"},
        )
        assert result == (["echo", "p"], "echo p")

    def test_get_dashboard(self, adapter, mock_gateway) -> None:
        mock_gateway.get_onepanel_dashboard_current.return_value = {"cpu": {"used": 10}}
        tgt = MagicMock()
        result = adapter.get_dashboard(tgt)
        mock_gateway.get_onepanel_dashboard_current.assert_called_once_with(tgt)
        assert result == {"cpu": {"used": 10}}


class TestAdapterFactory:
    """Test the get_provider() factory function."""

    def test_get_provider_returns_onepanel_adapter_by_default(self) -> None:
        from agentplane.providers import get_provider

        provider = get_provider()
        assert isinstance(provider, OnePanelAdapter)

    def test_get_provider_returns_stub_when_env_set(self, monkeypatch) -> None:
        from agentplane.providers import get_provider
        from agentplane.providers.stub_provider import StubProvider

        monkeypatch.setenv("AGENTPLANE_PROVIDER", "stub")
        provider = get_provider()
        assert isinstance(provider, StubProvider)
