from __future__ import annotations

from agentplane.runtime.execution import (
    ExecutionBindings,
    ExecutionPlan,
    RenderedExecution,
    require_local_executable,
    shell_join,
)
from agentplane.runtime.backends.registry import register_backend


@register_backend("linux-native")
class LinuxNativeBackend:
    backend_type = "linux-native"

    def render(self, plan: ExecutionPlan, bindings: ExecutionBindings) -> RenderedExecution:
        require_local_executable(plan.argv[0])
        cwd = bindings.resolve_cwd(plan.cwd_ref)
        env = bindings.resolve_env(plan.env_refs)
        stdin_text = bindings.resolve_input(plan.input_refs)
        display_command = shell_join(plan.argv)
        return RenderedExecution(
            backend_type=self.backend_type,
            argv=plan.argv,
            display_command=display_command,
            cwd=cwd,
            env=env,
            stdin_text=stdin_text,
            expected_outputs=plan.expected_outputs,
            capabilities=plan.capabilities,
        )
