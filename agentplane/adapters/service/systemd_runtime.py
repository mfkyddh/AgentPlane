from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any

from agentplane.adapters.service.common import run_shell_command, shell_command_spec
from agentplane.domain.service.models import ServiceDefinition


def _unit_name(definition: ServiceDefinition) -> str:
    unit_name = definition.metadata.get("unit_name")
    if isinstance(unit_name, str) and unit_name:
        return unit_name
    raise ValueError(f"{definition.name} 缺少 systemd unit_name")


def verify_systemd_service(repo_root: Path, target: str, definition: ServiceDefinition, declared: dict[str, Any] | None = None) -> dict[str, Any]:
    unit_name = _unit_name(definition)
    active = run_shell_command(repo_root, target, f"systemctl is-active {shlex.quote(unit_name)}")
    enabled = run_shell_command(repo_root, target, f"systemctl is-enabled {shlex.quote(unit_name)}")
    checks: dict[str, dict[str, object]] = {
        "active": {"ok": active["ok"] and str(active["stdout"]).strip() == "active", "actual": str(active["stdout"]).strip()},
        "enabled": {"ok": enabled["ok"] and str(enabled["stdout"]).strip() in {"enabled", "static"}, "actual": str(enabled["stdout"]).strip()},
    }

    listen_port = definition.metadata.get("listen_port")
    if isinstance(listen_port, int):
        socket_probe = run_shell_command(repo_root, target, f"ss -ltnp | grep {listen_port}")
        checks["listen"] = {"ok": socket_probe["ok"], "actual": str(socket_probe["stdout"]).strip()}
        evidence = [active, enabled, socket_probe]
    else:
        evidence = [active, enabled]

    failures = [name for name, item in checks.items() if not bool(item.get("ok"))]
    return {"ok": not failures, "checks": checks, "evidence": evidence, "failures": failures}


def plan_systemd_operation(repo_root: Path, target: str, definition: ServiceDefinition, operation: str) -> list[dict[str, object]]:
    unit_name = _unit_name(definition)
    if operation not in {"restart", "reload"}:
        raise ValueError(f"unsupported operation for {definition.name}: {operation}")
    command = f"systemctl {operation} {shlex.quote(unit_name)}"
    spec = shell_command_spec(repo_root, target, command)
    return [{"argv": spec.argv, "display": spec.display}]

