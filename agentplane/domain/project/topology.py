from __future__ import annotations

from pathlib import Path
from typing import Any

from agentplane.domain.app.object_handlers import _contract_payload, get_app, search_apps
from agentplane.domain.service.handlers import search_services
from agentplane.domain.targets import FORMAL_TARGETS


def _load_inventory(repo_root: Path, target: str) -> dict[str, Any]:
    import json

    inventory_file = repo_root / "inventory" / "servers" / target / "inventory.json"
    if not inventory_file.exists():
        return {}
    try:
        return json.loads(inventory_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _host_status(inventory: dict[str, Any]) -> str:
    has_services = bool(inventory.get("services"))
    return "connected" if has_services else "unknown"


def _extract_dependencies(contract: dict[str, Any]) -> list[dict[str, Any]]:
    runtime = contract.get("runtime", {}) if isinstance(contract.get("runtime"), dict) else {}
    deps: list[dict[str, Any]] = []
    healthcheck = runtime.get("healthcheck", {})
    if isinstance(healthcheck, dict) and healthcheck.get("path"):
        deps.append({"kind": "healthcheck", "path": healthcheck["path"]})
    return deps


def _app_with_contract(repo_root: Path, target: str, app_info: dict[str, Any]) -> dict[str, Any]:
    try:
        app_detail = get_app(repo_root, target, app_info["app"])
        contract = _contract_payload(
            Path(app_detail["app"]["contract_file"])
        ) if app_detail["app"].get("contract_file") else {}
    except Exception:  # noqa: BLE001
        contract = {}
    runtime = contract.get("runtime", {}) if isinstance(contract.get("runtime"), dict) else {}
    packaging = contract.get("packaging", {}) if isinstance(contract.get("packaging"), dict) else {}
    return {
        "app": app_info.get("app", ""),
        "image": packaging.get("image_name", ""),
        "port": runtime.get("container_port"),
        "status": app_info.get("control_plane", "unknown"),
        "public_url": app_info.get("public_url", ""),
        "control_plane": app_info.get("control_plane", ""),
        "dependencies": _extract_dependencies(contract),
    }


def build_topology(repo_root: Path) -> dict[str, Any]:
    """Build the full resource topology graph."""
    from datetime import datetime, timezone

    targets: list[dict[str, Any]] = []
    for target in FORMAL_TARGETS:
        inventory = _load_inventory(repo_root, target)
        if not inventory:
            continue
        ssh = inventory.get("ssh", {})
        apps_result = search_apps(repo_root, target, include_resolved_path=False)
        apps = [_app_with_contract(repo_root, target, item) for item in apps_result.get("items", [])]
        services_result = search_services(repo_root, target)
        services = [
            {"name": s.get("name", ""), "kind": s.get("kind", ""), "status": s.get("status", "unknown")}
            for s in services_result.get("items", [])
        ]
        targets.append({
            "target": target,
            "hostname": inventory.get("hostname", target),
            "ip": ssh.get("infra", inventory.get("public_ip", "")),
            "os": inventory.get("os", ""),
            "status": _host_status(inventory),
            "apps": apps,
            "services": services,
        })
    return {
        "targets": targets,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
