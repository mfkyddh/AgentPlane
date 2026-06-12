from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from agentplane.cli.audit import audit_filesystem
from agentplane.cli.cleanup import apply_cleanup_plan, build_cleanup_plan
from agentplane.cli.infra_automation import (
    apply_infra_automation,
    get_infra_automation,
    plan_infra_automation,
    search_infra_automations,
    verify_infra_automation,
)
from agentplane.cli.inventory import generate_inventory_snapshot
from agentplane.cli.networks import (
    apply_firewall_operation,
    audit_firewall_rules,
    audit_managed_bridge_networks,
    ensure_managed_bridge_networks,
    plan_firewall_operation,
)
from agentplane.cli.preflight import execute_remote_preflight
from agentplane.cli.remote import execute_remote_bash
from agentplane.cli.secrets import init_data_services, materialize_legacy_host_layout
from agentplane.domain.infra.handlers import init_secrets, run_doctor, run_inspect_local, run_verify_secrets
from agentplane.domain.infra.health import check_infra_health
from agentplane.domain.infra.live_gate import plan_live_gate, run_live_gate
from agentplane.domain.infra.local import handle_local_infra_command
from agentplane.runtime.wsl_bridge import normalize_repo_root_for_current_host


def _wrap(*, action: str, target: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "command": "infra",
        "action": action,
        "target": target,
        "payload": payload,
    }


def _without_public_envelope(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in payload.items()
        if key not in {"command", "action", "target", "env", "repo_root", "inventory_file"}
    }


def _normalize_repo_root(path: Path | str) -> Path:
    return normalize_repo_root_for_current_host(path)


def _handle_bootstrap(args: argparse.Namespace, repo_root: Path) -> dict[str, Any]:
    action = args.infra_bootstrap_action
    if action == "inspect-local":
        return _wrap(action="bootstrap.inspect-local", target="local", payload=run_inspect_local(repo_root))
    if action == "init-secrets":
        return _wrap(action="bootstrap.init-secrets", target="local", payload=init_secrets(repo_root))
    if action == "verify-secrets":
        return _wrap(action="bootstrap.verify-secrets", target="local", payload=run_verify_secrets(repo_root))
    if action == "doctor":
        return _wrap(action="bootstrap.doctor", target="local", payload=run_doctor(repo_root))
    raise ValueError(f"Unsupported bootstrap action: {action}")


