from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from agentplane.domain.app.object_handlers import search_apps
from agentplane.domain.targets import FORMAL_TARGETS


def _inventory_path(repo_root: Path, target: str) -> Path:
    return repo_root / "inventory" / "servers" / target / "inventory.json"


def _load_inventory(repo_root: Path, target: str) -> dict[str, Any]:
    inventory_file = _inventory_path(repo_root, target)
    if not inventory_file.exists():
        return {}
    try:
        return json.loads(inventory_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _host_status(inventory: dict[str, Any]) -> str:
    has_services = bool(inventory.get("services"))
    return "connected" if has_services else "unknown"


def list_hosts(repo_root: Path) -> dict[str, Any]:
    hosts = []
    for target in FORMAL_TARGETS:
        inventory = _load_inventory(repo_root, target)
        if not inventory:
            continue
        ssh = inventory.get("ssh", {})
        hosts.append({
            "target": target,
            "hostname": inventory.get("hostname", target),
            "ip": ssh.get("infra", inventory.get("public_ip", "")),
            "label": inventory.get("label", target),
            "provider": inventory.get("provider", ""),
            "status": _host_status(inventory),
            "last_seen": inventory.get("object_ledgers", {}).get("generated_at", ""),
        })
    return {"hosts": hosts}


def list_apps(repo_root: Path) -> dict[str, Any]:
    all_items = []
    for target in FORMAL_TARGETS:
        result = search_apps(repo_root, target, include_resolved_path=False)
        all_items.extend(result.get("items", []))
    return {"apps": all_items}


def list_operations(repo_root: Path) -> dict[str, Any]:
    operations = []
    for target in FORMAL_TARGETS:
        inventory = _load_inventory(repo_root, target)
        if not inventory:
            continue
        last_ops = inventory.get("object_ledgers", {}).get("last_operations", {})
        if not isinstance(last_ops, dict):
            continue
        for object_type, op in last_ops.items():
            if not isinstance(op, dict):
                continue
            operations.append({
                "timestamp": op.get("timestamp", ""),
                "target": target,
                "object_type": object_type,
                "action": op.get("action", ""),
                "result": op.get("result", ""),
                "op_id": op.get("op_id", ""),
            })
    operations.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return {"operations": operations}


def get_data_mtime(repo_root: Path) -> dict[str, Any]:
    max_mtime = 0.0
    for target in FORMAL_TARGETS:
        path = _inventory_path(repo_root, target)
        if path.exists():
            try:
                mt = os.stat(path).st_mtime
                if mt > max_mtime:
                    max_mtime = mt
            except OSError:
                pass
    return {"mtime": max_mtime}
