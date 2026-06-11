"""Unit tests: OnePanelAdapter delegates HealthProviderProtocol and InfraOpsProviderProtocol methods."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from agentplane.providers.onepanel_adapter import OnePanelAdapter
from agentplane.providers.protocol import HealthProviderProtocol, InfraOpsProviderProtocol

pytestmark = pytest.mark.unit


class TestHealthProtocolDelegation:
    """Each health method delegates to the correct gateway method."""

    def test_get_dashboard_base(self, adapter: OnePanelAdapter, mock_gateway: MagicMock) -> None:
        tgt = MagicMock()
        result = adapter.get_dashboard_base(tgt)
        mock_gateway.get_onepanel_dashboard_base.assert_called_once_with(tgt)
        assert result is mock_gateway.get_onepanel_dashboard_base.return_value

    def test_get_dashboard_top_cpu(self, adapter: OnePanelAdapter, mock_gateway: MagicMock) -> None:
        tgt = MagicMock()
        result = adapter.get_dashboard_top_cpu(tgt)
        mock_gateway.get_onepanel_dashboard_top_cpu.assert_called_once_with(tgt)
        assert result is mock_gateway.get_onepanel_dashboard_top_cpu.return_value

    def test_get_dashboard_top_mem(self, adapter: OnePanelAdapter, mock_gateway: MagicMock) -> None:
        tgt = MagicMock()
        result = adapter.get_dashboard_top_mem(tgt)
        mock_gateway.get_onepanel_dashboard_top_mem.assert_called_once_with(tgt)
        assert result is mock_gateway.get_onepanel_dashboard_top_mem.return_value

    def test_search_alerts(self, adapter: OnePanelAdapter, mock_gateway: MagicMock) -> None:
        tgt = MagicMock()
        result = adapter.search_alerts(tgt, alert_type="cpu", status="firing")
        mock_gateway.search_onepanel_alerts.assert_called_once_with(
            tgt,
            alert_type="cpu",
            status="firing",
        )
        assert result is mock_gateway.search_onepanel_alerts.return_value

    def test_search_alert_logs(self, adapter: OnePanelAdapter, mock_gateway: MagicMock) -> None:
        tgt = MagicMock()
        result = adapter.search_alert_logs(tgt, status="resolved")
        mock_gateway.search_onepanel_alert_logs.assert_called_once_with(
            tgt,
            status="resolved",
        )
        assert result is mock_gateway.search_onepanel_alert_logs.return_value

    def test_get_monitor_setting(self, adapter: OnePanelAdapter, mock_gateway: MagicMock) -> None:
        tgt = MagicMock()
        result = adapter.get_monitor_setting(tgt)
        mock_gateway.get_onepanel_monitor_setting.assert_called_once_with(tgt)
        assert result is mock_gateway.get_onepanel_monitor_setting.return_value


class TestInfraOpsProtocolDelegation:
    """InfraOps methods delegate to the correct gateway method."""

    def test_get_openresty_status(self, adapter: OnePanelAdapter, mock_gateway: MagicMock) -> None:
        tgt = MagicMock()
        result = adapter.get_openresty_status(tgt)
        mock_gateway.get_onepanel_openresty_status.assert_called_once_with(tgt)
        assert result is mock_gateway.get_onepanel_openresty_status.return_value


class TestAdapterSatisfiesSubProtocols:
    """Structural compatibility: adapter satisfies both sub-protocols."""

    def test_adapter_is_health_provider(self, adapter: OnePanelAdapter) -> None:
        assert isinstance(adapter, HealthProviderProtocol)

    def test_adapter_is_infra_ops_provider(self, adapter: OnePanelAdapter) -> None:
        assert isinstance(adapter, InfraOpsProviderProtocol)