def handle_infra_command(args: argparse.Namespace) -> dict[str, Any]:
    if args.infra_action == "local":
        action, payload = handle_local_infra_command(args)
        return _wrap(action=action, target="local", payload=payload)

    repo_root = _normalize_repo_root(getattr(args, "repo_root", "."))

    if args.infra_action == "inventory":
        result = generate_inventory_snapshot(repo_root, args.target, write=bool(args.write))
        return _wrap(
            action="inventory",
            target=args.target,
            payload={
                "snapshot": result["payload"],
                "inventory_file": result["inventory_file"],
                "backend_type": result.get("backend_type"),
            },
        )

    if args.infra_action == "audit":
        result = audit_filesystem(repo_root, args.target)
        if args.write:
            from agentplane.cli.operations import append_operation_ledger, next_operation_id

            append_operation_ledger(
                repo_root,
                command="infra",
                action="audit",
                target=args.target,
                op_id=next_operation_id("audit"),
                dry_run=False,
                result="pass" if result["ok"] else "fail",
                details={
                    "violations_count": len(result["violations"]),
                    "path_check_mode": result.get("path_check_mode"),
                },
            )
        return _wrap(
            action="audit",
            target=args.target,
            payload={
                "ok": result["ok"],
                "violations": result["violations"],
                "path_check_mode": result.get("path_check_mode"),
            },
        )

    if args.infra_action == "live-gate" and args.infra_live_gate_action == "plan":
        return _wrap(
            action="live-gate.plan",
            target=args.profile,
            payload=plan_live_gate(
                repo_root,
                profile=args.profile,
                app=args.app,
                projection_profile=args.projection_profile,
            ),
        )

    if args.infra_action == "live-gate" and args.infra_live_gate_action == "run":
        return _wrap(
            action="live-gate.run",
            target=args.profile,
            payload=run_live_gate(
                repo_root,
                profile=args.profile,
                app=args.app,
                projection_profile=args.projection_profile,
                execute=bool(args.execute),
            ),
        )

    if args.infra_action == "cleanup" and args.infra_cleanup_action == "plan":
        result = build_cleanup_plan(repo_root, args.target)
        return _wrap(
            action="cleanup.plan",
            target=args.target,
            payload=_without_public_envelope(result),
        )

    if args.infra_action == "cleanup" and args.infra_cleanup_action == "apply":
        result = apply_cleanup_plan(repo_root, args.target)
        return _wrap(
            action="cleanup.apply",
            target=args.target,
            payload=_without_public_envelope(result),
        )

    if args.infra_action == "automation" and args.infra_automation_action == "search":
        return _wrap(
            action="automation.search",
            target=args.target,
            payload=search_infra_automations(repo_root, args.target),
        )

    if args.infra_action == "automation" and args.infra_automation_action == "get":
        return _wrap(
            action="automation.get",
            target=args.target,
            payload=get_infra_automation(repo_root, args.target, args.name),
        )

    if args.infra_action == "automation" and args.infra_automation_action == "verify":
        return _wrap(
            action="automation.verify",
            target=args.target,
            payload=verify_infra_automation(
                repo_root, args.target, args.name, env_file=getattr(args, "env_file", None)
            ),
        )

    if args.infra_action == "automation" and args.infra_automation_action == "plan":
        return _wrap(
            action="automation.plan",
            target=args.target,
            payload=plan_infra_automation(
                repo_root,
                args.target,
                args.name,
                args.operation,
                env_file=getattr(args, "env_file", None),
            ),
        )

    if args.infra_action == "automation" and args.infra_automation_action == "apply":
        return _wrap(
            action="automation.apply",
            target=args.target,
            payload=apply_infra_automation(
                repo_root,
                args.target,
                args.name,
                args.operation,
                execute=bool(args.execute),
                env_file=getattr(args, "env_file", None),
            ),
        )

    if args.infra_action == "health":
        return _wrap(
            action="health",
            target=args.target,
            payload=check_infra_health(args.target),
        )

    if args.infra_action == "network" and args.infra_network_action == "audit":
        return {
            "command": "infra",
            "action": "network.audit",
            "target": args.target,
            "payload": audit_managed_bridge_networks(repo_root, args.target),
        }

    if args.infra_action == "network" and args.infra_network_action == "ensure":
        return {
            "command": "infra",
            "action": "network.ensure",
            "target": args.target,
            "payload": ensure_managed_bridge_networks(repo_root, args.target),
        }

    if args.infra_action == "network" and args.infra_network_action == "firewall-audit":
        return {
            "command": "infra",
            "action": "network.firewall-audit",
            "target": args.target,
            "payload": audit_firewall_rules(
                repo_root, args.target, env_file=getattr(args, "env_file", None)
            ),
        }

    if args.infra_action == "network" and args.infra_network_action == "firewall" and args.infra_firewall_action == "plan":
        return _wrap(
            action="network.firewall.plan",
            target=args.target,
            payload=plan_firewall_operation(
                repo_root,
                args.target,
                args.operation,
                env_file=getattr(args, "env_file", None),
                with_docker_restart=bool(getattr(args, "with_docker_restart", False)),
            ),
        )

    if args.infra_action == "network" and args.infra_network_action == "firewall" and args.infra_firewall_action == "apply":
        result = apply_firewall_operation(
            repo_root,
            args.target,
            args.operation,
            execute=bool(args.execute),
            env_file=getattr(args, "env_file", None),
            with_docker_restart=bool(getattr(args, "with_docker_restart", False)),
        )
        op_id = next_operation_id("firewall")
        append_operation_ledger(
            repo_root,
            command="infra",
            action="network.firewall.apply",
            target=args.target,
            op_id=op_id,
            dry_run=not bool(args.execute),
            result="executed" if result.get("ok") else "failed",
            details={"operation": args.operation},
        )
        return _wrap(action="network.firewall.apply", target=args.target, payload=result)

    if args.infra_action == "remote" and args.infra_remote_action == "preflight":
        report = execute_remote_preflight(repo_root, args.target)
        return _wrap(
            action="remote.preflight",
            target=args.target,
            payload=report.to_payload(),
        )

    if args.infra_action == "remote" and args.infra_remote_action == "bash":
        result = execute_remote_bash(
            repo_root=repo_root,
            target=args.target,
            remote_args=list(args.remote_args),
            script_file=args.script_file,
            dry_run=bool(args.dry_run),
            intent=args.intent,
            stream=bool(args.stream),
        )
        return _wrap(
            action="remote.bash",
            target=args.target,
            payload=_without_public_envelope(result),
        )

    if args.infra_action == "secrets" and args.infra_secrets_action == "init-data-services":
        result = init_data_services(repo_root, args.target, force=bool(args.force))
        return _wrap(
            action="secrets.init-data-services",
            target=args.target,
            payload=_without_public_envelope(result),
        )

    if args.infra_action == "secrets" and args.infra_secrets_action == "sync-layout":
        result = materialize_legacy_host_layout(repo_root, args.target, write=bool(args.write))
        return _wrap(
            action="secrets.sync-layout",
            target=args.target,
            payload=_without_public_envelope(result),
        )

    if args.infra_action == "bootstrap":
        return _handle_bootstrap(args, repo_root)

    raise ValueError(f"Unsupported infra action: {args.infra_action}")
