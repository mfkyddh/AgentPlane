from __future__ import annotations

from pathlib import Path
from typing import Any

from agentplane.domain.app.lifecycle_contract import (
    ValidatedDeliveryContract,  # noqa: F401
    load_validated_delivery_contract,
)
from agentplane.domain.app.lifecycle_post_actions import (
    _catalog_entry_from_validated,
    _catalog_step_payload,
    _plan_service_removal_step,
    _plan_service_step,
    _planned_post_actions,
    _record_step,
    _service_entry_from_validated,
    _target_policy_summary,
    run_delivery_post_actions,
)
from agentplane.domain.app.lifecycle_resources import (
    _build_resource_registry_entry,
    _canonical_secret_files,  # noqa: F401
    _fallback_secret_apply,
    _fallback_secret_plan,
    _ingress_definitions,
    _ingress_sites,  # noqa: F401
    _load_resource_registry,
    _resource_registry_path,
    _secret_files_from_registry_entry,
    _write_resource_registry,
)
from agentplane.domain.app.lifecycle_steps import (  # noqa: F401
    plan_local_backend_step,
    plan_remote_bash_stdin_step,
    plan_remote_copy_step,
    plan_remote_shell_step,
)
from agentplane.domain.app.projection.runtime_env import service_env_file
from agentplane.domain.app.projection_lifecycle import default_offboarding_plan, default_onboarding_plan
from agentplane.domain.app.secrets_lifecycle import (
    apply_secret_allocation,
    apply_secret_retirement,
    plan_secret_retirement,
)
from agentplane.domain.app.truth_lifecycle import (
    offboard_catalog_entry,
    onboard_catalog_entry,
    plan_app_resource_registry_offboard,
    plan_app_resource_registry_onboard,
    scan_offboarding_orphans,
)
from agentplane.domain.ingress.lifecycle import (
    apply_ingress_truth_offboard,
    apply_ingress_truth_onboard,
    plan_ingress_truth_offboard,
    plan_ingress_truth_onboard,
)
from agentplane.domain.service.lifecycle import (
    apply_service_offboard,
    apply_service_onboard,
)


