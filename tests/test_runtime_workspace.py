from pathlib import Path

from agentplane.runtime.resolution import WorkspaceResolver
from agentplane.runtime.secret_resolver import SecretResolver
from agentplane.runtime.workspace import resolve_workspace, resolve_workspace_from_repo


def test_workspace_resolves_windows_control_root_and_wsl_backend_root() -> None:
    workspace = resolve_workspace(
        control_root=Path("D:/Projects/AgentPlane"),
        legacy_control_root=Path("/root/work/AgentPlane"),
        private_root=Path("D:/Projects/AgentPlane/secrets"),
        linux_backend_root=Path("/root/work/AgentPlane"),
        source_root=Path("D:/Projects/AgentPlane"),
    )

    assert workspace.control_root.as_posix().endswith("Projects/AgentPlane")
    assert workspace.private_root.as_posix().endswith("Projects/AgentPlane/secrets")
    assert workspace.linux_backend_root is not None
    assert workspace.linux_backend_root.as_posix() == "/root/work/AgentPlane"
    assert workspace.source_root.as_posix().endswith("Projects/AgentPlane")
    assert workspace.local_command_root.as_posix().endswith("Projects/AgentPlane")


def test_workspace_from_repo_uses_common_root_for_private_materials(tmp_path: Path) -> None:
    main_root = tmp_path / "main"
    worktree_root = tmp_path / "worktree"
    git_worktree_dir = main_root / ".git" / "worktrees" / "demo"

    (main_root / "secrets").mkdir(parents=True, exist_ok=True)
    git_worktree_dir.mkdir(parents=True, exist_ok=True)
    worktree_root.mkdir(parents=True, exist_ok=True)
    (worktree_root / ".git").write_text(f"gitdir: {git_worktree_dir}\n", encoding="utf-8")

    workspace = resolve_workspace_from_repo(worktree_root)

    assert workspace.control_root == main_root
    assert workspace.private_root == main_root / "secrets"
    assert workspace.linux_backend_root == main_root
    assert workspace.source_root == worktree_root
    assert workspace.local_command_root == worktree_root


def test_workspace_resolver_exposes_linux_staging_root_for_windows_host() -> None:
    workspace = resolve_workspace(
        control_root=Path("D:/Projects/AgentPlane"),
        legacy_control_root=Path("/root/work/AgentPlane"),
        private_root=Path("D:/Projects/AgentPlane/secrets"),
        linux_backend_root=Path("/root/work/AgentPlane"),
        source_root=Path("/root/work/AgentPlane"),
    )

    resolver = WorkspaceResolver.from_workspace(repo_root=Path("D:/Projects/AgentPlane"), workspace=workspace)

    assert resolver.bindings.artifact_staging_root.as_posix() == "/root/work/AgentPlane/.agentplane/staging"
    assert resolver.bindings.source_root.as_posix() == "/root/work/AgentPlane"
    assert resolver.bindings.local_command_root.as_posix() == "/root/work/AgentPlane"


def test_secret_resolver_uses_main_repo_private_root_for_git_worktree(tmp_path: Path) -> None:
    main_root = tmp_path / "main"
    worktree_root = tmp_path / "worktree"
    git_worktree_dir = main_root / ".git" / "worktrees" / "demo"

    (main_root / "secrets" / "ssh").mkdir(parents=True, exist_ok=True)
    git_worktree_dir.mkdir(parents=True, exist_ok=True)
    worktree_root.mkdir(parents=True, exist_ok=True)
    (worktree_root / ".git").write_text(f"gitdir: {git_worktree_dir}\n", encoding="utf-8")

    secret_path = SecretResolver.from_repo_root(worktree_root).ssh_config_path()

    assert secret_path == main_root / "secrets" / "ssh" / "config"
