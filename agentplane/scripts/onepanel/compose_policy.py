#!/usr/bin/env python3
"""Compose normalization rules for repository-managed 1Panel app installs."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import yaml


DEFAULT_NETWORK = "zqf_network"
LEGACY_NETWORK = "1panel-network"
HOST_NETWORK_APP_KEYS = {"openresty"}


def requires_host_network(app_key: str) -> bool:
    return app_key in HOST_NETWORK_APP_KEYS


def _normalize_service_networks(value: Any, required_network: str) -> Any:
    if value is None:
        return [required_network]
    if isinstance(value, list):
        networks = [required_network if item == LEGACY_NETWORK else item for item in value]
        if required_network not in networks:
            networks.append(required_network)
        return networks
    if isinstance(value, dict):
        normalized = {}
        for key, item in value.items():
            normalized_key = required_network if key == LEGACY_NETWORK else key
            normalized[normalized_key] = item
        normalized.setdefault(required_network, None)
        return normalized
    return [required_network]


def enforce_zqf_network(raw_compose: str, required_network: str = DEFAULT_NETWORK) -> str:
    compose = yaml.safe_load(raw_compose) or {}
    if not isinstance(compose, dict):
        raise ValueError("Compose content must decode to a mapping")

    compose = deepcopy(compose)
    services = compose.get("services")
    if not isinstance(services, dict) or not services:
        raise ValueError("Compose content must include services")

    networks = compose.get("networks")
    if not isinstance(networks, dict):
        networks = {}
    if LEGACY_NETWORK in networks and required_network not in networks:
        networks[required_network] = networks.pop(LEGACY_NETWORK)
    networks.setdefault(required_network, {"external": True})
    compose["networks"] = networks

    for service_name, service in services.items():
        if not isinstance(service, dict):
            raise ValueError(f"Service {service_name} must be a mapping")
        service["networks"] = _normalize_service_networks(service.get("networks"), required_network)

    return yaml.safe_dump(compose, sort_keys=False, allow_unicode=False)


def enforce_host_network(raw_compose: str) -> str:
    compose = yaml.safe_load(raw_compose) or {}
    if not isinstance(compose, dict):
        raise ValueError("Compose content must decode to a mapping")

    compose = deepcopy(compose)
    services = compose.get("services")
    if not isinstance(services, dict) or not services:
        raise ValueError("Compose content must include services")

    compose.pop("networks", None)
    for service_name, service in services.items():
        if not isinstance(service, dict):
            raise ValueError(f"Service {service_name} must be a mapping")
        service.pop("networks", None)
        service["network_mode"] = "host"

    return yaml.safe_dump(compose, sort_keys=False, allow_unicode=False)


def normalize_compose_for_app(app_key: str, raw_compose: str) -> str:
    if requires_host_network(app_key):
        return enforce_host_network(raw_compose)
    return enforce_zqf_network(raw_compose)
