from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path

from agentplane.runtime.backends.registry import register_backend
from agentplane.runtime.execution import (
    CommandSpec,
    ExecutionBindings,
    ExecutionPlan,
    ExecutionResult,
    RenderedExecution,
    env_prefixed_command,
    require_local_executable,
)
from agentplane.ssh import SshTarget


@register_backend("ssh-linux")
class SshLinuxBackend:
    backend_type = "ssh-linux"

    def render(self, plan: ExecutionPlan, bindings: ExecutionBindings) -> RenderedExecution:
        transport = str(bindings.metadata.get("transport") or "shell")
        ssh_target = bindings.metadata.get("ssh_target")
        if not isinstance(ssh_target, SshTarget):
            raise ValueError("ssh-linux backend requires ssh_target metadata")
        stdin_text = bindings.resolve_input(plan.input_refs)

        if transport == "copy-to-remote":
            require_local_executable("wsl.exe" if os.name == "nt" else "scp")
            local_path = self._require_path(bindings.metadata.get("local_path"), field="local_path")
            remote_path = self._require_str(bindings.metadata.get("remote_path"), field="remote_path")
            argv = tuple(ssh_target.local_scp_args(str(local_path), remote_path))
            display = ssh_target.display_scp_command(str(local_path), remote_path)
            metadata = {
                "transport": transport,
                "connection_target": ssh_target.connection_target,
                "ssh_config": str(ssh_target.config_path),
            }
            return RenderedExecution(
                backend_type=self.backend_type,
                argv=argv,
                display_command=display,
                cwd=None,
                env={},
                stdin_text=None,
                expected_outputs=plan.expected_outputs,
                capabilities=plan.capabilities,
                metadata=metadata,
            )

        require_local_executable("wsl.exe" if os.name == "nt" else "ssh")
        cwd = bindings.resolve_cwd(plan.cwd_ref)
        env = bindings.resolve_env(plan.env_refs)
        if transport == "bash-stdin":
            remote_args = list(plan.argv)
            argv = tuple(ssh_target.local_ssh_args_for_bash_stdin(remote_args))
            remote_command = ssh_target.wrap_bash_stdin(remote_args)
            display = ssh_target.display_ssh_bash_stdin(remote_args)
        else:
            shell_command = bindings.metadata.get("shell_command")
            if isinstance(shell_command, str) and shell_command:
                remote_command = shell_command
            else:
                remote_command = env_prefixed_command(plan.argv, env)
            if cwd is not None:
                remote_command = f"cd {shlex.quote(str(cwd))} && {remote_command}"
            argv = tuple(ssh_target.local_ssh_args_for_shell(remote_command))
            display = ssh_target.display_ssh_command(remote_command)
        metadata = {
            "transport": transport,
            "connection_target": ssh_target.connection_target,
            "ssh_config": str(ssh_target.config_path),
            "remote_command": remote_command,
        }
        return RenderedExecution(
            backend_type=self.backend_type,
            argv=argv,
            display_command=display,
            cwd=None,
            env={},
            stdin_text=stdin_text,
            expected_outputs=plan.expected_outputs,
            capabilities=plan.capabilities,
            metadata=metadata,
        )

    def render_spec(self, spec: CommandSpec) -> RenderedExecution:
        transport = str(spec.metadata.get("transport") or "shell")
        ssh_target = spec.metadata.get("ssh_target")
        if not isinstance(ssh_target, SshTarget):
            raise ValueError("ssh-linux backend requires ssh_target metadata")

        if transport == "copy-to-remote":
            require_local_executable("wsl.exe" if os.name == "nt" else "scp")
            local_path = self._require_path(spec.metadata.get("local_path"), field="local_path")
            remote_path = self._require_str(spec.metadata.get("remote_path"), field="remote_path")
            argv = tuple(ssh_target.local_scp_args(str(local_path), remote_path))
            display = ssh_target.display_scp_command(str(local_path), remote_path)
            metadata = {
                "transport": transport,
                "connection_target": ssh_target.connection_target,
                "ssh_config": str(ssh_target.config_path),
            }
            return RenderedExecution(
                backend_type=self.backend_type,
                argv=argv,
                display_command=display,
                cwd=None,
                env={},
                stdin_text=None,
                expected_outputs=spec.expected_outputs,
                capabilities=spec.capabilities,
                metadata=metadata,
            )

        require_local_executable("wsl.exe" if os.name == "nt" else "ssh")
        if transport == "bash-stdin":
            remote_args = list(spec.argv)
            argv = tuple(ssh_target.local_ssh_args_for_bash_stdin(remote_args))
            remote_command = ssh_target.wrap_bash_stdin(remote_args)
            display = ssh_target.display_ssh_bash_stdin(remote_args)
        else:
            shell_command = spec.metadata.get("shell_command")
            if isinstance(shell_command, str) and shell_command:
                remote_command = shell_command
            else:
                remote_command = env_prefixed_command(spec.argv, spec.env)
            if spec.cwd is not None:
                remote_command = f"cd {shlex.quote(str(spec.cwd))} && {remote_command}"
            argv = tuple(ssh_target.local_ssh_args_for_shell(remote_command))
            display = ssh_target.display_ssh_command(remote_command)
        metadata = {
            "transport": transport,
            "connection_target": ssh_target.connection_target,
            "ssh_config": str(ssh_target.config_path),
            "remote_command": remote_command,
        }
        return RenderedExecution(
            backend_type=self.backend_type,
            argv=argv,
            display_command=display,
            cwd=None,
            env={},
            stdin_text=spec.stdin_text,
            expected_outputs=spec.expected_outputs,
            capabilities=spec.capabilities,
            metadata=metadata,
        )

    @staticmethod
    def _require_path(value: object, *, field: str) -> Path:
        if isinstance(value, Path):
            return value
        if isinstance(value, str) and value:
            return Path(value)
        raise ValueError(f"ssh-linux backend requires {field} metadata")

    @staticmethod
    def _require_str(value: object, *, field: str) -> str:
        if isinstance(value, str) and value:
            return value
        raise ValueError(f"ssh-linux backend requires {field} metadata")


def stream_docker_image(image: str, ssh_target: SshTarget) -> ExecutionResult:
    """Pipe docker save directly to ssh docker load, avoiding intermediate tar files."""
    save_cmd = ["docker", "save", image]
    ssh_args = ssh_target.local_ssh_args_for_argv(["docker", "load"])
    display = f"docker save {shlex.quote(image)} | ssh {ssh_target.connection_target} docker load"

    save_proc = subprocess.Popen(save_cmd, stdout=subprocess.PIPE)
    load_proc = subprocess.Popen(ssh_args, stdin=save_proc.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    save_proc.stdout.close()
    load_stdout, load_stderr = load_proc.communicate()
    save_proc.wait()

    returncode = max(save_proc.returncode or 0, load_proc.returncode or 0)
    stderr = load_stderr.decode("utf-8", errors="replace") if load_stderr else ""
    if save_proc.returncode != 0:
        stderr = f"docker save failed (exit {save_proc.returncode})" + (f"\n{stderr}" if stderr else "")

    return ExecutionResult(
        backend_type="ssh-linux",
        argv=tuple(ssh_args),
        display_command=display,
        cwd=None,
        returncode=returncode,
        stdout="",
        stderr=stderr,
        ok=returncode == 0,
    )
