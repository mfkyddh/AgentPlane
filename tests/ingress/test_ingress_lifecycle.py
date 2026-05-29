"""Tests for agentplane.domain.ingress.lifecycle — pure helper functions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from agentplane.domain.ingress.lifecycle import (
    _definition_payload,
    _find_alias,
    _inventory_file,
    _payload_matches,
    _public_ingresses_snapshot,
    _validate_target,
)
from agentplane.domain.ingress.models import IngressDefinition

pytestmark = pytest.mark.unit


def _make_definition(**overrides: Any) -> IngressDefinition:
    defaults: dict[str, Any] = {
        "alias": "myapp",
        "primary_domain": "myapp.example.com",
        "public_url": "https://myapp.example.com",
        "proxy": "http://127.0.0.1:3000",
        "status": "active",
        "config_file": "/etc/nginx/conf.d/myapp.conf",
        "ssl_id": None,
        "certificate_mode": "letsencrypt",
        "control_plane": "onepanel",
    }
    defaults.update(overrides)
    return IngressDefinition(**defaults)


# ---------------------------------------------------------------------------
# _validate_target
# ---------------------------------------------------------------------------


class TestValidateTarget:
    def test_valid_target(self) -> None:
        # Should not raise for supported targets
        _validate_target("wsl")

    def test_invalid_target(self) -> None:
        with pytest.raises(ValueError, match="unsupported ingress target"):
            _validate_target("invalid-xyz")


# ---------------------------------------------------------------------------
# _inventory_file
# ---------------------------------------------------------------------------


class TestInventoryFile:
    def test_path(self, tmp_path: Path) -> None:
        result = _inventory_file(tmp_path, "wsl")
        assert result == tmp_path / "inventory" / "servers" / "wsl" / "inventory.json"

    def test_prod0(self, tmp_path: Path) -> None:
        result = _inventory_file(tmp_path, "prod0-main")
        assert result == tmp_path / "inventory" / "servers" / "prod0-main" / "inventory.json"


# ---------------------------------------------------------------------------
# _definition_payload
# ---------------------------------------------------------------------------


class TestDefinitionPayload:
    def test_basic(self) -> None:
        definition = _make_definition()
        payload = _definition_payload(definition)
        assert payload["alias"] == "myapp"
        assert payload["primary_domain"] == "myapp.example.com"
        assert payload["public_url"] == "https://myapp.example.com"
        assert payload["proxy"] == "http://127.0.0.1:3000"

    def test_optional_fields(self) -> None:
        definition = _make_definition(status="", config_file="", ssl_id=None, certificate_mode="", control_plane="onepanel")
        payload = _definition_payload(definition)
        assert "status" not in payload
        assert "config_file" not in payload
        assert "ssl_id" not in payload
        assert "certificate_mode" not in payload
        assert "control_plane" not in payload

    def test_non_default_control_plane(self) -> None:
        definition = _make_definition(control_plane="custom")
        payload = _definition_payload(definition)
        assert payload["control_plane"] == "custom"

    def test_ssl_id_zero(self) -> None:
        definition = _make_definition(ssl_id=0)
        payload = _definition_payload(definition)
        assert payload["ssl_id"] == 0


# ---------------------------------------------------------------------------
# _find_alias
# ---------------------------------------------------------------------------


class TestFindAlias:
    def test_found(self) -> None:
        entries = [{"alias": "a"}, {"alias": "b"}, {"alias": "c"}]
        index, item = _find_alias(entries, "b")
        assert index == 1
        assert item["alias"] == "b"

    def test_not_found(self) -> None:
        entries = [{"alias": "a"}]
        index, item = _find_alias(entries, "missing")
        assert index is None
        assert item is None

    def test_empty(self) -> None:
        index, item = _find_alias([], "x")
        assert index is None
        assert item is None


# ---------------------------------------------------------------------------
# _payload_matches
# ---------------------------------------------------------------------------


class TestPayloadMatches:
    def test_identical(self) -> None:
        p = {"alias": "a", "domain": "d.com"}
        assert _payload_matches(p, p) is True

    def test_subset_matches(self) -> None:
        existing = {"alias": "a", "domain": "d.com", "extra": "x"}
        payload = {"alias": "a", "domain": "d.com"}
        assert _payload_matches(existing, payload) is True

    def test_mismatch(self) -> None:
        existing = {"alias": "a", "domain": "old.com"}
        payload = {"alias": "a", "domain": "new.com"}
        assert _payload_matches(existing, payload) is False

    def test_missing_key(self) -> None:
        existing = {"alias": "a"}
        payload = {"alias": "a", "domain": "d.com"}
        assert _payload_matches(existing, payload) is False


# ---------------------------------------------------------------------------
# _public_ingresses_snapshot
# ---------------------------------------------------------------------------


class TestPublicIngressesSnapshot:
    def test_valid(self) -> None:
        inventory: dict[str, Any] = {"services": {"public_ingresses": [{"alias": "a"}, {"alias": "b"}]}}
        result = _public_ingresses_snapshot(inventory)
        assert len(result) == 2

    def test_no_services(self) -> None:
        assert _public_ingresses_snapshot({}) == []

    def test_no_public_ingresses(self) -> None:
        assert _public_ingresses_snapshot({"services": {}}) == []

    def test_non_list(self) -> None:
        assert _public_ingresses_snapshot({"services": {"public_ingresses": "invalid"}}) == []

    def test_filters_non_dict(self) -> None:
        inventory: dict[str, Any] = {"services": {"public_ingresses": [{"alias": "a"}, "invalid", 42]}}
        result = _public_ingresses_snapshot(inventory)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Golden test
# ---------------------------------------------------------------------------


@pytest.mark.golden
class TestIngressLifecycleGolden:
    def test_full_definition_roundtrip(self) -> None:
        """Full definition payload with all fields populated."""
        definition = _make_definition(
            ssl_id=42,
            certificate_mode="custom",
            control_plane="nginx",
        )
        payload = _definition_payload(definition)
        assert payload["alias"] == "myapp"
        assert payload["ssl_id"] == 42
        assert payload["control_plane"] == "nginx"

        # Find in a snapshot
        entries = [payload, {"alias": "other"}]
        index, item = _find_alias(entries, "myapp")
        assert index == 0
        assert item["ssl_id"] == 42

        # Match check
        assert _payload_matches(payload, payload) is True
