from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from agentplane.domain.app.object_handlers import search_apps
from agentplane.domain.project.topology import build_topology
from agentplane.domain.targets import FORMAL_TARGETS
from agentplane.web.api_helpers import _host_status, _inventory_path, _load_inventory

logger = logging.getLogger(__name__)


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


def get_domain_infra(repo_root: Path) -> dict[str, Any]:
    try:
        hosts = []
        total_containers = 0
        total_compose = 0
        for target in FORMAL_TARGETS:
            inventory = _load_inventory(repo_root, target)
            if not inventory:
                continue
            ssh = inventory.get("ssh", {})
            containers = inventory.get("docker_containers", [])
            compose = inventory.get("compose_services", [])
            container_count = len(containers) if isinstance(containers, list) else 0
            compose_count = len(compose) if isinstance(compose, list) else 0
            total_containers += container_count
            total_compose += compose_count
            hosts.append({
                "target": target,
                "hostname": inventory.get("hostname", target),
                "ip": ssh.get("infra", inventory.get("public_ip", "")),
                "label": inventory.get("label", target),
                "provider": inventory.get("provider", ""),
                "status": _host_status(inventory),
                "containers": container_count,
                "compose_services": compose_count,
            })
        return {
            "ok": True,
            "payload": {
                "domain": "infra",
                "summary": {
                    "host_count": len(hosts),
                    "total_containers": total_containers,
                    "total_compose_services": total_compose,
                },
                "objects": hosts,
            },
            "error": None,
            "evidence": [],
            "artifacts": [],
        }
    except Exception as exc:
        return {
            "ok": False,
            "payload": None,
            "error": {
                "code": "domain.infra.fetch_failed",
                "hint": "Failed to load infrastructure inventory.",
                "message": str(exc),
            },
            "evidence": [],
            "artifacts": [],
        }


def get_domain_service(repo_root: Path) -> dict[str, Any]:
    try:
        from agentplane.domain.service.handlers import search_services

        all_items = []
        for target in FORMAL_TARGETS:
            result = search_services(repo_root, target)
            for item in result.get("items", []):
                item["target"] = target
                all_items.append(item)
        return {
            "ok": True,
            "payload": {
                "domain": "service",
                "summary": {"service_count": len(all_items)},
                "objects": all_items,
            },
            "error": None,
            "evidence": [],
            "artifacts": [],
        }
    except Exception as exc:
        return {
            "ok": False,
            "payload": None,
            "error": {
                "code": "domain.service.fetch_failed",
                "hint": "Failed to load service inventory.",
                "message": str(exc),
            },
            "evidence": [],
            "artifacts": [],
        }


def get_domain_app(repo_root: Path) -> dict[str, Any]:
    try:
        all_items = []
        for target in FORMAL_TARGETS:
            result = search_apps(repo_root, target, include_resolved_path=False)
            all_items.extend(result.get("items", []))
        return {
            "ok": True,
            "payload": {
                "domain": "app",
                "summary": {"app_count": len(all_items)},
                "objects": all_items,
            },
            "error": None,
            "evidence": [],
            "artifacts": [],
        }
    except Exception as exc:
        return {
            "ok": False,
            "payload": None,
            "error": {
                "code": "domain.app.fetch_failed",
                "hint": "Failed to load app inventory.",
                "message": str(exc),
            },
            "evidence": [],
            "artifacts": [],
        }


def get_domain_ingress(repo_root: Path) -> dict[str, Any]:
    try:
        from agentplane.domain.ingress.handlers import search_ingresses

        all_items = []
        for target in FORMAL_TARGETS:
            result = search_ingresses(repo_root, target)
            for item in result.get("items", []):
                item["target"] = target
                all_items.append(item)
        return {
            "ok": True,
            "payload": {
                "domain": "ingress",
                "summary": {"ingress_count": len(all_items)},
                "objects": all_items,
            },
            "error": None,
            "evidence": [],
            "artifacts": [],
        }
    except Exception as exc:
        return {
            "ok": False,
            "payload": None,
            "error": {
                "code": "domain.ingress.fetch_failed",
                "hint": "Failed to load ingress inventory.",
                "message": str(exc),
            },
            "evidence": [],
            "artifacts": [],
        }


def get_domain_project(repo_root: Path) -> dict[str, Any]:
    try:
        from agentplane.domain.project.status import build_repo_status

        status = build_repo_status(repo_root)
        summary = {
            "ok": status.get("ok", False),
            "targets": status.get("targets", {}).get("count", 0),
            "apps": status.get("apps", {}).get("count", 0),
            "public_skills": status.get("checks", {}).get("skills", {}).get("count", 0),
        }
        roadmap = status.get("roadmap", {})
        if roadmap.get("ok"):
            current_phase = roadmap.get("current_phase")
            if current_phase:
                summary["current_phase"] = current_phase.get("id", "")
                summary["phase_status"] = current_phase.get("status", "")
            next_task = roadmap.get("next_task")
            if next_task:
                summary["next_task"] = next_task.get("id", "")
        return {
            "ok": True,
            "payload": {
                "domain": "project",
                "summary": summary,
                "objects": status.get("targets", {}).get("items", []),
            },
            "error": None,
            "evidence": [],
            "artifacts": [],
        }
    except Exception as exc:
        return {
            "ok": False,
            "payload": None,
            "error": {
                "code": "domain.project.fetch_failed",
                "hint": "Failed to load project status.",
                "message": str(exc),
            },
            "evidence": [],
            "artifacts": [],
        }
