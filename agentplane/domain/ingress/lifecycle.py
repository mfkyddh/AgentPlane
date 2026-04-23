from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from agentplane.runtime.workspace import resolve_workspace_from_repo
from agentplane.domain.ingress.models import IngressDefinition, IngressFollowThrough
from agentplane.domain.ingress.registry import (
    SUPPORTED_INGRESS_TARGETS,
    resolve_ingress_verification_profile,
)

PAYLOAD_KEYS = (
    "alias",
    "primary_domain",
    "public_url",
    "proxy",
    "status",
    "config_file",
    "ssl_id",
    "certificate_mode",
    "control_plane",
)
WORKSPACE = resolve_workspace_from_repo(Path(__file__).resolve().parents[3])
REPO_ROOT = WORKSPACE.control_root


def summarize_ingress(definition: IngressDefinition) -> dict[str, Any]:
    return {
        "alias": definition.alias,
        "primary_domain": definition.primary_domain,
        "public_url": definition.public_url,
        "proxy": definition.proxy,
        "status": definition.status,
        "config_file": definition.config_file,
        "ssl_id": definition.ssl_id,
        "certificate_mode": definition.certificate_mode,
        "control_plane": definition.control_plane,
    }


def build_ingress_follow_through(target: str, *, source_surface: str, alias: str | None = None) -> dict[str, Any]:
    profile = resolve_ingress_verification_profile(target)
    verify_cmd = (
        f"uv run python -m agentplane.cli projection verification run "
        f"--target {target} --profile {profile} --repo-root {REPO_ROOT}"
    )
    if alias:
        verify_cmd = f"{verify_cmd} --website-alias {alias}"
    ledger_cmd = (
        f"uv run python -m agentplane.cli projection ledger refresh "
        f"--target {target} --repo-root {REPO_ROOT} --write"
    )
    follow_through = IngressFollowThrough(
        owner_surface="projection",
        source_surface=source_surface,
        verification_profile=profile,
        verification_command=verify_cmd,
        ledger_refresh_command=ledger_cmd,
        notes=(
            "ingress publish/reconcile 只负责入口对象变更，projection 承接验证与台帐刷新。",
            "如需写入验证报告，可在 verification 命令追加 --write-report。",
        ),
    )
    return follow_through.as_dict()


def plan_ingress_truth_onboard(repo_root: Path | str, target: str, definition: IngressDefinition) -> dict[str, Any]:
    resolved_root = Path(repo_root).resolve()
    _validate_target(target)
    payload = _definition_payload(definition)
    inventory_path = _inventory_file(resolved_root, target)
    entries = _public_ingresses_snapshot(_load_inventory(inventory_path))
    index, existing = _find_alias(entries, definition.alias)
    if index is None:
        drift = {"status": "missing", "failures": ["missing"]}
        steps = [
            {
                "kind": "append",
                "description": "add website truth entry to services.public_ingresses",
                "path": str(inventory_path),
                "payload": dict(payload),
            }
        ]
    else:
        if _payload_matches(existing, payload):
            drift = {"status": "matched", "failures": []}
            steps = []
        else:
            drift = {"status": "drift", "failures": ["mismatch"]}
            steps = [
                {
                    "kind": "replace",
                    "description": "update services.public_ingresses entry to match definition",
                    "path": str(inventory_path),
                    "payload": dict(payload),
                    "previous": dict(existing),
                }
            ]
    return _build_plan(
        target=target,
        alias=definition.alias,
        definition=summarize_ingress(definition),
        operation="onboard",
        drift=drift,
        steps=steps,
        source_surface="ingress.truth.onboard",
    )


def apply_ingress_truth_onboard(repo_root: Path | str, target: str, definition: IngressDefinition, *, execute: bool) -> dict[str, Any]:
    if not execute:
        raise ValueError("website truth onboarding apply requires --execute")
    resolved_root = Path(repo_root).resolve()
    plan = plan_ingress_truth_onboard(resolved_root, target, definition)
    payload = _definition_payload(definition)
    action = "noop"
    drift_status = plan["drift"]["status"]
    if drift_status == "missing":
        _append_ingress(resolved_root, target, payload)
        action = "created"
    elif drift_status == "drift":
        _replace_ingress(resolved_root, target, definition.alias, payload)
        action = "updated"
    verified = plan_ingress_truth_onboard(resolved_root, target, definition)
    return {
        "definition": plan["definition"],
        "operation": "onboard",
        "target": target,
        "result": {"action": action},
        "plan": plan,
        "verified": verified,
        "follow_through": plan["follow_through"],
    }


def plan_ingress_truth_offboard(repo_root: Path | str, target: str, alias: str) -> dict[str, Any]:
    resolved_root = Path(repo_root).resolve()
    _validate_target(target)
    inventory_path = _inventory_file(resolved_root, target)
    entries = _public_ingresses_snapshot(_load_inventory(inventory_path))
    index, existing = _find_alias(entries, alias)
    if index is None:
        drift = {"status": "matched", "failures": []}
        steps: list[dict[str, Any]] = []
    else:
        drift = {"status": "drift", "failures": ["present"]}
        steps = [
            {
                "kind": "remove",
                "description": "remove website truth entry from services.public_ingresses",
                "path": str(inventory_path),
                "payload": dict(existing),
            }
        ]
    return _build_plan(
        target=target,
        alias=alias,
        definition={"alias": alias},
        operation="offboard",
        drift=drift,
        steps=steps,
        source_surface="ingress.truth.offboard",
    )


