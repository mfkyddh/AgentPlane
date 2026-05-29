"""Tests for agentplane.domain.infra.networks — managed bridge network validation."""

from __future__ import annotations

import pytest
from agentplane.domain.infra.networks import managed_bridge_network_declaration_errors

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# managed_bridge_network_declaration_errors
# ---------------------------------------------------------------------------


class TestManagedBridgeNetworkDeclarationErrors:
    def test_missing_field(self) -> None:
        inventory: dict = {}
        errors = managed_bridge_network_declaration_errors(inventory)
        assert len(errors) >= 1
        assert "non-empty list" in errors[0]

    def test_empty_list(self) -> None:
        inventory = {"managed_bridge_networks": []}
        errors = managed_bridge_network_declaration_errors(inventory)
        assert len(errors) >= 1

    def test_non_list(self) -> None:
        inventory = {"managed_bridge_networks": "bad"}
        errors = managed_bridge_network_declaration_errors(inventory)
        assert len(errors) >= 1

    def test_valid_network(self) -> None:
        inventory = {
            "managed_bridge_networks": [
                {
                    "name": "mynet",
                    "driver": "bridge",
                    "subnet": "172.20.0.0/16",
                    "gateway_ip": "172.20.0.1/16",
                    "required_for": ["app1"],
                }
            ]
        }
        errors = managed_bridge_network_declaration_errors(inventory)
        assert errors == []

    def test_non_dict_item(self) -> None:
        inventory = {"managed_bridge_networks": ["bad"]}
        errors = managed_bridge_network_declaration_errors(inventory)
        assert any("must be an object" in e for e in errors)

    def test_empty_string_field(self) -> None:
        inventory = {
            "managed_bridge_networks": [
                {
                    "name": "",
                    "driver": "bridge",
                    "subnet": "172.20.0.0/16",
                    "gateway_ip": "172.20.0.1/16",
                }
            ]
        }
        errors = managed_bridge_network_declaration_errors(inventory)
        assert any("name" in e and "non-empty string" in e for e in errors)

    def test_invalid_driver(self) -> None:
        inventory = {
            "managed_bridge_networks": [
                {
                    "name": "mynet",
                    "driver": "overlay",
                    "subnet": "172.20.0.0/16",
                    "gateway_ip": "172.20.0.1/16",
                }
            ]
        }
        errors = managed_bridge_network_declaration_errors(inventory)
        assert any("driver only supports bridge" in e for e in errors)

    def test_invalid_subnet(self) -> None:
        inventory = {
            "managed_bridge_networks": [
                {
                    "name": "mynet",
                    "driver": "bridge",
                    "subnet": "not-a-cidr",
                    "gateway_ip": "172.20.0.1/16",
                }
            ]
        }
        errors = managed_bridge_network_declaration_errors(inventory)
        assert any("subnet" in e and "CIDR" in e for e in errors)

    def test_invalid_gateway(self) -> None:
        inventory = {
            "managed_bridge_networks": [
                {
                    "name": "mynet",
                    "driver": "bridge",
                    "subnet": "172.20.0.0/16",
                    "gateway_ip": "not-an-ip",
                }
            ]
        }
        errors = managed_bridge_network_declaration_errors(inventory)
        assert any("gateway_ip" in e and "CIDR" in e for e in errors)

    def test_gateway_not_in_subnet(self) -> None:
        inventory = {
            "managed_bridge_networks": [
                {
                    "name": "mynet",
                    "driver": "bridge",
                    "subnet": "172.20.0.0/16",
                    "gateway_ip": "10.0.0.1/16",
                }
            ]
        }
        errors = managed_bridge_network_declaration_errors(inventory)
        assert any("gateway_ip must belong to" in e for e in errors)

    def test_invalid_required_for(self) -> None:
        inventory = {
            "managed_bridge_networks": [
                {
                    "name": "mynet",
                    "driver": "bridge",
                    "subnet": "172.20.0.0/16",
                    "gateway_ip": "172.20.0.1/16",
                    "required_for": [123],
                }
            ]
        }
        errors = managed_bridge_network_declaration_errors(inventory)
        assert any("required_for" in e and "string list" in e for e in errors)

    def test_multiple_networks(self) -> None:
        inventory = {
            "managed_bridge_networks": [
                {
                    "name": "net1",
                    "driver": "bridge",
                    "subnet": "172.20.0.0/16",
                    "gateway_ip": "172.20.0.1/16",
                },
                {
                    "name": "net2",
                    "driver": "bridge",
                    "subnet": "172.21.0.0/16",
                    "gateway_ip": "172.21.0.1/16",
                },
            ]
        }
        errors = managed_bridge_network_declaration_errors(inventory)
        assert errors == []


# ---------------------------------------------------------------------------
# Golden test
# ---------------------------------------------------------------------------


@pytest.mark.golden
class TestNetworksGolden:
    def test_valid_and_invalid_mixed(self) -> None:
        """First network valid, second has bad gateway — only second errors."""
        inventory = {
            "managed_bridge_networks": [
                {
                    "name": "good",
                    "driver": "bridge",
                    "subnet": "172.20.0.0/16",
                    "gateway_ip": "172.20.0.1/16",
                },
                {
                    "name": "bad",
                    "driver": "bridge",
                    "subnet": "172.21.0.0/16",
                    "gateway_ip": "10.0.0.1/16",
                },
            ]
        }
        errors = managed_bridge_network_declaration_errors(inventory)
        assert len(errors) == 1
        assert "managed_bridge_networks[1]" in errors[0]
        assert "gateway_ip must belong to" in errors[0]
