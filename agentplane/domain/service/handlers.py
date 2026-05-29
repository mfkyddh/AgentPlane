from __future__ import annotations

from pathlib import Path
from typing import Any

from agentplane.adapters.service.common import run_command_argv
from agentplane.adapters.service.docker_runtime import plan_container_operation, verify_container_service
from agentplane.adapters.service.systemd_runtime import plan_systemd_operation, verify_systemd_service
from agentplane.domain.service.materialize import materialize_service_artifact
from agentplane.domain.service.models import ServiceDefinition
from agentplane.domain.service.registry import available_services, resolve_service
from agentplane.providers import get_provider
from agentplane.runtime.observation import build_verification_payload
from agentplane.runtime.path_policy import assert_canonical_ref


def _projection_handoff(
    definition: ServiceDefinition,
    declared: dict[str, Any] | None,
    *,
    target: str,
    trigger: str,
) -> dict[str, Any]:
    projection_app = ""
    if isinstance(declared, dict):
        raw_app = declared.get("app_id")
        if isinstance(raw_app, str):
            projection_app = raw_app.strip()
    if not projection_app:
        meta_app = definition.metadata.get("projection_app")
        if isinstance(meta_app, str):
            projection_app = meta_app.strip()

    required = trigger == "reconcile" and definition.control_plane in {"compose", "onepanel-compose"}
    steps: list[dict[str, Any]] = [
        {
            "command": "projection",
            "action": "ledger.refresh",
            "args": {"target": target, "write": required},
            "reason": "service inventory reconciliation follow-through",
        }
    ]
    if projection_app:
        steps.append(
            {
                "command": "projection",
                "action": "runtime-env.verify",
                "args": {"target": target, "app": projection_app},
                "reason": "runtime env projection drift check",
            }
        )
    return {"required": required, "trigger": trigger, "steps": steps}


def _service_summary(definition: ServiceDefinition, declared: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "name": definition.name,
        "kind": definition.runtime_kind,
        "control_plane": definition.control_plane,
        "supported_operations": list(definition.supported_operations),
        "declared": declared or {},
    }


def _service_canonical_ref(target: str, name: str) -> str:
    return assert_canonical_ref(f"targets/{target}/services/{name}")


def _service_ledger_fields(
    definition: ServiceDefinition, declared: dict[str, Any] | None, *, target: str
) -> dict[str, Any]:
    return {
        "target": target,
        **_service_summary(definition, declared),
    }


def search_services(repo_root: Path, target: str) -> dict[str, Any]:
    items = [_service_summary(definition, declared) for definition, declared in available_services(repo_root, target)]
    return {"items": items}


def get_service(repo_root: Path, target: str, name: str) -> dict[str, Any]:
    definition, declared = resolve_service(repo_root, target, name)
    if definition.runtime_kind == "docker":
        live = verify_container_service(repo_root, target, definition, declared)
    else:
        live = verify_systemd_service(repo_root, target, definition, declared)
    canonical_ref = _service_canonical_ref(target, definition.name)
    service_summary = _service_summary(definition, declared)
    return {
        "canonical_ref": canonical_ref,
        "ledger_fields": {
            "canonical_ref": canonical_ref,
            **_service_ledger_fields(definition, declared, target=target),
        },
        "verification_fields": {"live": live},
        "service": service_summary,
        "live": live,
    }


def verify_service(repo_root: Path, target: str, name: str) -> dict[str, Any]:
    definition, declared = resolve_service(repo_root, target, name)
    if definition.runtime_kind == "docker":
        payload = verify_container_service(repo_root, target, definition, declared)
    else:
        payload = verify_systemd_service(repo_root, target, definition, declared)
    canonical_ref = _service_canonical_ref(target, definition.name)
    live_payload = {
        "ok": payload.get("ok", False),
        "checks": payload.get("checks", {}),
        "evidence": payload.get("evidence", []),
        "failures": payload.get("failures", []),
    }
    wrapped = build_verification_payload(
        canonical_ref=canonical_ref,
        ledger_fields=_service_ledger_fields(definition, declared, target=target),
        verification_fields={"live": live_payload},
        evidence={"live": live_payload},
        checks=payload.get("checks", {}),
        failures=tuple(str(item) for item in payload.get("failures", [])),
        ok=bool(payload.get("ok")),
    )
    wrapped["service"] = _service_summary(definition, declared)
    wrapped["evidence"] = payload.get("evidence", [])
    wrapped["projection_handoff"] = _projection_handoff(definition, declared, target=target, trigger="verify")
    return wrapped


