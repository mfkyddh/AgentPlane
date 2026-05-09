from __future__ import annotations

import os
import select
import sys
from pathlib import Path
from typing import Any

from agentplane.runtime.backends import build_backend_runner
from agentplane.runtime.execution import CommandSpec, shell_join
from agentplane.runtime.host_profile import detect_host_profile
from agentplane.runtime.intent_guard import Intent, guard
from agentplane.runtime.operations import append_operation_ledger, next_operation_id
from agentplane.runtime.target_resolver import TargetResolver
from agentplane.ssh import resolve_ssh_target


def _strip_remainder_separator(args: list[str]) -> list[str]:
    if args[:1] == ["--"]:
        return args[1:]
    return args


def _read_piped_stdin() -> str | None:
    if sys.stdin.closed or sys.stdin.isatty():
        return None
    if os.name == "nt":
        text = sys.stdin.read()
        return text or None
    ready, _, _ = select.select([sys.stdin], [], [], 0)
    if not ready:
        return None
    text = sys.stdin.read()
    if not text:
        return None
    return text


def _build_remote_execution(
    *,
    repo_root: Path,
    target: str,
    remote_args: list[str],
    script_file: Path | None,
    stdin_text: str | None,
) -> tuple[str, CommandSpec]:
    target_resolution = TargetResolver(detect_host_profile()).resolve(target)
    effective_stdin = stdin_text
    if script_file is not None:
        effective_stdin = script_file.read_text(encoding="utf-8")
    if script_file is None and effective_stdin is None:
        effective_stdin = _read_piped_stdin()
    if effective_stdin is not None:
        effective_stdin = effective_stdin.replace("\r\n", "\n").replace("\r", "\n")

    if target_resolution.is_local:
        backend_type = str(target_resolution.execution_backend)
        if script_file is not None:
            transport = "script-file"
            argv = ("bash", "-s", "--", *remote_args)
        elif effective_stdin is not None or not remote_args:
            transport = "stdin"
            argv = ("bash", "-s", "--", *remote_args)
        else:
            transport = "inline-command"
            argv = tuple(remote_args)
        spec = CommandSpec(
            backend_type=backend_type,  # type: ignore[arg-type]
            argv=argv,
            cwd=repo_root,
            stdin_text=effective_stdin if effective_stdin else None,
            capabilities=("bash",),
            timeout=300,
        )
        return transport, spec

    ssh_target = resolve_ssh_target(repo_root, target_resolution.ssh_alias or target)
    if script_file is not None:
        transport = "script-file"
        metadata: dict[str, Any] = {"transport": "bash-stdin", "ssh_target": ssh_target}
    elif effective_stdin is not None or not remote_args:
        transport = "stdin"
        metadata = {"transport": "bash-stdin", "ssh_target": ssh_target}
    else:
        transport = "inline-command"
        metadata = {"transport": "shell", "ssh_target": ssh_target}
    spec = CommandSpec(
        backend_type="ssh-linux",
        argv=tuple(remote_args),
        stdin_text=effective_stdin if effective_stdin else None,
        capabilities=("ssh",),
        timeout=300,
        metadata=metadata,
    )
    return transport, spec


def _render_payload(
    *,
    repo_root: Path,
    target: str,
    transport: str,
    spec: CommandSpec,
    rendered: dict[str, Any],
    script_file: Path | None,
    dry_run: bool,
    intent: Intent = "mutation",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "command": "remote",
        "action": "bash",
        "ok": True,
        "target": target,
        "repo_root": str(repo_root),
        "transport": transport,
        "backend_type": spec.backend_type,
        "execution_plan": spec.to_payload(),
        "backend": rendered,
        "display_command": rendered["display_command"],
        "dry_run": dry_run,
        "intent": intent,
    }
    metadata = rendered.get("metadata", {})
    if script_file is not None:
        payload["script_file"] = str(script_file)
    if "ssh_config" in metadata:
        payload["ssh_config"] = metadata["ssh_config"]
    if "connection_target" in metadata:
        payload["connection_target"] = metadata["connection_target"]
    if "remote_command" in metadata:
        payload["remote_command"] = metadata["remote_command"]
    if spec.backend_type == "ssh-linux":
        payload["ssh_argv"] = rendered["argv"]
    else:
        payload["argv"] = rendered["argv"]
    if "error" in rendered:
        payload["error"] = rendered["error"]
    return payload


def _record_operation(
    repo_root: Path,
    *,
    target: str,
    payload: dict[str, Any],
    op_id: str,
    result: str,
) -> dict[str, Any]:
    ledger = append_operation_ledger(
        repo_root,
        command="remote",
        action="bash",
        target=target,
        op_id=op_id,
        dry_run=bool(payload["dry_run"]),
        result=result,
        details={
            "transport": payload["transport"],
            "connection_target": payload.get("connection_target", target),
            "remote_command": payload.get("remote_command", shell_join(payload["execution_plan"]["argv"])),
            "script_file": payload.get("script_file"),
            "backend_type": payload["backend_type"],
        },
    )
    operation = {
        "op_id": op_id,
        "result": result,
        "ledger_file": ledger["ledger_file"],
    }
    payload["operation"] = operation
    return operation


def execute_remote_bash(
    *,
    repo_root: Path,
    target: str,
    remote_args: list[str] | None = None,
    script_file: str | Path | None = None,
    stdin_text: str | None = None,
    dry_run: bool = False,
    intent: Intent = "mutation",
    stream: bool = False,
) -> dict[str, Any]:
    repo_root = Path(repo_root).resolve()
    remote_args = _strip_remainder_separator(list(remote_args or []))
    resolved_script = Path(script_file).resolve() if script_file is not None else None
    if resolved_script is not None and not resolved_script.is_file():
        raise ValueError(f"Script file not found: {resolved_script}")

    transport, spec = _build_remote_execution(
        repo_root=repo_root,
        target=target,
        remote_args=remote_args,
        script_file=resolved_script,
        stdin_text=stdin_text,
    )
    if not dry_run and transport in {"stdin", "script-file"} and not spec.stdin_text:
        raise ValueError("stdin is empty; pass --script-file <linux-path> or pipe a script body")

    # Intent guard: validate declared intent against inferred command semantics
    if transport == "inline-command":
        guard(intent, argv=spec.argv)
    else:
        guard(intent, argv=spec.argv, stdin_text=spec.stdin_text)

    runner = build_backend_runner()
    rendered = runner.render_spec(spec)
    payload = _render_payload(
        repo_root=repo_root,
        target=target,
        transport=transport,
        spec=spec,
        rendered=rendered.to_payload(),
        script_file=resolved_script,
        dry_run=dry_run,
        intent=intent,
    )

    op_id = next_operation_id("remote-bash")
    if dry_run:
        _record_operation(
            repo_root,
            target=target,
            payload=payload,
            op_id=op_id,
            result="planned",
        )
        return payload

    if stream:
        import sys

        result = runner.execute_spec_stream(
            spec,
            on_chunk=lambda chunk: (
                sys.stdout.write(chunk.text) if chunk.stream == "stdout" else sys.stderr.write(chunk.text)
            ),
        )
    else:
        result = runner.execute_spec(spec)
    payload["ok"] = result.ok
    payload["result"] = result.to_payload()
    _record_operation(
        repo_root,
        target=target,
        payload=payload,
        op_id=op_id,
        result="succeeded" if result.ok else "failed",
    )
    return payload
