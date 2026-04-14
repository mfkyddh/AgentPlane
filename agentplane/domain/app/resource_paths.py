from __future__ import annotations

from pathlib import Path

from agentplane.runtime.path_policy import assert_canonical_ref, is_canonical_ref
from agentplane.runtime.wsl_bridge import (
    is_windows_path,
    resolve_local_workspace,
    wsl_posix_to_unc,
)


_TARGET_CONTRACT_PATHS = {
    "wsl": Path("deploy/agentplane/contract.wsl.yaml"),
    "prod0-main": Path("deploy/agentplane/contract.yaml"),
    "prod2-main": Path("deploy/agentplane/contract.prod2.yaml"),
}


def git_common_root(repo_root: Path) -> Path | None:
    git_entry = repo_root / ".git"
    if git_entry.is_dir():
        return repo_root
    if not git_entry.is_file():
        return None
    content = git_entry.read_text(encoding="utf-8").strip()
    prefix = "gitdir:"
    if not content.startswith(prefix):
        return None
    git_dir = Path(content[len(prefix) :].strip())
    if not git_dir.is_absolute():
        git_dir = (repo_root / git_dir).resolve()
    if len(git_dir.parts) >= 3 and git_dir.parent.name == "worktrees" and git_dir.parent.parent.name == ".git":
        return git_dir.parents[2]
    return None


def secrets_root(repo_root: Path) -> Path:
    common_root = git_common_root(repo_root)
    if common_root is not None:
        common_secrets = common_root / "secrets"
        if common_secrets.exists():
            return common_secrets
    direct = repo_root / "secrets"
    if direct.exists():
        return direct
    return direct


def app_resource_secret_dir(repo_root: Path, target: str, app_id: str) -> Path:
    return secrets_root(repo_root) / "hosts" / target / "apps" / app_id / "resources"


def app_resource_secret_relative(target: str, app_id: str, kind: str) -> str:
    return f"secrets/hosts/{target}/apps/{app_id}/resources/{kind}.env"


def resolve_secret_file_path(repo_root: Path, secret_file: str) -> Path:
    candidate = Path(secret_file)
    if candidate.is_absolute():
        return candidate.resolve(strict=False)
    if candidate.parts and candidate.parts[0] == "secrets":
        return (secrets_root(repo_root) / Path(*candidate.parts[1:])).resolve(strict=False)
    return (repo_root / candidate).resolve(strict=False)


def canonical_app_repo_ref(app_id: str) -> str:
    return assert_canonical_ref(f"apps/{app_id}")


def canonical_contract_ref(app_id: str, target: str) -> str:
    if target not in _TARGET_CONTRACT_PATHS:
        raise ValueError(f"unsupported contract target: {target}")
    return assert_canonical_ref(f"apps/{app_id}/contracts/{target}")


def contract_relpath_for_target(target: str) -> str:
    try:
        return _TARGET_CONTRACT_PATHS[target].as_posix()
    except KeyError as exc:
        raise ValueError(f"unsupported contract target: {target}") from exc


def contract_ref_target(contract_ref: str) -> str | None:
    if not is_canonical_ref(contract_ref):
        return None
    parts = contract_ref.split("/")
    if len(parts) != 4 or parts[0] != "apps" or parts[2] != "contracts":
        return None
    target = parts[3]
    return target if target in _TARGET_CONTRACT_PATHS else None


def _append_candidate(candidates: list[Path], candidate: Path | None) -> None:
    if candidate is None:
        return
    if candidate not in candidates:
        candidates.append(candidate)


def _catalog_repo_candidates(workspace_control_root: Path, linux_backend_root: Path | None, *, repo_name: str) -> list[Path]:
    candidates: list[Path] = []
    _append_candidate(candidates, workspace_control_root.parent / repo_name)

    if linux_backend_root is not None:
        linux_sibling = linux_backend_root.parent / repo_name
        if is_windows_path(workspace_control_root):
            unc_candidate = wsl_posix_to_unc(linux_sibling)
            _append_candidate(candidates, Path(unc_candidate) if unc_candidate else None)
        else:
            _append_candidate(candidates, linux_sibling)

    legacy_posix_candidate = Path("/root/work") / repo_name
    if is_windows_path(workspace_control_root):
        unc_candidate = wsl_posix_to_unc(legacy_posix_candidate)
        _append_candidate(candidates, Path(unc_candidate) if unc_candidate else None)
    else:
        _append_candidate(candidates, legacy_posix_candidate)

    return candidates


def resolve_catalog_repo_root(repo_root: Path, *, repo_name: str) -> Path:
    repo_root = Path(repo_root)
    workspace = resolve_local_workspace(repo_root)
    candidates = _catalog_repo_candidates(
        Path(workspace.control_root),
        Path(workspace.linux_backend_root) if workspace.linux_backend_root is not None else None,
        repo_name=repo_name,
    )

    for candidate in candidates:
        try:
            exists = candidate.exists()
        except OSError:
            exists = False
        if exists:
            return candidate.resolve(strict=False)
    return candidates[0].resolve(strict=False) if candidates else (repo_root.parent / repo_name).resolve(strict=False)
