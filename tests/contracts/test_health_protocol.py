"""Contract tests for HealthProviderProtocol.

Validates that HealthProviderProtocol:
- Inherits all ProviderProtocol methods (13)
- Defines 6 additional health-specific methods
- Methods have correct return type annotations

These tests verify protocol STRUCTURE, not runtime behaviour.
Actual adapter/stub conformance tests belong in separate task files.
"""

from __future__ import annotations

import typing

import pytest
from agentplane.providers.protocol import HealthProviderProtocol, ProviderProtocol

pytestmark = pytest.mark.integration

HEALTH_METHODS = [
    "get_dashboard_base",
    "get_dashboard_top_cpu",
    "get_dashboard_top_mem",
    "search_alerts",
    "search_alert_logs",
    "get_monitor_setting",
]


class TestHealthProviderProtocolStructure:
    """Verify HealthProviderProtocol class structure and method definitions."""

    def test_class_exists(self) -> None:
        assert HealthProviderProtocol is not None

    def test_inherits_from_provider_protocol(self) -> None:
        assert ProviderProtocol in HealthProviderProtocol.__mro__

    @pytest.mark.parametrize("method_name", HEALTH_METHODS)
    def test_method_defined(self, method_name: str) -> None:
        assert hasattr(HealthProviderProtocol, method_name), (
            f"HealthProviderProtocol missing method: {method_name}"
        )

    @pytest.mark.parametrize("method_name", HEALTH_METHODS)
    def test_method_is_callable(self, method_name: str) -> None:
        method = getattr(HealthProviderProtocol, method_name)
        assert callable(method), f"{method_name} is not callable"

    def test_get_dashboard_base_returns_dict(self) -> None:
        hints = typing.get_type_hints(HealthProviderProtocol.get_dashboard_base)
        assert typing.get_origin(hints["return"]) is dict

    def test_get_dashboard_top_cpu_returns_list(self) -> None:
        hints = typing.get_type_hints(HealthProviderProtocol.get_dashboard_top_cpu)
        assert typing.get_origin(hints["return"]) is list

    def test_get_dashboard_top_mem_returns_list(self) -> None:
        hints = typing.get_type_hints(HealthProviderProtocol.get_dashboard_top_mem)
        assert typing.get_origin(hints["return"]) is list

    def test_search_alerts_returns_dict(self) -> None:
        hints = typing.get_type_hints(HealthProviderProtocol.search_alerts)
        assert typing.get_origin(hints["return"]) is dict

    def test_search_alert_logs_returns_dict(self) -> None:
        hints = typing.get_type_hints(HealthProviderProtocol.search_alert_logs)
        assert typing.get_origin(hints["return"]) is dict

    def test_get_monitor_setting_returns_dict(self) -> None:
        hints = typing.get_type_hints(HealthProviderProtocol.get_monitor_setting)
        assert typing.get_origin(hints["return"]) is dict


class TestHealthProviderProtocolMethodCount:
    """Verify that HealthProviderProtocol defines exactly 6 new methods."""

    def test_health_specific_method_count(self) -> None:
        parent_methods = {
            name
            for name in dir(ProviderProtocol)
            if not name.startswith("_") and callable(getattr(ProviderProtocol, name, None))
        }
        child_methods = {
            name
            for name in dir(HealthProviderProtocol)
            if not name.startswith("_")
            and callable(getattr(HealthProviderProtocol, name, None))
        }
        new_methods = child_methods - parent_methods
        assert len(new_methods) == 6, (
            f"HealthProviderProtocol defines {len(new_methods)} new methods, expected 6. "
            f"New methods: {sorted(new_methods)}"
        )

    def test_total_method_count(self) -> None:
        all_methods = [
            name
            for name in dir(HealthProviderProtocol)
            if not name.startswith("_")
            and callable(getattr(HealthProviderProtocol, name, None))
        ]
        assert len(all_methods) == 19, (
            f"HealthProviderProtocol has {len(all_methods)} total methods, expected 19 "
            f"(13 inherited + 6 new). Methods: {all_methods}"
        )



