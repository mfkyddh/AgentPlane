"""Shared infrastructure for delivery handlers — contract resolution and step execution engine."""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any

from agentplane.domain.app import runtime as app_runtime
from agentplane.domain.app.catalog import resolve_app_contract_source
from agentplane.domain.app.lifecycle import plan_local_backend_step, plan_remote_shell_step
from agentplane.runtime.backends import build_backend_runner
from agentplane.runtime.execution import CommandStep, shell_join
from agentplane.runtime.host_profile import detect_host_profile
from agentplane.runtime.redaction import redact_execution_payload


def _resolve_contract_file(
    repo_root: Path,
    *,
    target: str,
    app: str,
    app_repo_root: str | None,
) -> Path:
    _, contract_file = resolve_app_contract_source(repo_root, target=target, app=app, app_repo_root=app_repo_root)
    return contract_file


def _load_validated_contract(
    repo_root: Path,
    *,
    target: str,
    app: str,
    app_repo_root: str | None = None,
) -> tuple[Any, dict[str, Any], Path]:
    contract_file = _resolve_contract_file(repo_root, target=target, app=app, app_repo_root=app_repo_root)
    contract = app_runtime.validate_contract(contract_file, repo_root=repo_root, target=target)
    return app_runtime, contract, contract_file


def _check_delivery_preconditions(
    repo_root: Path,
    *,
    target: str,
    app: str,
    app_repo_root: str | None = None,
) -> dict[str, Any]:
    """在 deploy 等写操作前检查 app object 与 app resource 是否就绪。"""
    from agentplane.domain.app.object_handlers import verify_app_object
    from agentplane.domain.app.resource_handlers import verify_app_resource

    object_result = verify_app_object(repo_root, target, app, app_repo_root=app_repo_root)
    resource_result = verify_app_resource(repo_root, target, app)

    preconditions = {
        "app_object": {"ok": bool(object_result.get("ok")), "checks": object_result.get("checks", {})},
        "app_resource": {"ok": bool(resource_result.get("ok")), "checks": resource_result.get("checks", {})},
    }
    ok = all(v["ok"] for v in preconditions.values())
    return {"ok": ok, "preconditions": preconditions}


def _render_execution_steps(steps: list[CommandStep], *, _runner=None) -> list[dict[str, Any]]:
    runner = _runner or build_backend_runner()
    rendered_steps: list[dict[str, Any]] = []
    for step in steps:
        display_override = step.spec.metadata.get("display_override")
        try:
            rendered = runner.render_spec(step.spec)
            backend_payload = rendered.to_payload()
        except ValueError as exc:
            if step.spec.backend_type != "windows-wsl":
                raise
            backend_payload = {
                "backend_type": step.spec.backend_type,
                "argv": list(step.spec.argv),
                "display_command": display_override
                if isinstance(display_override, str) and display_override
                else shell_join(step.spec.argv),
                "cwd": None,
                "env": {},
                "expects_stdin": step.spec.stdin_text is not None,
                "expected_outputs": list(step.spec.expected_outputs),
                "capabilities": list(step.spec.capabilities),
                "blocked": True,
                "reason": str(exc),
            }
        if isinstance(display_override, str) and display_override:
            backend_payload["display_command"] = display_override
        rendered_steps.append(
            {
                "key": step.key,
                "plan": step.spec.to_payload(),
                "backend": backend_payload,
            }
        )
    return rendered_steps


def _execute_steps(steps: list[CommandStep], *, stop_on_failure: bool, _runner=None) -> list[dict[str, Any]]:
    runner = _runner or build_backend_runner()
    results: list[dict[str, Any]] = []
    for step in steps:
        result = runner.execute_spec(step.spec)
        results.append({"key": step.key, **redact_execution_payload(result.to_payload())})
        if stop_on_failure and not result.ok:
            break
    return results


def _display_commands(execution_steps: list[dict[str, Any]]) -> list[str]:
    return [str(step["backend"]["display_command"]) for step in execution_steps]


def _transition_step_to_execution(
    app_cli: Any,
    *,
    repo_root: Path,
    target: str,
    key: str,
    transition_step: tuple[list[str], str] | None,
) -> CommandStep | None:
    if transition_step is None:
        return None
    argv, _display = transition_step
    if argv and argv[0] == "ssh":
        ssh_target = app_cli._target_ssh_target(repo_root, target)
        remote_wrapped = str(argv[-1])
        parsed = shlex.split(remote_wrapped)
        shell_command = parsed[-1] if len(parsed) >= 3 and parsed[-2] == "-lc" else remote_wrapped
        return plan_remote_shell_step(
            key,
            ssh_target=ssh_target,
            cwd=None,
            argv=("sh",),
            shell_command=shell_command,
            capabilities=("ssh",),
        )
    executable = str(argv[0]) if argv else "python3"
    display_command = " ".join(str(item) for item in argv)
    return plan_local_backend_step(
        key,
        backend_type=detect_host_profile().linux_backend,
        cwd=repo_root,
        argv=tuple(str(item) for item in argv),
        capabilities=(executable,),
        display_command=display_command,
    )
