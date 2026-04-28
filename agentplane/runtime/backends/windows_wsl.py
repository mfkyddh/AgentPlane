from __future__ import annotations

import shlex

from agentplane.runtime.backends.registry import register_backend
from agentplane.runtime.execution import (
    ExecutionBindings,
    ExecutionPlan,
    RenderedExecution,
    env_prefixed_command,
    require_local_executable,
    shell_join,
)
from agentplane.runtime.wsl_bridge import windows_path_to_wsl_posix


@register_backend("windows-wsl")
class WindowsWslBackend:
    backend_type = "windows-wsl"

    def render(self, plan: ExecutionPlan, bindings: ExecutionBindings) -> RenderedExecution:
        cwd = bindings.resolve_cwd(plan.cwd_ref)
        posix_cwd = windows_path_to_wsl_posix(cwd)

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
