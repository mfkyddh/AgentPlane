from pathlib import Path

from agentplane.runtime.workspace import resolve_workspace
from agentplane.runtime.workspace_path import WorkspacePath


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
