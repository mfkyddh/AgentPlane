from pathlib import Path

from agentplane.runtime.workspace import resolve_workspace, resolve_workspace_from_repo


def test_workspace_resolves_windows_control_root_and_wsl_backend_root() -> None:
    workspace = resolve_workspace(
        control_root=Path("D:/Projects/AgentPlane"),
        legacy_control_root=Path("/root/work/AgentPlane"),
        private_root=Path("D:/Projects/AgentPlane/secrets"),
        linux_backend_root=Path("/root/work/AgentPlane"),
    )

    assert workspace.control_root.as_posix().endswith("Projects/AgentPlane")
    assert workspace.private_root.as_posix().endswith("Projects/AgentPlane/secrets")
    assert str(workspace.linux_backend_root) == "/root/work/AgentPlane"


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