def apply_ingress_truth_offboard(repo_root: Path | str, target: str, alias: str, *, execute: bool) -> dict[str, Any]:
    if not execute:
        raise ValueError("website truth offboarding apply requires --execute")
    resolved_root = Path(repo_root).resolve()
    plan = plan_ingress_truth_offboard(resolved_root, target, alias)
    action = "noop"
    if plan["drift"]["status"] == "drift":
        _remove_ingress(resolved_root, target, alias)
        action = "removed"
    verified = plan_ingress_truth_offboard(resolved_root, target, alias)
    return {
        "definition": plan["definition"],
        "operation": "offboard",
        "target": target,
        "result": {"action": action},
        "plan": plan,
        "verified": verified,
        "follow_through": plan["follow_through"],
    }


def _build_plan(
    *,
    target: str,
    alias: str,
    definition: dict[str, Any],
    operation: str,
    drift: dict[str, Any],
    steps: Iterable[dict[str, Any]],
    source_surface: str,
) -> dict[str, Any]:
    return {
        "definition": dict(definition),
        "operation": operation,
        "target": target,
        "preflight": {"target": target, "alias": alias},
        "drift": drift,
        "steps": list(steps),
        "warnings": [],
        "verify_after_apply": {"surface": "website.truth", "action": "verify", "alias": alias},
        "follow_through": build_ingress_follow_through(target, source_surface=source_surface, alias=alias),
    }


def _definition_payload(definition: IngressDefinition) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "alias": definition.alias,
        "primary_domain": definition.primary_domain,
        "public_url": definition.public_url,
        "proxy": definition.proxy,
    }
    if definition.status:
        payload["status"] = definition.status
    if definition.config_file:
        payload["config_file"] = definition.config_file
    if definition.ssl_id is not None:
        payload["ssl_id"] = definition.ssl_id
    if definition.certificate_mode:
        payload["certificate_mode"] = definition.certificate_mode
    if definition.control_plane and definition.control_plane != "onepanel":
        payload["control_plane"] = definition.control_plane
    return payload


def _validate_target(target: str) -> None:
    if target not in SUPPORTED_INGRESS_TARGETS:
        raise ValueError(f"unsupported ingress target: {target}")


def _inventory_file(repo_root: Path, target: str) -> Path:
    return repo_root / "inventory" / "servers" / target / "inventory.json"


def _load_inventory(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"缺少 inventory 文件: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"inventory 顶层必须是对象: {path}")
    return payload


def _dump_inventory(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _public_ingresses_snapshot(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    services = inventory.get("services")
    if not isinstance(services, dict):
        return []
    candidate = services.get("public_ingresses")
    if not isinstance(candidate, list):
        return []
    return [item for item in candidate if isinstance(item, dict)]


def _ensure_public_ingresses(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    services = inventory.setdefault("services", {})
    if not isinstance(services, dict):
        raise ValueError("inventory.services must be an object")
    websites = services.setdefault("public_ingresses", [])
    if not isinstance(websites, list):
        raise ValueError("inventory.services.public_ingresses must be a list")
    return websites


def _find_alias(entries: Iterable[dict[str, Any]], alias: str) -> tuple[int | None, dict[str, Any] | None]:
    for index, item in enumerate(entries):
        if item.get("alias") == alias:
            return index, item
    return None, None


def _payload_matches(existing: dict[str, Any], payload: dict[str, Any]) -> bool:
    for key, value in payload.items():
        if existing.get(key) != value:
            return False
    return True


def _append_ingress(repo_root: Path, target: str, payload: dict[str, Any]) -> None:
    inventory_path = _inventory_file(repo_root, target)
    inventory = _load_inventory(inventory_path)
    websites = _ensure_public_ingresses(inventory)
    websites.append(dict(payload))
    _dump_inventory(inventory_path, inventory)


def _replace_ingress(repo_root: Path, target: str, alias: str, payload: dict[str, Any]) -> None:
    inventory_path = _inventory_file(repo_root, target)
    inventory = _load_inventory(inventory_path)
    websites = _ensure_public_ingresses(inventory)
    for index, item in enumerate(websites):
        if item.get("alias") == alias:
            websites[index] = dict(payload)
            _dump_inventory(inventory_path, inventory)
            return
    raise RuntimeError(f"unable to replace ingress truth entry: {alias}")


def _remove_ingress(repo_root: Path, target: str, alias: str) -> None:
    inventory_path = _inventory_file(repo_root, target)
    inventory = _load_inventory(inventory_path)
    websites = _ensure_public_ingresses(inventory)
    for index, item in enumerate(websites):
        if item.get("alias") == alias:
            websites.pop(index)
            _dump_inventory(inventory_path, inventory)
            return
    raise RuntimeError(f"unable to remove ingress truth entry: {alias}")
