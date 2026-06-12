from __future__ import annotations

from pathlib import Path
from typing import Any

from agentplane.domain.infra.audit_common import SUPPORTED_AUDIT_ENVS
from agentplane.domain.infra.audit_prod0 import _audit_prod0_inventory
from agentplane.domain.infra.audit_wsl import (
    _audit_wsl_host_state,
    _audit_wsl_host_state_via_backend,
    _audit_wsl_templates,
    _wsl_backend_type,
)
from agentplane.runtime.host_profile import HostProfile

__all__ = ["SUPPORTED_AUDIT_ENVS", "audit_filesystem"]


def audit_filesystem(
    repo_root: Path,
    target_env: str,
    *,
    host_profile: HostProfile | None = None,
    runner: Any | None = None,
) -> dict[str, Any]:
    resolved_root = repo_root.resolve()
    path_check_mode = "local-path"
    if target_env == "wsl":
        backend_type = _wsl_backend_type(host_profile)
        if backend_type == "windows-wsl" and runner is not None:
            path_check_mode = "backend-exec"
            host_violations = _audit_wsl_host_state_via_backend(resolved_root, backend_type=backend_type, runner=runner)
        elif backend_type == "windows-wsl":
            path_check_mode = "tracked-snapshot"
            host_violations = []
        else:
            host_violations = _audit_wsl_host_state(resolved_root)
        violations = _audit_wsl_templates(resolved_root) + host_violations
    elif target_env == "prod0-main":
        violations = _audit_prod0_inventory(resolved_root)
    else:
        raise ValueError(f"Unsupported audit env: {target_env}")
    return {
        "command": "audit filesystem",
        "env": target_env,
        "repo_root": str(resolved_root),
        "ok": not violations,
        "violations": violations,
        "path_check_mode": path_check_mode,
    }
