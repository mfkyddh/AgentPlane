from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from pathlib import Path

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

    def resolve_many(self, targets: list[str]) -> list[ResolvedTarget]:
        return [self.resolve(t) for t in targets]

    @staticmethod
    def known_targets(repo_root: Path | str | None = None) -> list[str]:
        """Return statically known targets plus inventory-discovered ones."""
        static = ["wsl"]
        if repo_root is None:
            return static
        inventory_root = Path(repo_root) / "inventory" / "servers"
        if not inventory_root.is_dir():
            return static
        discovered = [p.name for p in inventory_root.iterdir() if p.is_dir() and not p.name.startswith(".")]
        combined = list(dict.fromkeys([*static, *sorted(discovered)]))
        return combined

    def resolve_expression(self, expression: str, *, repo_root: Path | str | None = None) -> list[ResolvedTarget]:
        """Resolve a target expression.

        Supported syntax:
        - ``all`` or ``*`` → every known target.
        - ``prod*`` → fnmatch against known targets.
        - ``wsl,prod0-main`` → comma-separated list.
        """
        expression = expression.strip()
        if expression in ("all", "*"):
            targets = self.known_targets(repo_root)
        elif "," in expression:
            targets = [t.strip() for t in expression.split(",") if t.strip()]
        else:
            candidates = self.known_targets(repo_root)
            matched = [c for c in candidates if fnmatch.fnmatch(c, expression)]
            targets = matched if matched else [expression]
        return self.resolve_many(targets)
