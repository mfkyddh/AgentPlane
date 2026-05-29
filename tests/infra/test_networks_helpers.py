"""Tests for agentplane.domain.infra.networks — pure helper functions."""

from __future__ import annotations

from typing import Any

import pytest
from agentplane.domain.infra.networks import (
    _bridge_interface_name,
    _connected_container_names,
    _parse_json_output,
    managed_bridge_network_declaration_errors,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# managed_bridge_network_declaration_errors
# ---------------------------------------------------------------------------


class TestManagedBridgeNetworkDeclarationErrors:
    def test_valid_declaration(self) -> None:
        inventory: dict[str, Any] = {
            "managed_bridge_networks": [
                {
                    "name": "app-net",
                    "driver": "bridge",
                    "subnet": "172.20.0.0/16",
                    "gateway_ip": "172.20.0.1/16",
                    "required_for": ["myapp"],
                }
            ]
        }
        assert managed_bridge_network_declaration_errors(inventory) == []

    def test_missing_list(self) -> None:
        errors = managed_bridge_network_declaration_errors({})
        assert len(errors) == 1
        assert "non-empty" in errors[0]

    def test_empty_list(self) -> None:
        errors = managed_bridge_network_declaration_errors({"managed_bridge_networks": []})
        assert len(errors) == 1

    def test_non_dict_item(self) -> None:
        inventory: dict[str, Any] = {"managed_bridge_networks": ["invalid"]}
        errors = managed_bridge_network_declaration_errors(inventory)
        assert any("must be an object" in e for e in errors)

    def test_missing_fields(self) -> None:
        inventory: dict[str, Any] = {"managed_bridge_networks": [{"name": "net"}]}
        errors = managed_bridge_network_declaration_errors(inventory)
        assert any("driver" in e for e in errors)
        assert any("subnet" in e for e in errors)

    def test_invalid_driver(self) -> None:
        inventory: dict[str, Any] = {
            "managed_bridge_networks": [
                {
                    "name": "net",
                    "driver": "overlay",
                    "subnet": "172.20.0.0/16",
                    "gateway_ip": "172.20.0.1/16",
                }
            ]
        }
        errors = managed_bridge_network_declaration_errors(inventory)
        assert any("bridge" in e for e in errors)

    def test_invalid_subnet(self) -> None:
        inventory: dict[str, Any] = {
            "managed_bridge_networks": [
                {
                    "name": "net",
                    "driver": "bridge",
                    "subnet": "not-a-cidr",
                    "gateway_ip": "172.20.0.1/16",
                }
            ]
        }
        errors = managed_bridge_network_declaration_errors(inventory)
        assert any("CIDR" in e for e in errors)

    def test_gateway_not_in_subnet(self) -> None:
        inventory: dict[str, Any] = {
            "managed_bridge_networks": [
                {
                    "name": "net",
                    "driver": "bridge",
                    "subnet": "172.20.0.0/16",
                    "gateway_ip": "10.0.0.1/16",
                }
            ]
        }
        errors = managed_bridge_network_declaration_errors(inventory)
        assert any("must belong to" in e for e in errors)

    def test_invalid_required_for(self) -> None:
        inventory: dict[str, Any] = {
            "managed_bridge_networks": [
                {
                    "name": "net",
                    "driver": "bridge",
                    "subnet": "172.20.0.0/16",
                    "gateway_ip": "172.20.0.1/16",
                    "required_for": [123],
                }
            ]
        }
        errors = managed_bridge_network_declaration_errors(inventory)
        assert any("required_for" in e for e in errors)


# ---------------------------------------------------------------------------
# _bridge_interface_name
# ---------------------------------------------------------------------------


class TestBridgeInterfaceName:
    def test_from_options(self) -> None:
        payload: dict[str, Any] = {"Options": {"com.docker.network.bridge.name": "br-custom"}}
        assert _bridge_interface_name(payload) == "br-custom"

    def test_from_id(self) -> None:
        payload: dict[str, Any] = {"Id": "abc123def456ghi789"}
        result = _bridge_interface_name(payload)
        assert result is not None
        assert result.startswith("br-")

    def test_no_data(self) -> None:
        assert _bridge_interface_name({}) is None

    def test_short_id(self) -> None:
        payload: dict[str, Any] = {"Id": "short"}
        assert _bridge_interface_name(payload) is None


# ---------------------------------------------------------------------------
# _parse_json_output
# ---------------------------------------------------------------------------


class TestParseJsonOutput:
    def test_valid(self) -> None:
        assert _parse_json_output('{"key": "value"}') == {"key": "value"}

    def test_empty(self) -> None:
        assert _parse_json_output("") is None

    def test_whitespace(self) -> None:
        assert _parse_json_output("  \n  ") is None


# ---------------------------------------------------------------------------
# _connected_container_names
# ---------------------------------------------------------------------------


class TestConnectedContainerNames:
    def test_valid(self) -> None:
        payload: dict[str, Any] = {
            "Containers": {
                "abc": {"Name": "app1"},
                "def": {"Name": "app2"},
            }
        }
        names = _connected_container_names(payload)
        assert names == ["app1", "app2"]

    def test_empty(self) -> None:
        assert _connected_container_names({}) == []

    def test_non_dict_containers(self) -> None:
        assert _connected_container_names({"Containers": "invalid"}) == []

    def test_non_dict_item(self) -> None:
        payload: dict[str, Any] = {"Containers": {"abc": "invalid"}}
        assert _connected_container_names(payload) == []


# ---------------------------------------------------------------------------
# Golden test
# ---------------------------------------------------------------------------


@pytest.mark.golden
class TestNetworksHelpersGolden:
    def test_full_declaration_validation(self) -> None:
        """Valid multi-network declaration passes all checks."""
        inventory: dict[str, Any] = {
            "managed_bridge_networks": [
                {
                    "name": "app-net",
                    "driver": "bridge",
                    "subnet": "172.20.0.0/16",
                    "gateway_ip": "172.20.0.1/16",
                    "required_for": ["sub2api", "myapp"],
                },
                {
                    "name": "infra-net",
                    "driver": "bridge",
                    "subnet": "172.21.0.0/16",
                    "gateway_ip": "172.21.0.1/16",
                    "required_for": [],
                },
            ]
        }
        errors = managed_bridge_network_declaration_errors(inventory)
        assert errors == []

    def test_bridge_name_roundtrip(self) -> None:
        """Bridge interface name resolved from Options or Id."""
        with_options: dict[str, Any] = {"Options": {"com.docker.network.bridge.name": "br-app"}}
        assert _bridge_interface_name(with_options) == "br-app"

        with_id: dict[str, Any] = {"Id": "a1b2c3d4e5f6a1b2c3d4e5f6"}
        name = _bridge_interface_name(with_id)
        assert name is not None
        assert name.startswith("br-")

        containers = _connected_container_names({
            "Containers": {"x": {"Name": "svc1"}, "y": {"Name": "svc2"}, "z": {"Name": "svc3"}}
        })
        assert len(containers) == 3
        assert containers == sorted(containers)
