from __future__ import annotations

import shlex

from agentplane.runtime.execution import ExecutionBindings, ExecutionPlan, RenderedExecution, env_prefixed_command, require_local_executable, shell_join
from agentplane.runtime.wsl_bridge import windows_path_to_wsl_posix


def _is_windows_drive_path(value: str) -> bool:
    return len(value) >= 2 and value[0].isalpha() and value[1] == ":"


def _is_wsl_unc_path(value: str) -> bool:
    normalized = value.replace("/", "\\").lower()
    return normalized.startswith("\\\\wsl.localhost\\") or normalized.startswith("\\\\wsl$\\")


def _is_windows_mount_path(value: str | None) -> bool:
    if value is None:
        return False
    normalized = value.replace("\\", "/").lower().rstrip("/")
    if not normalized.startswith("/mnt/"):
        return False
    parts = normalized.split("/")
    return len(parts) >= 3 and len(parts[2]) == 1 and parts[2].isalpha()


class WindowsWslBackend:
    backend_type = "windows-wsl"

    def render(self, plan: ExecutionPlan, bindings: ExecutionBindings) -> RenderedExecution:
        cwd = bindings.resolve_cwd(plan.cwd_ref)
        rendered_cwd = "" if cwd is None else str(cwd)
        posix_cwd = windows_path_to_wsl_posix(cwd)
        if (
            _is_windows_drive_path(rendered_cwd)
            or _is_wsl_unc_path(rendered_cwd)
            or _is_windows_mount_path(posix_cwd)
        ):
            raise ValueError(
                "AgentPlane forbids using a Windows checkout as the WSL working directory. "
                "Use a separate Linux-filesystem checkout for WSL backend commands."
            )

        require_local_executable("wsl.exe")
        env = bindings.resolve_env(plan.env_refs)
        stdin_text = bindings.resolve_input(plan.input_refs)
        linux_command = env_prefixed_command(plan.argv, env)
        if posix_cwd:
            linux_command = f"cd {shlex.quote(posix_cwd)} && {linux_command}"
        argv = ("wsl.exe", "-e", "bash", "-lc", linux_command)
        return RenderedExecution(
            backend_type=self.backend_type,
            argv=argv,
            display_command=shell_join(argv),
            cwd=None,
            env={},
            stdin_text=stdin_text,
            expected_outputs=plan.expected_outputs,
            capabilities=plan.capabilities,
            metadata={"linux_command": linux_command},
        )
