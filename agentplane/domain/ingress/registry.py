from __future__ import annotations

import json
from pathlib import Path

from agentplane.domain.ingress.models import IngressDefinition
from agentplane.domain.targets import SUPPORTED_INGRESS_TARGETS


INGRESS_VERIFICATION_PROFILE_BY_TARGET = {
    "wsl": "wsl-fixture",
    "prod0-main": "prod0-readonly",
    "prod2-main": "prod2-readonly",
}


def load_target_inventory(repo_root: Path, target: str) -> dict[str, object]:
    inventory_file = repo_root / "inventory" / "servers" / target / "inventory.json"
    if not inventory_file.is_file():
        raise ValueError(f"缺少 inventory 文件: {inventory_file}")
    payload = json.loads(inventory_file.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"inventory 顶层必须是对象: {inventory_file}")
    return payload


def available_ingresses(repo_root: Path, target: str) -> list[IngressDefinition]:
    inventory = load_target_inventory(repo_root, target)
    services = inventory.get("services")
    if not isinstance(services, dict):
        return []
    rows = services.get("public_ingresses")
    if not isinstance(rows, list):
        return []

    items: list[IngressDefinition] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        alias = row.get("alias")
        primary_domain = row.get("primary_domain")
        public_url = row.get("public_url")
        proxy = row.get("proxy")
        if not all(isinstance(value, str) and value for value in (alias, primary_domain, public_url, proxy)):
            continue
        ssl_id = row.get("ssl_id")
        items.append(
            IngressDefinition(
                alias=alias,
                primary_domain=primary_domain,
                public_url=public_url,
                proxy=proxy,
                status=str(row.get("status", "")),
                config_file=str(row.get("config_file", "")),
                ssl_id=int(ssl_id) if isinstance(ssl_id, int) else None,
                certificate_mode=str(row.get("certificate_mode", "")),
            )
        )
    return items


def resolve_ingress(repo_root: Path, target: str, alias: str) -> IngressDefinition:
    for item in available_ingresses(repo_root, target):
        if item.alias == alias:
            return item
    raise ValueError(f"unknown ingress for {target}: {alias}")


def resolve_ingress_verification_profile(target: str) -> str:
    try:
        return INGRESS_VERIFICATION_PROFILE_BY_TARGET[target]
    except KeyError as exc:
        raise ValueError(f"unsupported ingress target: {target}") from exc
