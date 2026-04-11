from __future__ import annotations

from pathlib import Path


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
