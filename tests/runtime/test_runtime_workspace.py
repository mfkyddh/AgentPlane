from __future__ import annotations
from pathlib import Path
import pytest
from agentplane.runtime.host_profile import HostProfile
from agentplane.runtime.host_profile import host_profile_from_platform
from agentplane.runtime.platform import HostPlatform, select_linux_backend
from agentplane.runtime.resolution import WorkspaceResolver
from agentplane.runtime.secret_resolver import SecretResolver
from agentplane.runtime.target_resolver import TargetResolver
from agentplane.runtime.workspace import resolve_workspace
from agentplane.runtime.workspace import resolve_workspace, resolve_workspace_from_repo
from agentplane.runtime.workspace_path import WorkspacePath
from agentplane.runtime.wsl_bridge import normalize_repo_root_for_current_host, windows_path_to_wsl_posix
from agentplane.runtime.wsl_bridge import windows_path_to_wsl_posix

pytestmark = pytest.mark.integration

def test_workspace_derives_wsl_root_from_windows_control_root_for_single_checkout() -> None:
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
    if workspace.linux_backend_root is not None:
        rendered_backend_root = str(workspace.linux_backend_root).replace("\\", "/")
        expected_wsl_root = windows_path_to_wsl_posix(main_root)
        assert rendered_backend_root in {str(main_root).replace("\\", "/"), expected_wsl_root}
    assert workspace.source_root == worktree_root
    assert workspace.local_command_root == worktree_root

def test_workspace_from_windows_repo_binds_linux_backend_to_same_checkout() -> None:
    workspace = resolve_workspace_from_repo(Path("C:/repos/agentplane"))

    assert workspace.control_root.as_posix().endswith("repos/agentplane")
    assert workspace.private_root.as_posix().endswith("repos/agentplane/secrets")
    assert workspace.linux_backend_root is not None
    assert workspace.linux_backend_root.as_posix() == "/mnt/c/repos/agentplane"

def test_workspace_accepts_windows_mounted_wsl_control_root() -> None:
    workspace = resolve_workspace(control_root=Path("/mnt/c/repos/agentplane"))

    assert workspace.control_root.as_posix() == "/mnt/c/repos/agentplane"
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

# ======================================================================
# From: test_workspace_path.py
# ======================================================================

def test_workspace_path_posix() -> None:
    ws = resolve_workspace(control_root=Path("/srv/agentplane"))
    wp = WorkspacePath(workspace=ws, canonical_ref="apps/sub2api/contract.yaml")
    assert wp.posix_path.as_posix() == "/srv/agentplane/apps/sub2api/contract.yaml"

def test_workspace_path_windows() -> None:
    ws = resolve_workspace(control_root=Path("C:/repos/agentplane"))
    wp = WorkspacePath(workspace=ws, canonical_ref="apps/sub2api/contract.yaml")
    assert wp.windows_path is not None
    assert "C:/repos/agentplane/apps/sub2api/contract.yaml" == str(wp.windows_path).replace("\\", "/")
    assert wp.wsl_path is not None
    assert wp.wsl_path.as_posix() == "/mnt/c/repos/agentplane/apps/sub2api/contract.yaml"

def test_workspace_path_linux_backend() -> None:
    ws = resolve_workspace(control_root=Path("C:/repos/agentplane"))
    wp = WorkspacePath(workspace=ws, canonical_ref="secrets/ssh/config")
    assert wp.linux_backend_path is not None
    assert wp.linux_backend_path.as_posix() == "/mnt/c/repos/agentplane/secrets/ssh/config"

def test_workspace_path_joinpath() -> None:
    ws = resolve_workspace(control_root=Path("/srv/agentplane"))
    wp = WorkspacePath(workspace=ws, canonical_ref="apps/sub2api")
    child = wp.joinpath("contracts", "prod0-main.yaml")
    assert child.canonical_ref == "apps/sub2api/contracts/prod0-main.yaml"

def test_workspace_path_with_suffix() -> None:
    ws = resolve_workspace(control_root=Path("/srv/agentplane"))
    wp = WorkspacePath(workspace=ws, canonical_ref="apps/sub2api/contract.yaml")
    changed = wp.with_suffix(".json")
    assert changed.canonical_ref == "apps/sub2api/contract.json"

def test_workspace_path_from_physical() -> None:
    ws = resolve_workspace(control_root=Path("C:/repos/agentplane"))
    wp = WorkspacePath.from_physical(ws, "C:/repos/agentplane/infra/compose/redis")
    assert wp.canonical_ref == "infra/compose/redis"

def test_workspace_path_payload() -> None:
    ws = resolve_workspace(control_root=Path("C:/repos/agentplane"))
    wp = WorkspacePath(workspace=ws, canonical_ref="apps/sub2api")
    payload = wp.to_payload()
    assert payload["canonical_ref"] == "apps/sub2api"
    assert str(payload["posix_path"]).replace("\\", "/") == "C:/repos/agentplane/apps/sub2api"
    assert str(payload["wsl_path"]).replace("\\", "/") == "/mnt/c/repos/agentplane/apps/sub2api"
    assert str(payload["linux_backend_path"]).replace("\\", "/") == "/mnt/c/repos/agentplane/apps/sub2api"