def onboard_delivery_for_app(
    repo_root: Path,
    *,
    target: str,
    app: str,
    dry_run: bool,
    write: bool,
    app_repo_root: str | None = None,
    repo_name: str | None = None,
    contract_path: str | None = None,
) -> dict[str, Any]:
    write_mode = bool(write) and not bool(dry_run)
    repo_root = repo_root.resolve()
    validated = load_validated_delivery_contract(
        repo_root,
        target=target,
        app=app,
        app_repo_root=app_repo_root,
        repo_name=repo_name,
        contract_path=contract_path,
    )
    contract = validated.contract
    service_key = str(contract.get("inventory", {}).get("service_key") or contract.get("app_id") or app)
    tenant_resources = contract.get("infra", {}).get("tenant_resources")
    tenant_resources = tenant_resources if isinstance(tenant_resources, dict) else {}

    sequence: list[dict[str, Any]] = [
        {
            "action": "app.delivery.validate-contract",
            "ok": True,
            "contract_file": str(validated.contract_file),
            "app_id": validated.app,
        }
    ]

    sequence.append(
        _record_step(
            "app.delivery.onboard.target-policy",
            write=False,
            ok=True,
            changed=False,
            payload=_target_policy_summary(repo_root, target=target),
        )
    )

    catalog_result = onboard_catalog_entry(
        repo_root,
        _catalog_entry_from_validated(validated, target=target),
        write=write_mode,
        allow_replace=True,
    )
    sequence.append(
        _record_step(
            "app.delivery.onboard.catalog",
            write=write_mode,
            ok=True,
            changed=catalog_result.changed,
            payload=_catalog_step_payload(catalog_result),
        )
    )

    registry_path = _resource_registry_path(repo_root, target)
    current_registry = _load_resource_registry(repo_root, target)
    next_registry, registry_evidence = plan_app_resource_registry_onboard(
        current_registry,
        app_id=validated.app,
        entry=_build_resource_registry_entry(validated, target=target),
        allow_replace=True,
    )
    registry_changed = next_registry != current_registry
    if write_mode and registry_changed:
        _write_resource_registry(registry_path, next_registry)
    sequence.append(
        _record_step(
            "app.delivery.onboard.app-resource-truth",
            write=write_mode,
            ok=True,
            changed=registry_changed,
            payload={"registry_file": str(registry_path), **registry_evidence},
        )
    )

    secret_files = _secret_files_from_registry_entry(
        next_registry.get(validated.app), target=target, app=validated.app, tenant_resources=tenant_resources
    )
    if write_mode:
        try:
            secret_payload = apply_secret_allocation(repo_root, target, validated.app, execute=True)
        except ValueError:
            secret_payload = {
                "operation": "allocate",
                "target": target,
                "app": validated.app,
                **_fallback_secret_apply(repo_root=repo_root, operation="allocate", secret_files=secret_files),
            }
    else:
        secret_payload = _fallback_secret_plan(
            repo_root=repo_root,
            target=target,
            app=validated.app,
            operation="allocate",
            secret_files=secret_files,
        )
    sequence.append(
        _record_step(
            "app.delivery.onboard.secrets",
            write=write_mode,
            ok=True,
            changed=bool(secret_payload.get("created_files") or registry_changed),
            payload=secret_payload,
        )
    )

    service_entry = _service_entry_from_validated(validated)
    if write_mode:
        service_result = apply_service_onboard(
            repo_root,
            target,
            service_key=service_key,
            entry=service_entry,
            allow_replace=True,
            write=True,
        )
        service_payload: dict[str, Any] = {
            "inventory_file": str(service_result.path),
            "service_key": service_result.service_key,
            "evidence": service_result.evidence,
            "entry": service_result.entry,
        }
        service_changed = service_result.changed
    else:
        service_payload = _plan_service_step(repo_root, target=target, service_key=service_key, entry=service_entry)
        service_changed = True
    sequence.append(
        _record_step(
            "app.delivery.onboard.service-truth",
            write=write_mode,
            ok=True,
            changed=service_changed,
            payload=service_payload,
        )
    )

    website_steps: list[dict[str, Any]] = []
    for definition in _ingress_definitions(validated):
        if write_mode:
            payload = apply_ingress_truth_onboard(repo_root, target, definition, execute=True)
            changed = payload["result"]["action"] in {"created", "updated"}
        else:
            payload = plan_ingress_truth_onboard(repo_root, target, definition)
            changed = bool(payload.get("steps"))
        website_steps.append(
            _record_step(
                "app.delivery.onboard.website-truth",
                write=write_mode,
                ok=True,
                changed=changed,
                payload=payload,
            )
        )
    sequence.extend(website_steps)

    sequence.append(
        _record_step(
            "app.delivery.onboard.projection-plan",
            write=write_mode,
            ok=True,
            changed=write_mode,
            payload=default_onboarding_plan(dry_run=not write_mode).summary(),
        )
    )

    post_actions = (
        run_delivery_post_actions(
            repo_root,
            target=target,
            app=validated.app,
            app_repo_root=app_repo_root,
            write=True,
            write_evidence=True,
            evidence_action="onboard",
            evidence_op_prefix="onboard-post-actions",
            deploy_operation=None,
        )
        if write_mode
        else _planned_post_actions(validated, target=target, write=False, intent="onboard")
    )
    sequence.extend(post_actions.get("steps", []))

    return {
        "ok": all(bool(step.get("ok", False)) for step in sequence),
        "target": target,
        "app": validated.app,
        "contract_file": str(validated.contract_file),
        "write": write_mode,
        "sequence": sequence,
        "post_actions": post_actions,
    }


def _remove_service_env(repo_root: Path, *, target: str, app_id: str, write: bool) -> dict[str, Any]:
    env_path = service_env_file(repo_root, target, app_id)
    exists = env_path.exists()
    ok = not env_path.is_dir()
    changed = exists and ok
    if write and changed:
        env_path.unlink()
    return {
        "env_file": str(env_path),
        "exists": exists,
        "removed": changed and write,
    }


