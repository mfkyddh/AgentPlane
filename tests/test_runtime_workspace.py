from pathlib import Path

from agentplane.runtime.resolution import WorkspaceResolver
from agentplane.runtime.secret_resolver import SecretResolver
from agentplane.runtime.workspace import resolve_workspace, resolve_workspace_from_repo
from agentplane.runtime.wsl_bridge import windows_path_to_wsl_posix


def test_workspace_derives_linux_backend_root_from_windows_control_root() -> None:
    workspace = resolve_workspace(
        control_root=Path("C:/repos/agentplane"),
        private_root=Path("C:/repos/agentplane/secrets"),
        source_root=Path("C:/repos/agentplane"),
    )

    assert workspace.control_root.as_posix().endswith("repos/agentplane")
    assert workspace.private_root.as_posix().endswith("repos/agentplane/secrets")
    assert workspace.linux_backend_root is not None
    assert workspace.linux_backend_root.as_posix() == "/mnt/c/repos/agentplane"
    assert workspace.source_root.as_posix().endswith("repos/agentplane")
    assert workspace.local_command_root.as_posix().endswith("repos/agentplane")


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
    assert workspace.linux_backend_root is not None
    rendered_backend_root = str(workspace.linux_backend_root).replace("\\", "/")
    expected_wsl_root = windows_path_to_wsl_posix(main_root)
    assert rendered_backend_root in {str(main_root).replace("\\", "/"), expected_wsl_root}
    assert workspace.source_root == worktree_root
    assert workspace.local_command_root == worktree_root


def test_workspace_from_windows_repo_derives_linux_backend_root() -> None:
    workspace = resolve_workspace_from_repo(Path("C:/repos/agentplane"))

    assert workspace.control_root.as_posix().endswith("repos/agentplane")
    assert workspace.private_root.as_posix().endswith("repos/agentplane/secrets")
    assert workspace.linux_backend_root is not None
    assert workspace.linux_backend_root.as_posix() == "/mnt/c/repos/agentplane"


def test_workspace_resolver_exposes_linux_staging_root_for_unc_control_root() -> None:
    workspace = resolve_workspace(
        control_root=Path(r"\\wsl.localhost\Ubuntu\srv\control-plane\agentplane"),
        private_root=Path(r"\\wsl.localhost\Ubuntu\srv\control-plane\agentplane\secrets"),
        source_root=Path("/srv/control-plane/agentplane"),
    )

    resolver = WorkspaceResolver.from_workspace(
        repo_root=Path(r"\\wsl.localhost\Ubuntu\srv\control-plane\agentplane"),
        workspace=workspace,
    )

    assert resolver.bindings.artifact_staging_root.as_posix() == "/srv/control-plane/agentplane/.agentplane/staging"
    assert resolver.bindings.source_root.as_posix() == "/srv/control-plane/agentplane"
    assert resolver.bindings.local_command_root.as_posix() == "/srv/control-plane/agentplane"


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
