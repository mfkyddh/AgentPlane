from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentplane.domain.app import runtime as app_runtime
from agentplane.domain.app.artifacts import resolve_delivery_contract_spec
from agentplane.domain.app.contracts import validate_contract
from agentplane.domain.app.catalog import resolve_app_contract, resolve_app_entry
from agentplane.domain.app.models import AppCatalogEntry, DeliveryContractSpec
from agentplane.domain.app.projection.runtime_env import (
    apply_runtime_env_projection,
    plan_runtime_env_projection,
    service_env_file,
)
from agentplane.domain.app.projection_lifecycle import default_offboarding_plan, default_onboarding_plan
from agentplane.domain.app.resource_paths import (
    app_resource_secret_dir,
    app_resource_secret_relative,
    resolve_secret_file_path,
)
from agentplane.domain.app.secrets_lifecycle import (
    apply_secret_allocation,
    apply_secret_retirement,
    plan_secret_retirement,
)
from agentplane.domain.app.truth_lifecycle import (
    CatalogMutationResult,
    load_json_file,
    make_app_resource_registry_entry,
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
from agentplane.domain.ingress.models import IngressDefinition
from agentplane.domain.service.lifecycle import (
    apply_service_offboard,
    apply_service_onboard,
    plan_service_registry_offboard,
    plan_service_registry_onboard,
)
from agentplane.runtime.execution import CommandSpec, CommandStep, shell_join
from agentplane.ssh import SshTarget


@dataclass(frozen=True)
class ValidatedDeliveryContract:
    app_cli: Any
    contract: dict[str, Any]
    delivery_contract: DeliveryContractSpec
    contract_file: Path
    app: str
    repo_name: str
    app_root: Path
    contract_relpath: str
    catalog_entry: AppCatalogEntry | None


def plan_local_backend_step(
    key: str,
    *,
    backend_type: str,
    cwd: Path | str,
    argv: tuple[str, ...],
    env: dict[str, str] | None = None,
    stdin_text: str | None = None,
    capabilities: tuple[str, ...] = (),
    expected_outputs: tuple[str, ...] = (),
    timeout: int = 300,
    display_command: str | None = None,
) -> CommandStep:
    return CommandStep(
        key=key,
        spec=CommandSpec(
            backend_type=backend_type,  # type: ignore[arg-type]
            argv=argv,
            cwd=cwd,
            env=env or {},
            stdin_text=stdin_text,
            expected_outputs=expected_outputs,
            capabilities=capabilities,
            timeout=timeout,
            metadata={"display_override": display_command or shell_join(argv)},
        ),
    )


def plan_remote_shell_step(
    key: str,
    *,
    ssh_target: SshTarget,
    cwd: str | None,
    argv: tuple[str, ...],
    shell_command: str | None = None,
    env: dict[str, str] | None = None,
    capabilities: tuple[str, ...] = (),
    expected_outputs: tuple[str, ...] = (),
    timeout: int = 300,
) -> CommandStep:
    metadata: dict[str, Any] = {"transport": "shell", "ssh_target": ssh_target}
    if shell_command is not None:
        metadata["shell_command"] = shell_command
    return CommandStep(
        key=key,
        spec=CommandSpec(
            backend_type="ssh-linux",
            argv=argv,
            cwd=cwd,
            env=env or {},
            expected_outputs=expected_outputs,
            capabilities=capabilities,
            timeout=timeout,
            metadata=metadata,
        ),
    )


def plan_remote_bash_stdin_step(
    key: str,
    *,
    ssh_target: SshTarget,
    argv: tuple[str, ...],
    stdin_text: str,
    capabilities: tuple[str, ...] = (),
    expected_outputs: tuple[str, ...] = (),
    timeout: int = 300,
) -> CommandStep:
    return CommandStep(
        key=key,
        spec=CommandSpec(
            backend_type="ssh-linux",
            argv=argv,
            stdin_text=stdin_text,
            expected_outputs=expected_outputs,
            capabilities=capabilities,
            timeout=timeout,
            metadata={"transport": "bash-stdin", "ssh_target": ssh_target},
        ),
    )


def plan_remote_copy_step(
    key: str,
    *,
    ssh_target: SshTarget,
    local_path: Path,
    remote_path: str,
    expected_outputs: tuple[str, ...] = (),
    timeout: int = 300,
) -> CommandStep:
    return CommandStep(
        key=key,
        spec=CommandSpec(
            backend_type="ssh-linux",
            argv=("scp", str(local_path), remote_path),
            expected_outputs=expected_outputs,
            capabilities=("scp",),
            timeout=timeout,
            metadata={
                "transport": "copy-to-remote",
                "ssh_target": ssh_target,
                "local_path": local_path,
                "remote_path": remote_path,
            },
        ),
    )


def _resolve_contract_source(
    repo_root: Path,
    *,
    target: str,
    app: str,
    app_repo_root: str | None = None,
    repo_name: str | None = None,
    contract_path: str | None = None,
) -> tuple[AppCatalogEntry | None, str, Path, Path]:
    if app_repo_root:
        resolved_app_root = Path(app_repo_root).expanduser().resolve()
        resolved_repo_name = repo_name or resolved_app_root.name
        resolved_contract = (
            (resolved_app_root / contract_path).resolve()
            if contract_path and not Path(contract_path).is_absolute()
            else Path(contract_path).resolve()
            if contract_path
            else (resolved_app_root / "deploy" / "agentplane" / "contract.yaml").resolve()
        )
        if not resolved_contract.is_file():
            raise ValueError(f"missing onboarding contract file: {resolved_contract}")
        try:
            existing_entry = resolve_app_entry(repo_root, app=app)
        except ValueError:
            existing_entry = None
        try:
            contract_relpath = str(resolved_contract.relative_to(resolved_app_root))
        except ValueError as exc:
            raise ValueError("contract file must stay inside app repo root") from exc
        return existing_entry, resolved_repo_name, resolved_app_root, resolved_contract

    entry, contract_file = resolve_app_contract(repo_root, target=target, app=app)
    contract_relpath = entry.contracts.get(target)
    if not isinstance(contract_relpath, str) or not contract_relpath:
        raise ValueError(f"app catalog missing target mapping: target={target} app={app}")
    return entry, entry.repo_name, entry.repo_root.resolve(), contract_file


def load_validated_delivery_contract(
    repo_root: Path,
    *,
    target: str,
    app: str,
    app_repo_root: str | None = None,
    repo_name: str | None = None,
    contract_path: str | None = None,
) -> ValidatedDeliveryContract:
    catalog_entry, resolved_repo_name, resolved_app_root, resolved_contract = _resolve_contract_source(
        repo_root,
        target=target,
        app=app,
        app_repo_root=app_repo_root,
        repo_name=repo_name,
        contract_path=contract_path,
    )
    contract = validate_contract(resolved_contract, repo_root=repo_root, target=target)
    contract_app = str(contract.get("app_id") or "")
    if contract_app != app:
        raise ValueError(f"contract app_id mismatch: expected {app!r}, got {contract_app!r}")
    try:
        contract_relpath = str(resolved_contract.relative_to(resolved_app_root))
    except ValueError as exc:
        raise ValueError("contract file must stay inside app repo root") from exc
    return ValidatedDeliveryContract(
        app_cli=app_runtime,
        contract=contract,
        delivery_contract=resolve_delivery_contract_spec(contract),
        contract_file=resolved_contract,
        app=app,
        repo_name=resolved_repo_name,
        app_root=resolved_app_root,
        contract_relpath=contract_relpath,
        catalog_entry=catalog_entry,
    )


def _record_step(action: str, *, write: bool, ok: bool, changed: bool, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "action": action,
        "write": write,
        "ok": ok,
        "changed": changed,
        "payload": payload,
    }


def _catalog_entry_from_validated(validated: ValidatedDeliveryContract, *, target: str) -> AppCatalogEntry:
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


def _canonical_secret_files(*, target: str, app: str, tenant_resources: dict[str, Any]) -> list[str]:
    secret_files: list[str] = []
    for kind in sorted(tenant_resources):
        secret_files.append(app_resource_secret_relative(target, app, kind))
    return secret_files


def _resource_registry_path(repo_root: Path, target: str) -> Path:
    return repo_root / "inventory" / "servers" / target / "app-resources.json"


def _load_resource_registry(repo_root: Path, target: str) -> dict[str, Any]:
    return load_json_file(_resource_registry_path(repo_root, target))


def _write_resource_registry(path: Path, registry: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _build_resource_registry_entry(validated: ValidatedDeliveryContract, *, target: str) -> dict[str, Any]:
    tenant_resources = validated.contract.get("infra", {}).get("tenant_resources")
    resolved_resources = tenant_resources if isinstance(tenant_resources, dict) else {}
    return make_app_resource_registry_entry(
        app_id=validated.app,
        resources={kind: value for kind, value in resolved_resources.items() if isinstance(value, dict)},
        secret_files=_canonical_secret_files(target=target, app=validated.app, tenant_resources=resolved_resources),
        ledger_status={"local_secret_presence": "planned"},
    )


def _secret_files_from_registry_entry(
    registry_entry: dict[str, Any] | None,
    *,
    target: str,
    app: str,
    tenant_resources: dict[str, Any] | None = None,
) -> list[str]:
    if isinstance(registry_entry, dict):
        secret_files = registry_entry.get("secret_files")
        if isinstance(secret_files, list):
            resolved = [item for item in secret_files if isinstance(item, str) and item]
            if resolved:
                return resolved
    return _canonical_secret_files(target=target, app=app, tenant_resources=tenant_resources or {})


def _fallback_secret_plan(
    *,
    repo_root: Path,
    target: str,
    app: str,
    operation: str,
    secret_files: list[str],
) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    missing: list[str] = []
    for relative_path in secret_files:
        resolved = resolve_secret_file_path(repo_root, relative_path)
        exists = resolved.is_file()
        files.append({"relative": relative_path, "path": str(resolved), "exists": exists})
        if not exists:
            missing.append(relative_path)
    return {
        "operation": operation,
        "target": target,
        "app": app,
        "planned": True,
        "guarded": operation == "retire",
        "files": files,
        "missing_files": missing,
        "secret_root": str(app_resource_secret_dir(repo_root, target, app)),
    }


def _fallback_secret_apply(
    *,
    repo_root: Path,
    operation: str,
    secret_files: list[str],
) -> dict[str, Any]:
    changed_files: list[str] = []
    for relative_path in secret_files:
        resolved = resolve_secret_file_path(repo_root, relative_path)
        if operation == "allocate":
            if not resolved.is_file():
                resolved.parent.mkdir(parents=True, exist_ok=True)
                resolved.write_text("", encoding="utf-8")
                resolved.chmod(0o600)
                changed_files.append(str(resolved))
        else:
            if resolved.is_file():
                resolved.unlink()
                changed_files.append(str(resolved))
    key = "created_files" if operation == "allocate" else "removed_files"
    return {key: changed_files, "fallback": True}


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


def _ingress_sites(contract: dict[str, Any]) -> list[dict[str, Any]]:
    top_level = contract.get("public_sites")
    if isinstance(top_level, list):
        return [site for site in top_level if isinstance(site, dict)]
    ingress_sites = contract.get("ingress", {}).get("public_sites")
    if isinstance(ingress_sites, list):
        return [site for site in ingress_sites if isinstance(site, dict)]
    return []


def _ingress_definitions(validated: ValidatedDeliveryContract) -> list[IngressDefinition]:
    runtime = validated.contract.get("runtime", {})
    proxy = f"http://{runtime.get('host_binding', '127.0.0.1:80')}"
    definitions: list[IngressDefinition] = []
    for site in _ingress_sites(validated.contract):
        alias = str(site.get("website_object") or site.get("alias") or validated.app)
        primary_domain = str(site.get("domain") or site.get("primary_domain") or alias)
        public_url = str(site.get("public_url") or "")
        definitions.append(
            IngressDefinition(
                alias=alias,
                primary_domain=primary_domain,
                public_url=public_url,
                proxy=proxy,
                status=str(site.get("status") or ""),
                config_file=str(site.get("config_file") or ""),
                control_plane=str(site.get("control_plane") or "onepanel"),
            )
        )
    return definitions


def _target_policy_summary(repo_root: Path, *, target: str) -> dict[str, Any]:
    if target == "wsl":
        from agentplane.domain.app.lifecycle_wsl import lane2_policy_helper as wsl_policy_helper

        return wsl_policy_helper()
    if target == "prod0-main":
        from agentplane.domain.app.lifecycle_prod0_main import lane2_policy_helper as prod0_policy_helper

        return prod0_policy_helper()
    return {"target": target}


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
