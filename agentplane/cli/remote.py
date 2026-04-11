from __future__ import annotations

import shlex
import select
import subprocess
import sys
from pathlib import Path
from typing import Any

from agentplane.cli.operations import append_operation_ledger, next_operation_id
from agentplane.ssh import resolve_ssh_target


def _strip_remainder_separator(args: list[str]) -> list[str]:
    if args[:1] == ["--"]:
        return args[1:]
    return args


def _render_payload(
    *,
    repo_root: Path,
    target: str,
    ssh_target: Any,
    remote_command: str,
    ssh_argv: list[str],
    display_command: str,
    transport: str,
    script_file: Path | None,
    dry_run: bool,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "command": "remote",
        "action": "bash",
        "ok": True,
        "target": target,
        "repo_root": str(repo_root),
        "transport": transport,
        "ssh_config": str(ssh_target.config_path),
        "connection_target": ssh_target.connection_target,
        "remote_command": remote_command,
        "ssh_argv": ssh_argv,
        "display_command": display_command,
        "dry_run": dry_run,
    }
    if script_file is not None:
        payload["script_file"] = str(script_file)
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
            "connection_target": payload["connection_target"],
            "remote_command": payload["remote_command"],
            "script_file": payload.get("script_file"),
        },
    )
    operation = {
        "op_id": op_id,
        "result": result,
        "ledger_file": ledger["ledger_file"],
    }
    payload["operation"] = operation
    return operation


def _execute_remote_bash(
    command: list[str],
    *,
    transport: str,
    script_file: Path | None,
    stdin_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    if transport == "inline-command":
        return subprocess.run(command, text=True, capture_output=True, check=False)

    if script_file is not None:
        with script_file.open("r", encoding="utf-8") as handle:
            return subprocess.run(command, stdin=handle, text=True, capture_output=True, check=False)

    if stdin_text is None:
        stdin_text = sys.stdin.read()
    if not stdin_text:
        raise ValueError("stdin is empty; pass --script-file <linux-path> or pipe a script body")
    return subprocess.run(command, input=stdin_text, text=True, capture_output=True, check=False)


def _read_piped_stdin() -> str | None:
    if sys.stdin.closed or sys.stdin.isatty():
        return None
    ready, _, _ = select.select([sys.stdin], [], [], 0)
    if not ready:
        return None
    text = sys.stdin.read()
    if not text:
        return None
    return text


def _inline_command_from_args(remote_args: list[str]) -> str:
    return " ".join(shlex.quote(arg) for arg in remote_args)


def execute_remote_bash(
    *,
    repo_root: Path,
    target: str,
    remote_args: list[str] | None = None,
    script_file: str | Path | None = None,
    stdin_text: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    repo_root = Path(repo_root).resolve()
    remote_args = _strip_remainder_separator(list(remote_args or []))
    script_file = Path(script_file).resolve() if script_file is not None else None
    if script_file is not None and not script_file.is_file():
        raise ValueError(f"Script file not found: {script_file}")

    effective_stdin = stdin_text
    if script_file is None and effective_stdin is None:
        effective_stdin = _read_piped_stdin()

    ssh_target = resolve_ssh_target(repo_root, target)
    if script_file is not None:
        transport = "script-file"
        remote_command = ssh_target.wrap_bash_stdin(remote_args)
        ssh_argv = ssh_target.ssh_args_for_bash_stdin(remote_args)
        display_command = ssh_target.display_ssh_bash_stdin(remote_args)
    elif effective_stdin is not None:
        transport = "stdin"
        remote_command = ssh_target.wrap_bash_stdin(remote_args)
        ssh_argv = ssh_target.ssh_args_for_bash_stdin(remote_args)
        display_command = ssh_target.display_ssh_bash_stdin(remote_args)
    elif remote_args:
        transport = "inline-command"
        inline_command = _inline_command_from_args(remote_args)
        remote_command = ssh_target.wrap_shell(inline_command)
        ssh_argv = ssh_target.ssh_args_for_shell(inline_command)
        display_command = ssh_target.display_ssh_command(inline_command)
    else:
        transport = "stdin"
        remote_command = ssh_target.wrap_bash_stdin(remote_args)
        ssh_argv = ssh_target.ssh_args_for_bash_stdin(remote_args)
        display_command = ssh_target.display_ssh_bash_stdin(remote_args)

    payload = _render_payload(
        repo_root=repo_root,
        target=target,
        ssh_target=ssh_target,
        remote_command=remote_command,
        ssh_argv=ssh_argv,
        display_command=display_command,
        transport=transport,
        script_file=script_file,
        dry_run=dry_run,
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

    result = _execute_remote_bash(
        payload["ssh_argv"],
        transport=transport,
        script_file=script_file,
        stdin_text=effective_stdin,
    )
    payload["ok"] = result.returncode == 0
    payload["result"] = {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }
    _record_operation(
        repo_root,
        target=target,
        payload=payload,
        op_id=op_id,
        result="succeeded" if result.returncode == 0 else "failed",
    )
    return payload
