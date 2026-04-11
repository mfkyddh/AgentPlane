from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agentplane.runtime.resolution import ResolvedReference, WorkspaceResolver


@dataclass(frozen=True)
class SecretResolver:
    workspace_resolver: WorkspaceResolver

    @classmethod
    def from_repo_root(cls, repo_root: Path | str) -> "SecretResolver":
        return cls(workspace_resolver=WorkspaceResolver.from_repo_root(repo_root))

    def resolve_secret_ref(self, secret_ref: str) -> ResolvedReference:
        secret_path = Path(secret_ref)
        if secret_path.is_absolute():
            raise ValueError(f"secret_ref must be relative to private_root: {secret_ref}")
        return self.workspace_resolver.resolve_relative_reference(
            canonical_ref=secret_ref,
            relative_path=secret_path,
            base_root=self.workspace_resolver.bindings.private_root,
        )

    def resolve_ssh_config(self) -> ResolvedReference:
        return self.resolve_secret_ref("ssh/config")

    def ssh_config_path(self) -> Path:
        return self.resolve_ssh_config().resolved_path
