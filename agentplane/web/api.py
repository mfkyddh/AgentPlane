from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from agentplane.domain.app.object_handlers import (
    _contract_payload,
    get_app,
    search_apps,
)
from agentplane.domain.project.topology import build_topology
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


def get_topology(repo_root: Path) -> dict[str, Any]:
    """Return full resource graph: targets → servers → apps → dependencies."""
    return build_topology(repo_root)


def get_server_detail(repo_root: Path, target: str) -> dict[str, Any]:
    """Return full inventory payload for one target."""
    inventory = _load_inventory(repo_root, target)
    if not inventory:
        return {"error": "not_found", "target": target}
    ssh = inventory.get("ssh", {})
    return {
        "target": target,
        "hostname": inventory.get("hostname", target),
        "ip": ssh.get("infra", inventory.get("public_ip", "")),
        "os": inventory.get("os", ""),
        "label": inventory.get("label", target),
        "provider": inventory.get("provider", ""),
        "status": _host_status(inventory),
        "docker_containers": inventory.get("docker_containers", []),
        "compose_services": inventory.get("compose_services", []),
        "host_truth": inventory.get("host_truth", {}),
    }


def get_app_detail(repo_root: Path, target: str, app: str) -> dict[str, Any]:
    """Return app object info with contract details."""
    try:
        detail = get_app(repo_root, target, app)
    except Exception:  # noqa: BLE001
        return {"error": "not_found", "target": target, "app": app}
    contract = _contract_payload(
        Path(detail["app"]["contract_file"])
    ) if detail["app"].get("contract_file") else {}
    return {
        "app": detail["app"],
        "inventory_entry": detail.get("inventory_entry", {}),
        "contract": contract,
        "summary_files": detail.get("summary_files", []),
        "ledger_status": detail.get("ledger_status", {}),
    }
