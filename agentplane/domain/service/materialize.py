from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml
from agentplane.domain.service.models import ServiceDefinition

ARTIFACT_CLASH_LOCAL_PROFILE = "clash-local-profile"
SUPPORTED_SERVICE_ARTIFACTS = (ARTIFACT_CLASH_LOCAL_PROFILE,)
DIRECT_TOKENS = {"DIRECT", "REJECT", "REJECT-DROP", "PASS", "GLOBAL", "直接连接"}


def _new_trojan_node(*, node_name: str, server: str, port: int, password: str, sni: str) -> dict[str, Any]:
    return {
        "name": node_name,
        "type": "trojan",
        "server": server,
        "port": port,
        "password": password,
        "sni": sni,
        "udp": True,
        "skip-cert-verify": False,
    }


def _effective_rules(source_rules: Any, merge_template: dict[str, Any] | None) -> list[Any]:
    rules = list(source_rules) if isinstance(source_rules, list) else []
    if not isinstance(merge_template, dict):
        return rules

    prepend_rules = merge_template.get("prepend__rules")
    if isinstance(prepend_rules, list):
        rules = list(prepend_rules) + rules

    append_rules = merge_template.get("append__rules")
    if isinstance(append_rules, list):
        rules.extend(append_rules)

    return rules


def render_clash_local_profile(
    source: dict[str, Any],
    *,
    merge_template: dict[str, Any] | None,
    node_name: str,
    server: str,
    port: int,
    password: str,
    sni: str,
) -> dict[str, Any]:
    rendered = deepcopy(source)
    source_proxy_names = {
        proxy.get("name")
        for proxy in source.get("proxies", [])
        if isinstance(proxy, dict) and isinstance(proxy.get("name"), str)
    }
    group_names = {
        group.get("name")
        for group in source.get("proxy-groups", [])
        if isinstance(group, dict) and isinstance(group.get("name"), str)
    }

    rendered["proxies"] = [_new_trojan_node(node_name=node_name, server=server, port=port, password=password, sni=sni)]
    for group in rendered.get("proxy-groups", []):
        proxies = group.get("proxies")
        if not isinstance(proxies, list):
            continue

        next_proxies: list[str] = []
        for item in proxies:
            if not isinstance(item, str):
                continue
            if item in DIRECT_TOKENS or item in group_names:
                if item not in next_proxies:
                    next_proxies.append(item)
                continue
            if item in source_proxy_names:
                if node_name not in next_proxies:
                    next_proxies.append(node_name)
                continue
            if item not in next_proxies:
                next_proxies.append(item)

        group["proxies"] = next_proxies

    rendered["rules"] = _effective_rules(source.get("rules"), merge_template)
    return rendered


def materialize_service_artifact(
    definition: ServiceDefinition,
    declared: dict[str, Any] | None,
    *,
    artifact: str,
    source: Path,
    merge_template: Path | None,
    output: Path,
    password: str,
    node_name: str = "",
    server: str = "",
    port: int | None = None,
    sni: str = "",
) -> dict[str, Any]:
    if artifact != ARTIFACT_CLASH_LOCAL_PROFILE:
        raise ValueError(f"unsupported service artifact: {artifact}")
    if not isinstance(declared, dict):
        raise ValueError(f"service {definition.name} does not expose tracked artifact metadata")

    profile = declared.get("client_profile")
    if profile is not None and not isinstance(profile, dict):
        raise ValueError(f"service {definition.name} client_profile must be an object")
    profile_contract = profile if isinstance(profile, dict) else {}
    declared_format = profile_contract.get("format")
    if declared_format is not None and declared_format != artifact:
        raise ValueError(f"service {definition.name} does not support artifact {artifact}")

    public_endpoint = declared.get("public_endpoint")
    endpoint_contract = public_endpoint if isinstance(public_endpoint, dict) else {}
    resolved_server = _resolve_required_str(
        server or _string_value(profile_contract.get("server")) or _string_value(endpoint_contract.get("domain")),
        field="server",
        service_name=definition.name,
    )
    resolved_port = _resolve_required_port(
        port if port is not None else profile_contract.get("port", endpoint_contract.get("port")),
        service_name=definition.name,
    )
    resolved_node_name = _resolve_required_str(
        node_name or _string_value(profile_contract.get("node_name")) or definition.name,
        field="node_name",
        service_name=definition.name,
    )
    resolved_sni = _resolve_required_str(
        sni or _string_value(profile_contract.get("sni")) or resolved_server,
        field="sni",
        service_name=definition.name,
    )

    source_payload = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    if not isinstance(source_payload, dict):
        raise ValueError(f"artifact source must be a YAML object: {source}")
    merge_payload: dict[str, Any] | None = None
    if merge_template is not None:
        loaded_merge = yaml.safe_load(merge_template.read_text(encoding="utf-8")) or {}
        if not isinstance(loaded_merge, dict):
            raise ValueError(f"artifact merge template must be a YAML object: {merge_template}")
        merge_payload = loaded_merge

    rendered = render_clash_local_profile(
        source_payload,
        merge_template=merge_payload,
        node_name=resolved_node_name,
        server=resolved_server,
        port=resolved_port,
        password=password,
        sni=resolved_sni,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(yaml.safe_dump(rendered, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return {
        "ok": True,
        "artifact": artifact,
        "output": str(output),
        "resolved": {
            "node_name": resolved_node_name,
            "server": resolved_server,
            "port": resolved_port,
            "sni": resolved_sni,
        },
    }


def _string_value(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _resolve_required_str(value: str, *, field: str, service_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"service {service_name} requires a non-empty {field}")
    return normalized


def _resolve_required_port(value: Any, *, service_name: str) -> int:
    if isinstance(value, int):
        resolved = value
    elif isinstance(value, str) and value.strip().isdigit():
        resolved = int(value.strip())
    else:
        raise ValueError(f"service {service_name} requires a valid port")
    if resolved <= 0:
        raise ValueError(f"service {service_name} requires a valid port")
    return resolved
