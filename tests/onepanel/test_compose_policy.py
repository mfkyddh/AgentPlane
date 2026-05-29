"""Tests for agentplane.scripts.onepanel.compose_policy — pure functions."""

from __future__ import annotations

import pytest
import yaml
from agentplane.scripts.onepanel.compose_policy import (
    _normalize_service_networks,
    enforce_host_network,
    enforce_zqf_network,
    normalize_compose_for_app,
    requires_host_network,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# requires_host_network
# ---------------------------------------------------------------------------


class TestRequiresHostNetwork:
    def test_openresty(self) -> None:
        assert requires_host_network("openresty") is True

    def test_other_app(self) -> None:
        assert requires_host_network("myapp") is False


# ---------------------------------------------------------------------------
# _normalize_service_networks
# ---------------------------------------------------------------------------


class TestNormalizeServiceNetworks:
    def test_none(self) -> None:
        result = _normalize_service_networks(None, "zqf_network")
        assert result == ["zqf_network"]

    def test_list_with_legacy(self) -> None:
        result = _normalize_service_networks(["1panel-network"], "zqf_network")
        assert result == ["zqf_network"]

    def test_list_without_required(self) -> None:
        result = _normalize_service_networks(["other"], "zqf_network")
        assert result == ["other", "zqf_network"]

    def test_list_already_has_required(self) -> None:
        result = _normalize_service_networks(["zqf_network"], "zqf_network")
        assert result == ["zqf_network"]

    def test_dict_with_legacy_key(self) -> None:
        result = _normalize_service_networks({"1panel-network": None}, "zqf_network")
        assert "zqf_network" in result
        assert "1panel-network" not in result

    def test_dict_without_required(self) -> None:
        result = _normalize_service_networks({"other": {"priority": 1}}, "zqf_network")
        assert "zqf_network" in result
        assert result["other"] == {"priority": 1}

    def test_scalar_fallback(self) -> None:
        result = _normalize_service_networks("invalid", "zqf_network")
        assert result == ["zqf_network"]


# ---------------------------------------------------------------------------
# enforce_zqf_network
# ---------------------------------------------------------------------------


class TestEnforceZqfNetwork:
    def test_basic(self) -> None:
        raw = yaml.dump({
            "services": {"web": {"image": "nginx"}},
            "networks": {"1panel-network": {"external": True}},
        })
        result = yaml.safe_load(enforce_zqf_network(raw))
        assert "zqf_network" in result["networks"]
        assert "1panel-network" not in result["networks"]

    def test_no_services_raises(self) -> None:
        with pytest.raises(ValueError, match="services"):
            enforce_zqf_network("not_a_dict: true")

    def test_non_mapping_raises(self) -> None:
        with pytest.raises(ValueError, match="mapping"):
            enforce_zqf_network(yaml.dump("just a string"))

    def test_non_mapping_service_raises(self) -> None:
        raw = yaml.dump({"services": {"web": "nginx"}})
        with pytest.raises(ValueError, match="mapping"):
            enforce_zqf_network(raw)


# ---------------------------------------------------------------------------
# enforce_host_network
# ---------------------------------------------------------------------------


class TestEnforceHostNetwork:
    def test_basic(self) -> None:
        raw = yaml.dump({
            "services": {"web": {"image": "nginx", "networks": ["net1"]}},
            "networks": {"net1": {}},
        })
        result = yaml.safe_load(enforce_host_network(raw))
        assert "networks" not in result
        assert result["services"]["web"]["network_mode"] == "infra"
        assert "networks" not in result["services"]["web"]

    def test_no_services_raises(self) -> None:
        with pytest.raises(ValueError, match="services"):
            enforce_host_network("not_a_dict: true")

    def test_non_mapping_service_raises(self) -> None:
        raw = yaml.dump({"services": {"web": "nginx"}})
        with pytest.raises(ValueError, match="mapping"):
            enforce_host_network(raw)


# ---------------------------------------------------------------------------
# normalize_compose_for_app
# ---------------------------------------------------------------------------


class TestNormalizeComposeForApp:
    def test_host_network_app(self) -> None:
        raw = yaml.dump({
            "services": {"openresty": {"image": "openresty/openresty"}},
        })
        result = yaml.safe_load(normalize_compose_for_app("openresty", raw))
        assert result["services"]["openresty"]["network_mode"] == "infra"

    def test_regular_app(self) -> None:
        raw = yaml.dump({
            "services": {"web": {"image": "nginx"}},
        })
        result = yaml.safe_load(normalize_compose_for_app("myapp", raw))
        assert "zqf_network" in result.get("networks", {})


# ---------------------------------------------------------------------------
# Golden test
# ---------------------------------------------------------------------------


@pytest.mark.golden
class TestComposePolicyGolden:
    def test_full_normalize_roundtrip(self) -> None:
        """Legacy network → zqf_network normalization end-to-end."""
        raw = yaml.dump({
            "services": {
                "web": {"image": "nginx", "networks": ["1panel-network"]},
                "api": {"image": "python:3.12"},
            },
            "networks": {"1panel-network": {"external": True}},
        })
        result = yaml.safe_load(enforce_zqf_network(raw))
        assert "zqf_network" in result["networks"]
        assert "1panel-network" not in result["networks"]
        assert "zqf_network" in result["services"]["web"]["networks"]
        assert "zqf_network" in result["services"]["api"]["networks"]