# ======================================================================
# From: test_target_expression.py
# ======================================================================

def test_resolve_many_returns_list() -> None:
    resolver = TargetResolver(HostProfile(os_name="windows", linux_backend="windows-wsl", supports_docker=True))
    results = resolver.resolve_many(["wsl", "prod0-main"])
    assert len(results) == 2
    assert results[0].is_local is True
    assert results[1].is_local is False

def test_resolve_expression_all_returns_known_targets(tmp_path: Path) -> None:
    resolver = TargetResolver(HostProfile(os_name="windows", linux_backend="windows-wsl", supports_docker=True))
    # Without repo_root: only wsl
    assert resolver.resolve_expression("all") == [resolver.resolve("wsl")]
    assert resolver.resolve_expression("*") == [resolver.resolve("wsl")]

    # With repo_root containing inventory servers
    servers = tmp_path / "inventory" / "servers"
    (servers / "prod0-main").mkdir(parents=True)
    (servers / "prod2-main").mkdir(parents=True)
    results = resolver.resolve_expression("all", repo_root=tmp_path)
    assert [r.target for r in results] == ["wsl", "prod0-main", "prod2-main"]

def test_resolve_expression_comma_separated() -> None:
    resolver = TargetResolver(HostProfile(os_name="windows", linux_backend="windows-wsl", supports_docker=True))
    results = resolver.resolve_expression("wsl,prod0-main")
    assert [r.target for r in results] == ["wsl", "prod0-main"]

def test_resolve_expression_wildcard(tmp_path: Path) -> None:
    resolver = TargetResolver(HostProfile(os_name="windows", linux_backend="windows-wsl", supports_docker=True))
    servers = tmp_path / "inventory" / "servers"
    (servers / "prod0-main").mkdir(parents=True)
    (servers / "prod2-main").mkdir(parents=True)
    (servers / "staging0").mkdir(parents=True)

    results = resolver.resolve_expression("prod*", repo_root=tmp_path)
    assert [r.target for r in results] == ["prod0-main", "prod2-main"]

def test_resolve_expression_unknown_target_falls_back_to_literal() -> None:
    resolver = TargetResolver(HostProfile(os_name="windows", linux_backend="windows-wsl", supports_docker=True))
    results = resolver.resolve_expression("custom-target")
    assert len(results) == 1
    assert results[0].target == "custom-target"
    assert results[0].execution_backend == "ssh-linux"

# ======================================================================
# From: test_runtime_platform.py
# ======================================================================

def test_selects_wsl_linux_backend_for_windows_host() -> None:
    facts = HostPlatform(os_name="windows", has_wsl=True, is_wsl=False)

    backend = select_linux_backend(facts)

    assert backend.backend_type == "wsl-linux"
    assert backend.executable == ("wsl.exe", "-e")
    assert backend.shell_executable == ("wsl.exe", "-e", "bash", "-lc")

def test_selects_native_backend_inside_wsl_linux() -> None:
    facts = HostPlatform(os_name="linux", has_wsl=True, is_wsl=True)

    backend = select_linux_backend(facts)

    assert backend.backend_type == "native-posix"
    assert backend.executable == ()
    assert backend.shell_executable == ("bash", "-lc")

def test_windows_backend_prefers_direct_program_invocation_for_simple_commands() -> None:
    backend = select_linux_backend(HostPlatform(os_name="windows", has_wsl=True, is_wsl=False))

    assert backend.program_argv("python3", "--version") == ["wsl.exe", "-e", "python3", "--version"]

def test_host_profile_maps_windows_host_to_windows_wsl_backend() -> None:
    profile = host_profile_from_platform(HostPlatform(os_name="windows", has_wsl=True, is_wsl=False))

    assert profile.os_name == "windows"
    assert profile.linux_backend == "windows-wsl"
    assert profile.supports_docker is True

def test_host_profile_maps_wsl_linux_to_linux_native_backend() -> None:
    profile = host_profile_from_platform(HostPlatform(os_name="linux", has_wsl=True, is_wsl=True))

    assert profile.os_name == "linux"
    assert profile.linux_backend == "linux-native"
    assert profile.is_wsl is True

def test_repo_root_normalization_keeps_windows_drive_path_on_windows_host() -> None:
    normalized = normalize_repo_root_for_current_host(
        "C:/repos/agentplane",
        host_platform=HostPlatform(os_name="windows", has_wsl=True, is_wsl=False),
    )

    assert str(normalized).replace("\\", "/") == "C:/repos/agentplane"

def test_windows_path_to_wsl_posix_maps_drive_path_to_mnt_mount() -> None:
    assert windows_path_to_wsl_posix("C:/repos/agentplane") == "/mnt/c/repos/agentplane"
