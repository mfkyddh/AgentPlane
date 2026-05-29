"""Tests for agentplane.domain.app.contracts — pure helper functions."""

from __future__ import annotations

import pytest
from agentplane.domain.app.contracts import (
    _inventory_container_names,
    _validate_previous_control_plane,
    has_public_ingress,
    ingress_mode,
    nested_get,
    public_sites,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# nested_get
# ---------------------------------------------------------------------------


class TestNestedGet:
    def test_simple(self) -> None:
        assert nested_get({"a": 1}, "a") == 1

    def test_dotted(self) -> None:
        assert nested_get({"a": {"b": 2}}, "a.b") == 2

    def test_missing(self) -> None:
        assert nested_get({"a": 1}, "b") is None

    def test_missing_nested(self) -> None:
        assert nested_get({"a": {"b": 2}}, "a.c") is None

    def test_non_dict_intermediate(self) -> None:
        assert nested_get({"a": "string"}, "a.b") is None

    def test_none_value(self) -> None:
        assert nested_get({"a": None}, "a") is None

    def test_empty_dict(self) -> None:
        assert nested_get({}, "a.b") is None


# ---------------------------------------------------------------------------
# ingress_mode
# ---------------------------------------------------------------------------


class TestIngressMode:
    def test_public(self) -> None:
        assert ingress_mode({"ingress": {"mode": "public"}}) == "public"

    def test_internal(self) -> None:
        assert ingress_mode({"ingress": {"mode": "internal"}}) == "internal"

    def test_missing_ingress(self) -> None:
        assert ingress_mode({}) == "public"

    def test_none_mode(self) -> None:
        assert ingress_mode({"ingress": {"mode": None}}) == "public"

    def test_empty_mode(self) -> None:
        assert ingress_mode({"ingress": {"mode": ""}}) == "public"

    def test_non_dict_ingress(self) -> None:
        assert ingress_mode({"ingress": "invalid"}) == "public"


# ---------------------------------------------------------------------------
# public_sites
# ---------------------------------------------------------------------------


class TestPublicSites:
    def test_valid_list(self) -> None:
        contract = {"ingress": {"public_sites": [{"domain": "example.com"}]}}
        result = public_sites(contract)
        assert len(result) == 1
        assert result[0]["domain"] == "example.com"

    def test_missing_ingress(self) -> None:
        assert public_sites({}) == []

    def test_non_list_public_sites(self) -> None:
        assert public_sites({"ingress": {"public_sites": "invalid"}}) == []

    def test_filters_non_dicts(self) -> None:
        contract = {"ingress": {"public_sites": [{"domain": "ok"}, "bad", 123]}}
        result = public_sites(contract)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# has_public_ingress
# ---------------------------------------------------------------------------


class TestHasPublicIngress:
    def test_public(self) -> None:
        assert has_public_ingress({"ingress": {"mode": "public"}}) is True

    def test_internal(self) -> None:
        assert has_public_ingress({"ingress": {"mode": "internal"}}) is False

    def test_default_public(self) -> None:
        assert has_public_ingress({}) is True


# ---------------------------------------------------------------------------
# _validate_previous_control_plane
# ---------------------------------------------------------------------------


class TestValidatePreviousControlPlane:
    def test_none_kind(self) -> None:
        _validate_previous_control_plane({"kind": "none"})

    def test_systemd_valid(self) -> None:
        _validate_previous_control_plane({"kind": "systemd", "service_name": "svc"})

    def test_systemd_missing_service_name(self) -> None:
        with pytest.raises(ValueError, match="service_name"):
            _validate_previous_control_plane({"kind": "systemd"})

    def test_systemd_empty_service_name(self) -> None:
        with pytest.raises(ValueError, match="service_name"):
            _validate_previous_control_plane({"kind": "systemd", "service_name": ""})

    def test_1panel_app_with_install_id(self) -> None:
        _validate_previous_control_plane({"kind": "1panel-app", "install_id": 1})

    def test_1panel_app_with_app_key(self) -> None:
        _validate_previous_control_plane({"kind": "1panel-app", "app_key": "myapp"})

    def test_1panel_app_missing_both(self) -> None:
        with pytest.raises(ValueError, match="install_id"):
            _validate_previous_control_plane({"kind": "1panel-app"})

    def test_1panel_app_empty_app_key(self) -> None:
        with pytest.raises(ValueError, match="install_id"):
            _validate_previous_control_plane({"kind": "1panel-app", "app_key": ""})

    def test_1panel_compose_valid(self) -> None:
        _validate_previous_control_plane({"kind": "1panel-compose", "project_name": "proj"})

    def test_1panel_compose_missing_project_name(self) -> None:
        with pytest.raises(ValueError, match="project_name"):
            _validate_previous_control_plane({"kind": "1panel-compose"})

    def test_1panel_compose_bad_container_name(self) -> None:
        with pytest.raises(ValueError, match="container_name"):
            _validate_previous_control_plane({
                "kind": "1panel-compose", "project_name": "p", "container_name": ""
            })

    def test_1panel_compose_bad_project_path(self) -> None:
        with pytest.raises(ValueError, match="project_path"):
            _validate_previous_control_plane({
                "kind": "1panel-compose", "project_name": "p", "project_path": ""
            })

    def test_1panel_compose_bad_compose_file(self) -> None:
        with pytest.raises(ValueError, match="compose_file"):
            _validate_previous_control_plane({
                "kind": "1panel-compose", "project_name": "p", "compose_file": ""
            })

    def test_unsupported_kind(self) -> None:
        with pytest.raises(ValueError, match="不支持"):
            _validate_previous_control_plane({"kind": "unsupported"})

    def test_not_dict_raises(self) -> None:
        with pytest.raises(ValueError, match="必须是对象"):
            _validate_previous_control_plane("not a dict")


# ---------------------------------------------------------------------------
# _inventory_container_names
# ---------------------------------------------------------------------------


class TestInventoryContainerNames:
    def test_valid(self) -> None:
        payload = {
            "services": {
                "web": {"container_name": "c1"},
                "api": {"container_name": "c2"},
            }
        }
        result = _inventory_container_names(payload)
        assert result == {"c1", "c2"}

    def test_empty_services(self) -> None:
        assert _inventory_container_names({}) == set()

    def test_non_dict_services(self) -> None:
        assert _inventory_container_names({"services": "invalid"}) == set()

    def test_non_dict_service_value(self) -> None:
        payload = {"services": {"web": "not a dict"}}
        assert _inventory_container_names(payload) == set()

    def test_missing_container_name(self) -> None:
        payload = {"services": {"web": {"image": "nginx"}}}
        assert _inventory_container_names(payload) == set()


# ---------------------------------------------------------------------------
# Golden test
# ---------------------------------------------------------------------------


@pytest.mark.golden
class TestContractsGolden:
    def test_full_contract_validation_roundtrip(self) -> None:
        """nested_get → ingress_mode → has_public_ingress → public_sites → validate."""
        contract = {
            "app_id": "test",
            "ingress": {"mode": "public", "public_sites": [{"domain": "example.com"}]},
            "rollback": {"previous_control_plane": {"kind": "none"}},
        }
        assert nested_get(contract, "ingress.mode") == "public"
        assert ingress_mode(contract) == "public"
        assert has_public_ingress(contract) is True
        assert len(public_sites(contract)) == 1
        _validate_previous_control_plane(nested_get(contract, "rollback.previous_control_plane"))
