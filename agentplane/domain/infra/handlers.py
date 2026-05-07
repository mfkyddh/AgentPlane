from __future__ import annotations

from pathlib import Path
from typing import Any

from agentplane.domain.infra.secrets import copy_template_file
from agentplane.runtime.bootstrap import (
    bootstrap_directory_specs,
    bootstrap_doctor_payload,
    bootstrap_required_truth_specs,
    inspect_local_bootstrap,
    verify_bootstrap_truths,
)


def init_secrets(repo_root: Path) -> dict[str, Any]:
    scaffold_dirs: set[str] = set()
    files: list[dict[str, Any]] = []
    for item in bootstrap_directory_specs(repo_root):
        destination = Path(item["destination"])
        scaffold_dirs.add(str(destination.parent))
        target = item.get("target")
        transform = None
        if isinstance(target, str):
            def transform(text, target=target):
                return text.replace("<target>", target)
        files.append(copy_template_file(Path(item["template"]), destination, transform=transform))
    ssh_keys_dir = repo_root / "secrets" / "ssh" / "keys"
    ssh_keys_dir.mkdir(parents=True, exist_ok=True)
    scaffold_dirs.add(str(ssh_keys_dir))
    for item in bootstrap_required_truth_specs(repo_root):
        destination = Path(item["destination"])
        scaffold_dirs.add(str(destination.parent))
        files.append(copy_template_file(Path(item["template"]), destination))
    return {"ok": True, "repo_root": str(repo_root), "directories": sorted(scaffold_dirs), "files": files}


def run_inspect_local(repo_root: Path) -> dict[str, Any]:
    return inspect_local_bootstrap(repo_root)


def run_verify_secrets(repo_root: Path) -> dict[str, Any]:
    return verify_bootstrap_truths(repo_root)


def run_doctor(repo_root: Path) -> dict[str, Any]:
    return bootstrap_doctor_payload(repo_root, secrets_status=verify_bootstrap_truths(repo_root))
