from __future__ import annotations

import shlex

from agentplane.runtime.execution import (
    ExecutionBindings,
    ExecutionPlan,
    RenderedExecution,
    env_prefixed_command,
    require_local_executable,
    shell_join,
)


class MacosLimaBackend:
    backend_type = "macos-lima"

    def render(self, plan: ExecutionPlan, bindings: ExecutionBindings) -> RenderedExecution:
        require_local_executable("limactl")
        cwd = bindings.resolve_cwd(plan.cwd_ref)
        env = bindings.resolve_env(plan.env_refs)
        stdin_text = bindings.resolve_input(plan.input_refs)
        linux_command = env_prefixed_command(plan.argv, env)
        if cwd is not None:
            linux_command = f"cd {shlex.quote(str(cwd))} && {linux_command}"
        argv = ("limactl", "shell", "default", "bash", "-lc", linux_command)
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
