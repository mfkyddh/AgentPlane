from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from agentplane.domain.app.object_handlers import (
    _contract_payload,
    get_app,
    search_apps,
)
from agentplane.domain.project.topology import build_topology
from agentplane.domain.targets import FORMAL_TARGETS
from agentplane.web.api_helpers import _host_status, _load_inventory

logger = logging.getLogger(__name__)


def get_dashboard(repo_root: Path) -> dict[str, Any]:
    """Single endpoint: read inventory once, return all dashboard data."""
    all_hosts = []
    all_apps = []
    all_operations = []
    total_containers = 0
    total_compose = 0
    infra_hosts = []
    service_items = []
    ingress_items = []

    for target in FORMAL_TARGETS:
        inventory = _load_inventory(repo_root, target)
        if not inventory:
            continue

        ssh = inventory.get("ssh", {})
        all_hosts.append({
            "target": target,
            "hostname": inventory.get("hostname", target),
            "ip": ssh.get("infra", inventory.get("public_ip", "")),
            "label": inventory.get("label", target),
            "provider": inventory.get("provider", ""),
            "status": _host_status(inventory),
            "last_seen": inventory.get("object_ledgers", {}).get("generated_at", ""),
        })

        containers = inventory.get("docker_containers", [])
        compose = inventory.get("compose_services", [])
        container_count = len(containers) if isinstance(containers, list) else 0
        compose_count = len(compose) if isinstance(compose, list) else 0
        total_containers += container_count
        total_compose += compose_count
        infra_hosts.append({
            "target": target,
            "hostname": inventory.get("hostname", target),
            "ip": ssh.get("infra", inventory.get("public_ip", "")),
            "label": inventory.get("label", target),
            "provider": inventory.get("provider", ""),
            "status": _host_status(inventory),
            "containers": container_count,
            "compose_services": compose_count,
        })

        last_ops = inventory.get("object_ledgers", {}).get("last_operations", {})
        if isinstance(last_ops, dict):
            for object_type, op in last_ops.items():
                if isinstance(op, dict):
                    all_operations.append({
                        "timestamp": op.get("timestamp", ""),
                        "target": target,
                        "object_type": object_type,
                        "action": op.get("action", ""),
                        "result": op.get("result", ""),
                        "op_id": op.get("op_id", ""),
                    })

    all_operations.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    for target in FORMAL_TARGETS:
        result = search_apps(repo_root, target, include_resolved_path=False)
        for item in result.get("items", []):
            item["target"] = target
            all_apps.append(item)

    topology = build_topology(repo_root)

    app_count = len(all_apps)
    host_count = len(all_hosts)
    domain_infra = {"host_count": host_count, "total_containers": total_containers, "total_compose_services": total_compose}
    domain_app = {"app_count": app_count}

    try:
        from agentplane.domain.service.handlers import search_services
        for target in FORMAL_TARGETS:
            for item in search_services(repo_root, target).get("items", []):
                item["target"] = target
                service_items.append(item)
    except Exception:
        logger.debug("Failed to load service data", exc_info=True)
    domain_service = {"service_count": len(service_items)}

    try:
        from agentplane.domain.ingress.handlers import search_ingresses
        for target in FORMAL_TARGETS:
            for item in search_ingresses(repo_root, target).get("items", []):
                item["target"] = target
                ingress_items.append(item)
    except Exception:
        logger.debug("Failed to load ingress data", exc_info=True)
    domain_ingress = {"ingress_count": len(ingress_items)}

    domain_project: dict[str, Any] = {}
    try:
        from agentplane.domain.project.status import build_repo_status
        status = build_repo_status(repo_root)
        domain_project = {
            "ok": status.get("ok", False),
            "targets": status.get("targets", {}).get("count", 0),
            "apps": status.get("apps", {}).get("count", 0),
            "public_skills": status.get("checks", {}).get("skills", {}).get("count", 0),
        }
        roadmap = status.get("roadmap", {})
        if roadmap.get("ok"):
            current_phase = roadmap.get("current_phase")
            if current_phase:
                domain_project["current_phase"] = current_phase.get("id", "")
                domain_project["phase_status"] = current_phase.get("status", "")
    except Exception:
        logger.debug("Failed to load project data", exc_info=True)

    return {
        "hosts": all_hosts,
        "apps": all_apps,
        "operations": all_operations,
        "topology": topology,
        "domains": {
            "infra": domain_infra,
            "service": domain_service,
            "app": domain_app,
            "ingress": domain_ingress,
            "project": domain_project,
        },
    }


def get_capabilities() -> dict[str, Any]:
    """Return static capability tree from capabilities.json."""

    data_file = Path(__file__).parent / "static" / "data" / "capabilities.json"
    if not data_file.exists():
        return {
            "ok": False,
            "payload": None,
            "error": {
                "code": "capabilities.not_found",
                "hint": "capabilities.json not found in static/data/",
                "message": "Capability data file is missing.",
            },
            "evidence": [],
            "artifacts": [],
        }
    try:
        return json.loads(data_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return {
            "ok": False,
            "payload": None,
            "error": {
                "code": "capabilities.load_failed",
                "hint": "Failed to parse capabilities.json.",
                "message": str(exc),
            },
            "evidence": [],
            "artifacts": [],
        }


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


def get_audit_log(repo_root: Path, limit: int = 100, target: str | None = None) -> dict[str, Any]:
    """Return operation audit log from JSONL ledger files."""
    
    ledger_dir = repo_root / "tmp" / "operation-ledger"
    if not ledger_dir.exists():
        return {"entries": [], "total": 0}
    
    entries = []
    for ledger_file in sorted(ledger_dir.glob("*.jsonl"), reverse=True):
        try:
            with ledger_file.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        if target and entry.get("target") != target:
                            continue
                        entries.append(entry)
                    except json.JSONDecodeError:
                        continue
        except OSError:
            continue
        
        if len(entries) >= limit:
            break
    
    entries.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    entries = entries[:limit]
    
    return {
        "entries": entries,
        "total": len(entries),
    }
