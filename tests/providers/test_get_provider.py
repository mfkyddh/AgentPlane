"""Unit tests for get_provider() factory with protocol validation."""

from __future__ import annotations

import pytest
from agentplane.providers import (
    HealthProviderProtocol,
    InfraOpsProviderProtocol,
    ProviderProtocol,
    UnsupportedProviderProtocol,
    get_provider,
)
from agentplane.providers.onepanel_adapter import OnePanelAdapter

pytestmark = pytest.mark.unit


class TestGetProviderProtocolValidation:
    """Verify protocol parameter behavior."""

    def test_no_protocol_returns_provider(self) -> None:
        provider = get_provider()
        assert isinstance(provider, OnePanelAdapter)

    def test_provider_protocol_accepted(self) -> None:
        provider = get_provider(protocol=ProviderProtocol)
        assert isinstance(provider, OnePanelAdapter)

    def test_unsupported_health_protocol_raises(self) -> None:
        with pytest.raises(UnsupportedProviderProtocol) as exc_info:
            get_provider(protocol=HealthProviderProtocol)
        assert "HealthProviderProtocol" in str(exc_info.value)

    def test_unsupported_infra_ops_protocol_raises(self) -> None:
        with pytest.raises(UnsupportedProviderProtocol) as exc_info:
            get_provider(protocol=InfraOpsProviderProtocol)
        assert "InfraOpsProviderProtocol" in str(exc_info.value)

    def test_unsupported_protocol_is_type_error(self) -> None:
        with pytest.raises(TypeError):
            get_provider(protocol=HealthProviderProtocol)

    def test_stub_provider_protocol_accepted(self, monkeypatch) -> None:
        monkeypatch.setenv("AGENTPLANE_PROVIDER", "stub")
        provider = get_provider(protocol=ProviderProtocol)
        assert provider is not None

    def test_stub_provider_unsupported_protocol_raises(self, monkeypatch) -> None:
        monkeypatch.setenv("AGENTPLANE_PROVIDER", "stub")
        with pytest.raises(UnsupportedProviderProtocol):
            get_provider(protocol=HealthProviderProtocol)
