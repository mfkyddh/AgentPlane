from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from agentplane.cli.secrets import copy_template_file, summarize_secret_file
from agentplane.runtime.bootstrap import (
    bootstrap_directory_specs,
    bootstrap_doctor_payload,
    bootstrap_template_specs,
    inspect_local_bootstrap,
)
from agentplane.runtime.wsl_bridge import normalize_repo_root_for_current_host


def add_bootstrap_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    bootstrap_parser = subparsers.add_parser("bootstrap", help="模板仓库 bootstrap 入口")
    bootstrap_subparsers = bootstrap_parser.add_subparsers(dest="bootstrap_action", required=True)

    for action in ("inspect-local", "init-secrets", "verify-secrets", "doctor"):
        parser = bootstrap_subparsers.add_parser(action, help=f"{action} bootstrap flow")
        parser.add_argument("--repo-root", default=".", help="AgentPlane 仓库根目录")


def _wrap(action: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {"command": "bootstrap", "action": action, "payload": payload}


def _normalize_repo_root(path: Path | str) -> Path:
    return normalize_repo_root_for_current_host(path)


def _init_secrets(repo_root: Path) -> dict[str, Any]:
    scaffold_dirs: set[str] = set()
    files: list[dict[str, Any]] = []

    for item in bootstrap_directory_specs(repo_root):
        destination = Path(item["destination"])
        scaffold_dirs.add(str(destination.parent))
        target = item.get("target")
        transform = None
        if isinstance(target, str):
            transform = lambda text, target=target: text.replace("<target>", target)
        files.append(
            copy_template_file(
                Path(item["template"]),
                destination,
                transform=transform,
            )
        )

    ssh_keys_dir = repo_root / "secrets" / "ssh" / "keys"
    ssh_keys_dir.mkdir(parents=True, exist_ok=True)
    scaffold_dirs.add(str(ssh_keys_dir))

    for item in bootstrap_template_specs(repo_root):
        destination = Path(item["destination"])
        scaffold_dirs.add(str(destination.parent))
        files.append(copy_template_file(Path(item["template"]), destination))

    return {
        "ok": True,
        "repo_root": str(repo_root),
        "directories": sorted(scaffold_dirs),
        "files": files,
    }


def _verify_secrets(repo_root: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    for item in bootstrap_template_specs(repo_root):
        status = summarize_secret_file(
            Path(item["destination"]),
            placeholder_markers=tuple(item["placeholder_markers"]),
            required_fragments=tuple(item["required_fragments"]),
        )
        status["secret_ref"] = item["secret_ref"]
        checks.append(status)
    return {
        "ok": all(item["ok"] for item in checks),
        "repo_root": str(repo_root),
        "checks": checks,
    }


def handle_bootstrap_command(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = _normalize_repo_root(getattr(args, "repo_root", "."))

    if args.bootstrap_action == "inspect-local":
        return _wrap("inspect-local", inspect_local_bootstrap(repo_root))
    if args.bootstrap_action == "init-secrets":
        return _wrap("init-secrets", _init_secrets(repo_root))
    if args.bootstrap_action == "verify-secrets":
        return _wrap("verify-secrets", _verify_secrets(repo_root))
    if args.bootstrap_action == "doctor":
        return _wrap("doctor", bootstrap_doctor_payload(repo_root, secrets_status=_verify_secrets(repo_root)))
    raise ValueError(f"Unsupported bootstrap action: {args.bootstrap_action}")
