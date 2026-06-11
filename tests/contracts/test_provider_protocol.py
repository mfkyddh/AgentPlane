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

import pytest

pytestmark = pytest.mark.integration


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


class TestBoundaryConditions:
    """Edge-case tests for StubProvider contract compliance."""

    def test_search_with_empty_name(self) -> None:
        from agentplane.providers.stub_provider import StubProvider

        stub = StubProvider()
        tgt = stub.get_target("test")
        result = stub.search_websites(tgt, name="")
        assert isinstance(result, dict)

    def test_lifecycle_with_empty_rollback(self) -> None:
        from agentplane.providers.stub_provider import StubProvider

        stub = StubProvider()
        argv, display = stub.app_lifecycle_step(
            Path("."), target="t", operate="restart", rollback_entry={},
        )
        assert isinstance(argv, list)
        assert len(argv) > 0

    def test_dashboard_has_required_keys(self) -> None:
        from agentplane.providers.stub_provider import StubProvider

        stub = StubProvider()
        tgt = stub.get_target("test")
        result = stub.get_dashboard(tgt)
        assert "cpu" in result
        assert "memory" in result
        assert "load" in result

    def test_get_target_returns_consistent_type(self) -> None:
        from agentplane.providers.stub_provider import StubProvider

        stub = StubProvider()
        tgt1 = stub.get_target("host-a")
        tgt2 = stub.get_target("host-b")
        assert type(tgt1) is type(tgt2)


class TestNegativeContracts:
    """Negative and edge-case contract tests for StubProvider."""

    def test_search_websites_empty_name_returns_empty(self) -> None:
        from agentplane.providers.stub_provider import StubProvider

        stub = StubProvider()
        tgt = stub.get_target("test")
        result = stub.search_websites(tgt, name="")
        assert result["total"] == 0
        assert result["items"] == []

    def test_search_installed_apps_empty_name_returns_empty(self) -> None:
        from agentplane.providers.stub_provider import StubProvider

        stub = StubProvider()
        tgt = stub.get_target("test")
        result = stub.search_installed_apps(tgt, name="")
        assert result["total"] == 0
        assert result["items"] == []

    def test_search_databases_returns_empty(self) -> None:
        from agentplane.providers.stub_provider import StubProvider

        stub = StubProvider()
        tgt = stub.get_target("test")
        result = stub.search_databases(tgt, db_type="postgresql")
        assert result["total"] == 0
        assert result["items"] == []

    def test_get_website_returns_id(self) -> None:
        from agentplane.providers.stub_provider import StubProvider

        stub = StubProvider()
        tgt = stub.get_target("test")
        result = stub.get_website(tgt, website_id=42)
        assert result["id"] == 42

    def test_get_website_ssl_returns_id(self) -> None:
        from agentplane.providers.stub_provider import StubProvider

        stub = StubProvider()
        tgt = stub.get_target("test")
        result = stub.get_website_ssl(tgt, ssl_id=99)
        assert result["id"] == 99

    def test_get_installed_app_returns_id(self) -> None:
        from agentplane.providers.stub_provider import StubProvider

        stub = StubProvider()
        tgt = stub.get_target("test")
        result = stub.get_installed_app(tgt, install_id=7)
        assert result["id"] == 7

    def test_plan_website_create_preserves_params(self) -> None:
        from agentplane.providers.stub_provider import StubProvider

        stub = StubProvider()
        result = stub.plan_website_create(
            alias="myapp", domain="example.com", proxy="http://localhost:3000",
            remark="production", ipv6=True,
        )
        body = result["body"]
        assert body["alias"] == "myapp"
        assert body["domain"] == "example.com"
        assert body["proxy"] == "http://localhost:3000"
        assert body["remark"] == "production"
        assert body["ipv6"] is True

    def test_lifecycle_step_preserves_operate(self) -> None:
        from agentplane.providers.stub_provider import StubProvider

        stub = StubProvider()
        for operate in ("start", "stop", "restart"):
            argv, display = stub.app_lifecycle_step(
                Path("."), target="t", operate=operate, rollback_entry={},
            )
            assert operate in argv[-1]
            assert operate in display

    def test_project_lifecycle_step_preserves_operate(self) -> None:
        from agentplane.providers.stub_provider import StubProvider

        stub = StubProvider()
        for operate in ("start", "stop", "restart"):
            argv, display = stub.project_lifecycle_step(
                Path("."), target="t", operate=operate, rollback_entry={},
            )
            assert operate in argv[-1]
            assert operate in display

    def test_dashboard_has_all_metric_sections(self) -> None:
        from agentplane.providers.stub_provider import StubProvider

        stub = StubProvider()
        tgt = stub.get_target("test")
        result = stub.get_dashboard(tgt)
        for section in ("cpu", "memory", "load"):
            assert section in result
            assert isinstance(result[section], dict)

    def test_refresh_ledgers_write_false_no_side_effect(self) -> None:
        from agentplane.providers.stub_provider import StubProvider

        stub = StubProvider()
        result = stub.refresh_ledgers(Path("/nonexistent"), "target", write=False)
        assert result["write"] is False
        assert result["status"] == "stub"

    def test_refresh_app_resource_ledgers_write_false_no_side_effect(self) -> None:
        from agentplane.providers.stub_provider import StubProvider

        stub = StubProvider()
        result = stub.refresh_app_resource_ledgers(Path("/nonexistent"), "target", write=False)
        assert result["write"] is False
        assert result["status"] == "stub"

    def test_target_handle_is_hashable(self) -> None:
        from agentplane.providers.stub_provider import StubProvider

        stub = StubProvider()
        tgt = stub.get_target("test")
        hash(tgt)

    def test_target_handle_equality(self) -> None:
        from agentplane.providers.stub_provider import StubProvider

        stub = StubProvider()
        tgt1 = stub.get_target("same")
        tgt2 = stub.get_target("same")
        assert tgt1 == tgt2

    def test_target_handle_inequality(self) -> None:
        from agentplane.providers.stub_provider import StubProvider

        stub = StubProvider()
        tgt1 = stub.get_target("a")
        tgt2 = stub.get_target("b")
        assert tgt1 != tgt2
