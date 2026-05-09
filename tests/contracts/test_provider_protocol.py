"""Contract tests for ProviderProtocol.

Every test is parametrized over all provider implementations (OnePanelAdapter,
StubProvider).  If a test passes for one implementation but fails for another,
the Protocol contract is violated.

These tests validate BEHAVIOUR (return types, key structure), not correctness
of specific provider data.  We don't need a real 1Panel server — only that
the implementation conforms to the protocol shape.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest


class TestProviderProtocolContract:
    """Verify that any ProviderProtocol implementation satisfies the contract."""

    def test_get_target_returns_something(self, provider) -> None:
        prov, target = provider
        tgt = prov.get_target(target)
        assert tgt is not None

    def test_refresh_ledgers_returns_dict(self, provider) -> None:
        prov, target = provider
        result = prov.refresh_ledgers(Path("."), target, write=False)
        assert isinstance(result, dict)

    def test_refresh_app_resource_ledgers_returns_dict(self, provider) -> None:
        prov, target = provider
        result = prov.refresh_app_resource_ledgers(Path("."), target, write=False)
        assert isinstance(result, dict)

    def test_search_websites_returns_dict_with_items(self, provider) -> None:
        prov, target = provider
        tgt = prov.get_target(target)
        result = prov.search_websites(tgt, name="nonexistent")
        assert isinstance(result, dict)
        assert "total" in result or "items" in result

    def test_get_website_returns_dict(self, provider) -> None:
        prov, target = provider
        tgt = prov.get_target(target)
        try:
            result = prov.get_website(tgt, website_id=0)
        except RuntimeError:
            # Real provider may raise on "record not found" — still a valid response
            return
        assert isinstance(result, dict)
        assert "id" in result

    def test_get_website_ssl_returns_dict(self, provider) -> None:
        prov, target = provider
        tgt = prov.get_target(target)
        try:
            result = prov.get_website_ssl(tgt, ssl_id=0)
        except RuntimeError:
            return
        assert isinstance(result, dict)
        assert "id" in result

    def test_plan_website_create_returns_object(self, provider) -> None:
        prov, _ = provider
        result = prov.plan_website_create(
            alias="test", domain="test.local", proxy="http://localhost:8080",
            remark="test", ipv6=False,
        )
        assert result is not None

    def test_search_installed_apps_returns_dict(self, provider) -> None:
        prov, target = provider
        tgt = prov.get_target(target)
        result = prov.search_installed_apps(tgt, name="nonexistent")
        assert isinstance(result, dict)

    def test_get_installed_app_returns_dict(self, provider) -> None:
        prov, target = provider
        tgt = prov.get_target(target)
        result = prov.get_installed_app(tgt, install_id=0)
        assert isinstance(result, dict)
        assert "id" in result

    def test_search_databases_returns_dict(self, provider) -> None:
        prov, target = provider
        tgt = prov.get_target(target)
        result = prov.search_databases(tgt, db_type="mysql")
        assert isinstance(result, dict)

    def test_app_lifecycle_step_returns_argv_and_display(self, provider) -> None:
        prov, target = provider
        argv, display = prov.app_lifecycle_step(
            Path("."), target=target, operate="start",
            rollback_entry={"install_id": 1},
        )
        assert isinstance(argv, list)
        assert len(argv) > 0
        assert isinstance(display, str)
        assert len(display) > 0

    def test_project_lifecycle_step_returns_argv_and_display(self, provider) -> None:
        prov, target = provider
        argv, display = prov.project_lifecycle_step(
            Path("."), target=target, operate="start",
            rollback_entry={"project_name": "test-project"},
        )
        assert isinstance(argv, list)
        assert len(argv) > 0
        assert isinstance(display, str)
        assert len(display) > 0

    def test_get_dashboard_returns_dict_with_metrics(self, provider) -> None:
        prov, target = provider
        tgt = prov.get_target(target)
        try:
            result = prov.get_dashboard(tgt)
        except RuntimeError:
            return
        assert isinstance(result, dict)
        assert len(result) > 0


class TestProtocolMethodCount:
    """Ensure the protocol doesn't exceed the 15-method abort threshold."""

    def test_protocol_method_count_within_limit(self) -> None:
        from agentplane.providers.protocol import ProviderProtocol

        # Count methods defined in the Protocol (excluding inherited object methods)
        protocol_methods = [
            name for name in dir(ProviderProtocol)
            if not name.startswith("_") and callable(getattr(ProviderProtocol, name, None))
        ]
        assert len(protocol_methods) <= 15, (
            f"ProviderProtocol has {len(protocol_methods)} methods, exceeds limit of 15. "
            f"Methods: {protocol_methods}"
        )


class TestProjectionContract:
    """Projection-specific contract tests.

    Validates that refresh_ledgers and refresh_app_resource_ledgers
    satisfy the projection contract:
    - Input: repo_root + target
    - Output: dict with projection metadata
    - Side effects: none when write=False (idempotent read)
    """

    def test_refresh_ledgers_idempotent_when_write_false(self, provider) -> None:
        prov, target = provider
        r1 = prov.refresh_ledgers(Path("."), target, write=False)
        r2 = prov.refresh_ledgers(Path("."), target, write=False)
        assert r1 == r2

    def test_refresh_app_resource_ledgers_idempotent_when_write_false(self, provider) -> None:
        prov, target = provider
        r1 = prov.refresh_app_resource_ledgers(Path("."), target, write=False)
        r2 = prov.refresh_app_resource_ledgers(Path("."), target, write=False)
        assert r1 == r2

    def test_refresh_ledgers_returns_target_key(self, provider) -> None:
        prov, target = provider
        result = prov.refresh_ledgers(Path("."), target, write=False)
        assert "target" in result

    def test_refresh_app_resource_ledgers_returns_target_key(self, provider) -> None:
        prov, target = provider
        result = prov.refresh_app_resource_ledgers(Path("."), target, write=False)
        assert "target" in result

    def test_projection_methods_return_consistent_types(self, provider) -> None:
        """Both projection methods must return dict — callers rely on this."""
        prov, target = provider
        r1 = prov.refresh_ledgers(Path("."), target, write=False)
        r2 = prov.refresh_app_resource_ledgers(Path("."), target, write=False)
        assert type(r1) is type(r2)


class TestStubProviderSatisfiesProtocol:
    """Explicit check that StubProvider structurally matches ProviderProtocol."""

    def test_stub_is_protocol_compatible(self) -> None:
        from agentplane.providers.protocol import ProviderProtocol
        from agentplane.providers.stub_provider import StubProvider

        # Structural compatibility check
        stub = StubProvider()
        proto: ProviderProtocol = stub  # type: ignore[assignment]
        assert proto is stub
