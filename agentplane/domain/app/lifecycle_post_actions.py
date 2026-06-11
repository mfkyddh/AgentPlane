"""Post-delivery actions and step payload builders."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from agentplane.domain.app.projection.runtime_env import (
    apply_runtime_env_projection,
    plan_runtime_env_projection,
)
from agentplane.domain.app.projection_lifecycle import default_offboarding_plan, default_onboarding_plan
from agentplane.domain.app.truth_lifecycle import CatalogMutationResult, load_json_file
from agentplane.domain.service.lifecycle import plan_service_registry_offboard, plan_service_registry_onboard

if TYPE_CHECKING:
    from agentplane.domain.app.lifecycle import ValidatedDeliveryContract
    from agentplane.domain.app.models import AppCatalogEntry


def _record_step(action: str, *, write: bool, ok: bool, changed: bool, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "action": action,
        "write": write,
        "ok": ok,
        "changed": changed,
        "payload": payload,
    }


def _catalog_entry_from_validated(validated: ValidatedDeliveryContract, *, target: str) -> AppCatalogEntry:
    from agentplane.domain.app.models import AppCatalogEntry

    service_key = str(validated.contract.get("inventory", {}).get("service_key") or validated.app)
    contracts = dict(validated.catalog_entry.contracts) if validated.catalog_entry is not None else {}
    contracts[target] = validated.contract_relpath
    return AppCatalogEntry(
        app=validated.app,
        repo_name=validated.repo_name,
        repo_root=validated.app_root,
        service_key=service_key,
        contracts=contracts,
    )


def _ingress_sites(contract: dict[str, Any]) -> list[dict[str, Any]]:
    top_level = contract.get("public_sites")
    if isinstance(top_level, list):
        return [site for site in top_level if isinstance(site, dict)]
    ingress_sites = contract.get("ingress", {}).get("public_sites")
    if isinstance(ingress_sites, list):
        return [site for site in ingress_sites if isinstance(site, dict)]
    return []


def _service_entry_from_validated(validated: ValidatedDeliveryContract) -> dict[str, Any]:
    runtime = validated.contract.get("runtime", {})
    host_binding = runtime.get("host_binding")
    entry: dict[str, Any] = {
        "container_name": str(runtime.get("container_name") or f"{validated.app}-prod"),
        "control_plane": "compose",
    }
    if isinstance(host_binding, str) and host_binding:
        entry["host_binding"] = host_binding
    public_sites = _ingress_sites(validated.contract)
    if public_sites:
        public_url = public_sites[0].get("public_url")
        if isinstance(public_url, str) and public_url:
            entry["public_url"] = public_url
    return entry


def _target_policy_summary(repo_root: Path, *, target: str) -> dict[str, Any]:
    if target == "wsl":
        from agentplane.domain.app.lifecycle_wsl import lane2_policy_helper as wsl_policy_helper

        return wsl_policy_helper()
    if target == "prod0-main":
        from agentplane.domain.app.lifecycle_prod0_main import lane2_policy_helper as prod0_policy_helper

        return prod0_policy_helper()
    return {"target": target}


def _catalog_step_payload(result: CatalogMutationResult) -> dict[str, Any]:
    return {
        "path": str(result.path),
        "before_count": result.before_count,
        "after_count": result.after_count,
        "entry": None
        if result.entry is None
        else {
            "app": result.entry.app,
            "repo_name": result.entry.repo_name,
            "repo_root": str(result.entry.repo_root),
            "service_key": result.entry.service_key,
            "contracts": dict(result.entry.contracts),
        },
    }


def _plan_service_step(repo_root: Path, *, target: str, service_key: str, entry: dict[str, Any]) -> dict[str, Any]:
    inventory_payload = load_json_file(repo_root / "inventory" / "servers" / target / "inventory.json")
    services = inventory_payload.get("services")
    next_services, evidence = plan_service_registry_onboard(
        services, service_key=service_key, entry=entry, allow_replace=True
    )
    return {"services_after": sorted(next_services), "evidence": evidence}


def _plan_service_removal_step(repo_root: Path, *, target: str, service_key: str) -> dict[str, Any]:
    inventory_payload = load_json_file(repo_root / "inventory" / "servers" / target / "inventory.json")
    services = inventory_payload.get("services")
    try:
        next_services, evidence = plan_service_registry_offboard(services, service_key=service_key)
        return {"services_after": sorted(next_services), "evidence": evidence, "present": True}
    except ValueError:
        return {
            "services_after": sorted((services or {}).keys()) if isinstance(services, dict) else [],
            "present": False,
        }


def _planned_post_actions(
    validated: ValidatedDeliveryContract, *, target: str, write: bool, intent: str
) -> dict[str, Any]:
    projection_plan = (
        default_onboarding_plan(dry_run=not write)
        if intent == "onboard"
        else default_offboarding_plan(dry_run=not write)
    )
    return {
        "ok": True,
        "write": write,
        "steps": [
            {
                "action": "projection.runtime-env.apply" if write else "projection.runtime-env.plan",
                "write": write,
                "ok": True,
                "payload": projection_plan.summary(),
            },
            {
                "action": "app.delivery.inventory-refresh",
                "write": write,
                "ok": True,
                "payload": {"planned": True, "contract_paths": [str(validated.contract_file)], "target": target},
            },
            {
                "action": "app.delivery.doc-sync",
                "write": write,
                "ok": True,
                "payload": {
                    "planned": True,
                    "target": target,
                    "server_readme": str(Path("inventory") / "servers" / target / "README.md"),
                    "app_docs": [str(validated.contract.get("docs", {}))],
                },
            },
        ],
    }


def run_delivery_post_actions(
    repo_root: Path,
    *,
    target: str,
    app: str,
    app_repo_root: str | None = None,
    write: bool,
    write_evidence: bool,
    evidence_action: str,
    evidence_op_prefix: str,
    deploy_operation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from agentplane.domain.app.lifecycle import load_validated_delivery_contract

    validated = load_validated_delivery_contract(repo_root, target=target, app=app, app_repo_root=app_repo_root)
    app_cli = validated.app_cli
    contract_file = validated.contract_file

    try:
        projection_payload = (
            apply_runtime_env_projection(repo_root, target, app)
            if write
            else plan_runtime_env_projection(repo_root, target, app)
        )
    except (FileNotFoundError, ValueError) as exc:
        projection_payload = {
            "ok": True,
            "skipped": True,
            "reason": str(exc),
            "target": target,
            "app": app,
        }
    steps: list[dict[str, Any]] = [
        {
            "action": "projection.runtime-env.apply" if write else "projection.runtime-env.plan",
            "write": write,
            "ok": bool(projection_payload.get("ok", False)),
            "payload": projection_payload,
        }
    ]
    error: dict[str, Any] | None = None
    if projection_payload.get("ok", False):
        try:
            inventory_payload = app_cli.inventory_refresh(
                repo_root=repo_root, target=target, contract_paths=[contract_file], write=write
            )
            steps.append(
                {
                    "action": "app.delivery.inventory-refresh",
                    "write": write,
                    "ok": True,
                    "payload": inventory_payload,
                }
            )
            doc_payload = app_cli.doc_sync(
                repo_root=repo_root, target=target, contract_paths=[contract_file], write=write
            )
            steps.append(
                {
                    "action": "app.delivery.doc-sync",
                    "write": write,
                    "ok": True,
                    "payload": doc_payload,
                }
            )
        except Exception as exc:  # pragma: no cover
            error = {"message": str(exc), "type": type(exc).__name__}
            steps.append(
                {
                    "action": "app.delivery.sequence",
                    "write": write,
                    "ok": False,
                    "error": error,
                }
            )
    else:
        error = {"message": "projection runtime-env post-action failed", "type": "RuntimeError"}
    ok = error is None
    evidence: dict[str, Any] | None = None
    if write_evidence:
        evidence_op_id = app_cli.next_operation_id(evidence_op_prefix)
        details: dict[str, Any] = {
            "artifact_summary": f"{app} projection/inventory/doc-sync",
            "write": write,
            "post_actions": [item.get("action", "") for item in steps],
        }
        if deploy_operation is not None:
            details["deploy_operation_op_id"] = str(deploy_operation.get("op_id", ""))
        if error is not None:
            details["post_actions_error"] = error
        operation = app_cli._record_app_operation(
            repo_root,
            action=evidence_action,
            target=target,
            dry_run=not write,
            operation={
                "op_id": evidence_op_id,
                "target": target,
                "result": "post-actions-synced" if ok else "post-actions-failed",
            },
            details=details,
        )
        evidence = {"ledger_file": operation["ledger_file"], "operation": operation}
    payload: dict[str, Any] = {"ok": ok, "write": write, "steps": steps}
    if error is not None:
        payload["error"] = error
    if evidence is not None:
        payload["evidence"] = evidence
    return payload
