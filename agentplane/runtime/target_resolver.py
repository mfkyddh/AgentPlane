from __future__ import annotations

from dataclasses import dataclass

from agentplane.runtime.host_profile import HostLinuxBackend, HostProfile


@dataclass(frozen=True)
class ResolvedTarget:
    target: str
    canonical_ref: str
    ssh_alias: str | None
    execution_backend: HostLinuxBackend | str
    is_local: bool

    def to_payload(self) -> dict[str, bool | str | None]:
        return {
            "target": self.target,
            "canonical_ref": self.canonical_ref,
            "ssh_alias": self.ssh_alias,
            "execution_backend": self.execution_backend,
            "is_local": self.is_local,
        }


@dataclass(frozen=True)
class TargetResolver:
    host_profile: HostProfile

    def resolve(self, target: str) -> ResolvedTarget:
        if target == "wsl":
            return ResolvedTarget(
                target=target,
                canonical_ref="targets/wsl",
                ssh_alias=None,
                execution_backend=self.host_profile.linux_backend,
                is_local=True,
            )
        return ResolvedTarget(
            target=target,
            canonical_ref=f"targets/{target}",
            ssh_alias=target,
            execution_backend="ssh-linux",
            is_local=False,
        )