def _plan_steps(
    repo_root: Path, target: str, definition: ServiceDefinition, declared: dict[str, Any] | None, operation: str
) -> list[dict[str, object]]:
    if operation not in definition.supported_operations:
        raise ValueError(f"unsupported operation for {definition.name}: {operation}")
    if definition.runtime_kind == "docker":
        return plan_container_operation(repo_root, target, definition, declared, operation)
    return plan_systemd_operation(repo_root, target, definition, operation)


def plan_service_operation(repo_root: Path, target: str, name: str, operation: str) -> dict[str, Any]:
    definition, declared = resolve_service(repo_root, target, name)
    steps = _plan_steps(repo_root, target, definition, declared, operation)
    canonical_ref = _service_canonical_ref(target, definition.name)
    return {
        "canonical_ref": canonical_ref,
        "ledger_fields": {
            "canonical_ref": canonical_ref,
            **_service_ledger_fields(definition, declared, target=target),
        },
        "service": _service_summary(definition, declared),
        "operation": operation,
        "preflight": {"target": target, "service": name},
        "steps": steps,
        "verify_after_apply": {"service": name, "action": "verify"},
        "projection_handoff": _projection_handoff(definition, declared, target=target, trigger=operation),
    }


def apply_service_operation(
    repo_root: Path, target: str, name: str, operation: str, *, execute: bool
) -> dict[str, Any]:
    if not execute:
        raise ValueError("service apply requires --execute")

    definition, declared = resolve_service(repo_root, target, name)
    steps = _plan_steps(repo_root, target, definition, declared, operation)
    results: list[dict[str, object]] = []
    ok = True
    for step in steps:
        result = run_command_argv(list(step["argv"]), str(step["display"]))
        results.append(result)
        if not result["ok"]:
            ok = False
            break

    verified = verify_service(repo_root, target, name) if ok else {"ok": False, "failures": ["apply_failed"]}
    handoff = _projection_handoff(definition, declared, target=target, trigger=operation)
    canonical_ref = _service_canonical_ref(target, definition.name)
    return {
        "ok": ok and bool(verified.get("ok")),
        "canonical_ref": canonical_ref,
        "ledger_fields": {
            "canonical_ref": canonical_ref,
            **_service_ledger_fields(definition, declared, target=target),
        },
        "verification_fields": {"results": results, "verified": verified},
        "observation": verified.get("observation"),
        "service": _service_summary(definition, declared),
        "operation": operation,
        "results": results,
        "verified": verified,
        "projection_handoff": handoff,
    }


def refresh_service_ledger(repo_root: Path, target: str, *, write: bool = False) -> dict[str, Any]:
    result = get_provider().refresh_ledgers(Path(repo_root).resolve(), target, write=write)
    service_ledger = result.get("ledgers", {}).get("containers")
    return {
        "ok": True,
        "service_ledger": service_ledger,
        "all_counts": result.get("counts", {}),
        "write": write,
    }


def materialize_service(
    repo_root: Path,
    target: str,
    name: str,
    artifact: str,
    *,
    source: Path,
    merge_template: Path | None,
    output: Path,
    password: str,
    node_name: str = "",
    server: str = "",
    port: int | None = None,
    sni: str = "",
) -> dict[str, Any]:
    definition, declared = resolve_service(repo_root, target, name)
    payload = materialize_service_artifact(
        definition,
        declared,
        artifact=artifact,
        source=source,
        merge_template=merge_template,
        output=output,
        password=password,
        node_name=node_name,
        server=server,
        port=port,
        sni=sni,
    )
    payload["service"] = _service_summary(definition, declared)
    return payload