def offboard_delivery_for_app(
    repo_root: Path,
    *,
    target: str,
    app: str,
    dry_run: bool,
    write: bool,
    extra_hooks: list[Any] | None = None,
) -> dict[str, Any]:
    write_mode = bool(write) and not bool(dry_run)
    repo_root = repo_root.resolve()
    validated = load_validated_delivery_contract(repo_root, target=target, app=app)
    contract = validated.contract
    service_key = str(contract.get("inventory", {}).get("service_key") or validated.app)

    steps: list[dict[str, Any]] = [
        {
            "action": "app.delivery.validate-contract",
            "ok": True,
            "contract_file": str(validated.contract_file),
            "app_id": validated.app,
        },
        _record_step(
            "app.delivery.offboard.target-policy",
            write=False,
            ok=True,
            changed=False,
            payload=_target_policy_summary(repo_root, target=target),
        ),
    ]

    for definition in _ingress_definitions(validated):
        if write_mode:
            payload = apply_ingress_truth_offboard(repo_root, target, definition.alias, execute=True)
            changed = payload["result"]["action"] == "removed"
        else:
            payload = plan_ingress_truth_offboard(repo_root, target, definition.alias)
            changed = bool(payload.get("steps"))
        steps.append(
            _record_step(
                "app.delivery.offboard.website-truth",
                write=write_mode,
                ok=True,
                changed=changed,
                payload=payload,
            )
        )

    if write_mode:
        try:
            service_result = apply_service_offboard(repo_root, target, service_key=service_key, write=True)
            service_payload = {
                "inventory_file": str(service_result.path),
                "service_key": service_result.service_key,
                "evidence": service_result.evidence,
                "entry": service_result.entry,
            }
            service_changed = service_result.changed
        except ValueError:
            service_payload = {"service_key": service_key, "present": False}
            service_changed = False
    else:
        service_payload = _plan_service_removal_step(repo_root, target=target, service_key=service_key)
        service_changed = bool(service_payload.get("present"))
    steps.append(
        _record_step(
            "app.delivery.offboard.service-truth",
            write=write_mode,
            ok=True,
            changed=service_changed,
            payload=service_payload,
        )
    )

    registry_path = _resource_registry_path(repo_root, target)
    current_registry = _load_resource_registry(repo_root, target)
    next_registry, registry_evidence = plan_app_resource_registry_offboard(current_registry, app_id=validated.app)
    registry_changed = next_registry != current_registry
    secret_files = _secret_files_from_registry_entry(
        current_registry.get(validated.app), target=target, app=validated.app
    )
    if write_mode and registry_changed:
        _write_resource_registry(registry_path, next_registry)
    steps.append(
        _record_step(
            "app.delivery.offboard.app-resource-truth",
            write=write_mode,
            ok=True,
            changed=registry_changed,
            payload={"registry_file": str(registry_path), **registry_evidence},
        )
    )

    if write_mode:
        try:
            secret_payload = apply_secret_retirement(repo_root, target, validated.app, execute=True)
        except ValueError:
            secret_payload = {
                "operation": "retire",
                "target": target,
                "app": validated.app,
                **_fallback_secret_apply(repo_root=repo_root, operation="retire", secret_files=secret_files),
            }
    else:
        try:
            secret_payload = plan_secret_retirement(repo_root, target, validated.app)
        except ValueError:
            secret_payload = _fallback_secret_plan(
                repo_root=repo_root,
                target=target,
                app=validated.app,
                operation="retire",
                secret_files=secret_files,
            )
    steps.append(
        _record_step(
            "app.delivery.offboard.secrets",
            write=write_mode,
            ok=True,
            changed=bool(secret_payload.get("removed_files") or secret_payload.get("files")),
            payload=secret_payload,
        )
    )

    catalog_result = offboard_catalog_entry(repo_root, app_id=validated.app, write=write_mode)
    steps.append(
        _record_step(
            "app.delivery.offboard.catalog",
            write=write_mode,
            ok=True,
            changed=catalog_result.changed,
            payload=_catalog_step_payload(catalog_result),
        )
    )

    steps.append(
        _record_step(
            "app.delivery.offboard.projection-plan",
            write=write_mode,
            ok=True,
            changed=write_mode,
            payload=default_offboarding_plan(dry_run=not write_mode).summary(),
        )
    )

    runtime_env_payload = _remove_service_env(repo_root, target=target, app_id=validated.app, write=write_mode)
    steps.append(
        _record_step(
            "app.delivery.offboard.runtime-env",
            write=write_mode,
            ok=True,
            changed=bool(runtime_env_payload.get("removed")),
            payload=runtime_env_payload,
        )
    )

    hooks: dict[str, Any] = {"lane3_orphans": scan_offboarding_orphans(repo_root, app_id=validated.app)}
    if extra_hooks:
        for index, hook in enumerate(extra_hooks, start=1):
            hooks[f"extra_{index}"] = hook(validated, write_mode)

    doc_sync_payload: dict[str, Any]
    if write_mode:
        doc_sync_payload = validated.app_cli.doc_sync(repo_root=repo_root, target=target, contract_paths=[], write=True)
    else:
        doc_sync_payload = {
            "planned": True,
            "server_readme": str(Path("inventory") / "servers" / target / "README.md"),
            "app_docs": [],
        }
    steps.append(
        _record_step(
            "app.delivery.offboard.doc-sync",
            write=write_mode,
            ok=True,
            changed=True,
            payload=doc_sync_payload,
        )
    )

    return {
        "ok": all(bool(step.get("ok", False)) for step in steps),
        "target": target,
        "app": validated.app,
        "app_id": validated.app,
        "write": write_mode,
        "steps": steps,
        "hooks": hooks,
        "doc_sync": doc_sync_payload,
    }
