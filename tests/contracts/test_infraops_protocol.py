"""Contract tests for InfraOpsProviderProtocol.

Validates that InfraOpsProviderProtocol:
- Inherits all ProviderProtocol methods (13)
- Defines 1 additional infra-ops method
- Method has correct return type annotation

These tests verify protocol STRUCTURE, not runtime behaviour.
"""

from __future__ import annotations

import typing

import pytest
from agentplane.providers.protocol import InfraOpsProviderProtocol, ProviderProtocol

pytestmark = pytest.mark.integration

INFRAOPS_METHODS = [
    "get_openresty_status",
]


class TestInfraOpsProviderProtocolStructure:
    """Verify InfraOpsProviderProtocol class structure and method definitions."""

    def test_class_exists(self) -> None:
        assert InfraOpsProviderProtocol is not None

    def test_inherits_from_provider_protocol(self) -> None:
        assert ProviderProtocol in InfraOpsProviderProtocol.__mro__

    @pytest.mark.parametrize("method_name", INFRAOPS_METHODS)
    def test_method_defined(self, method_name: str) -> None:
        assert hasattr(InfraOpsProviderProtocol, method_name), (
            f"InfraOpsProviderProtocol missing method: {method_name}"
        )

    @pytest.mark.parametrize("method_name", INFRAOPS_METHODS)
    def test_method_is_callable(self, method_name: str) -> None:
        method = getattr(InfraOpsProviderProtocol, method_name)
        assert callable(method), f"{method_name} is not callable"

    def test_get_openresty_status_returns_dict(self) -> None:
        hints = typing.get_type_hints(InfraOpsProviderProtocol.get_openresty_status)
        assert typing.get_origin(hints["return"]) is dict


class TestInfraOpsProviderProtocolMethodCount:
    """Verify that InfraOpsProviderProtocol defines exactly 1 new method."""

    def test_infraops_specific_method_count(self) -> None:
        parent_methods = {
            name
            for name in dir(ProviderProtocol)
            if not name.startswith("_") and callable(getattr(ProviderProtocol, name, None))
        }
        child_methods = {
            name
            for name in dir(InfraOpsProviderProtocol)
            if not name.startswith("_")
            and callable(getattr(InfraOpsProviderProtocol, name, None))
        }
        new_methods = child_methods - parent_methods
        assert len(new_methods) == 1, (
            f"InfraOpsProviderProtocol defines {len(new_methods)} new methods, expected 1. "
            f"New methods: {sorted(new_methods)}"
        )

    def test_total_method_count(self) -> None:
        all_methods = [
            name
            for name in dir(InfraOpsProviderProtocol)
            if not name.startswith("_")
            and callable(getattr(InfraOpsProviderProtocol, name, None))
        ]
        assert len(all_methods) == 14, (
            f"InfraOpsProviderProtocol has {len(all_methods)} total methods, expected 14 "
            f"(13 inherited + 1 new). Methods: {all_methods}"
        )



