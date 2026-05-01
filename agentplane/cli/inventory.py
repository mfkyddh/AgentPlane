from __future__ import annotations

import json
import os
import platform
import socket
import subprocess
from pathlib import Path
from typing import Any

from agentplane.runtime.backends import build_backend_runner
from agentplane.runtime.execution import ExecutionBindings, ExecutionPlan
from agentplane.runtime.host_profile import HostProfile, detect_host_profile
from agentplane.runtime.target_resolver import TargetResolver

SUPPORTED_INVENTORY_TARGETS = ("wsl", "prod0-main")
_WSL_SNAPSHOT_SCRIPT = """
import json
import pathlib
import sys

repo_root = pathlib.Path.cwd()
sys.path.insert(0, str(repo_root))
from agentplane.cli.inventory import _wsl_snapshot

print(json.dumps(_wsl_snapshot(repo_root), ensure_ascii=False))
""".strip()


def _run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, capture_output=True, check=False)


def _docker_container_rows() -> list[dict[str, Any]]:
    result = _run_command(
        [
            "docker",
            "ps",
            "--format",
            '{{.Names}}|{{.Image}}|{{.Ports}}|{{.Status}}|{{.Label "com.docker.compose.project.config_files"}}',
        ]
    )
    if result.returncode != 0:
        return []
    rows: list[dict[str, Any]] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        name, image, ports, status, config_files = (line.split("|", 4) + ["", "", "", "", ""])[:5]
        rows.append(
            {
                "name": name,
                "image": image,
                "ports": ports,
                "status": status,
                "labels": {
                    "com.docker.compose.project.config_files": config_files,
                },
            }
        )
    return rows


def _symlink_state(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "is_symlink": path.is_symlink(),
        "target": str(path.resolve(strict=False)) if path.is_symlink() else None,
    }


def _wsl_inventory_file(repo_root: Path) -> Path:
    return repo_root / "inventory" / "servers" / "wsl" / "inventory.json"


def _prod0_inventory_file(repo_root: Path) -> Path:
    return repo_root / "inventory" / "servers" / "prod0-main" / "inventory.json"


def _load_existing_wsl_metadata(repo_root: Path) -> dict[str, Any]:
    inventory_file = _wsl_inventory_file(repo_root)
    if not inventory_file.exists():
        return {}
    try:
        payload = json.loads(inventory_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    metadata: dict[str, Any] = {}
    if isinstance(payload.get("automations"), list):
        metadata["automations"] = payload["automations"]
    services = payload.get("services")
    if isinstance(services, dict):
        metadata["services"] = services
    object_ledgers = payload.get("object_ledgers")
    if isinstance(object_ledgers, dict):
        metadata["object_ledgers"] = object_ledgers
    resource_ledgers = payload.get("resource_ledgers")
    if isinstance(resource_ledgers, dict):
        metadata["resource_ledgers"] = resource_ledgers
    host_truth = payload.get("host_truth")
    if isinstance(host_truth, dict):
        metadata["host_truth"] = host_truth
    return metadata


def _normalize_compose_label_paths(value: Any) -> set[str]:
    if not isinstance(value, str):
        return set()
    return {item.strip() for item in value.split(",") if item.strip()}


def _strip_container_labels(row: dict[str, Any]) -> dict[str, str]:
    return {
        "name": str(row.get("name", "")),
        "image": str(row.get("image", "")),
        "ports": str(row.get("ports", "")),
        "status": str(row.get("status", "")),
    }


def _wsl_snapshot(repo_root: Path) -> dict[str, Any]:
    compose_root = repo_root / "infra" / "compose"
    services = sorted(path.name for path in compose_root.iterdir() if path.is_dir()) if compose_root.is_dir() else []
    managed_compose_files = {str(path) for path in compose_root.glob("*/docker-compose*.yml")}
    managed_rows: list[dict[str, str]] = []
    unmanaged_rows: list[dict[str, str]] = []
    for row in _docker_container_rows():
        config_files = _normalize_compose_label_paths(
            row.get("labels", {}).get("com.docker.compose.project.config_files")
        )
        if config_files & managed_compose_files:
            managed_rows.append(_strip_container_labels(row))
        else:
            unmanaged_rows.append(_strip_container_labels(row))
    payload = {
        "label": "WSL 跳板机",
        "target": "wsl",
        "hostname": socket.gethostname(),
        "os": platform.platform(),
        "runtime_user": os.getenv("USER") or os.getenv("LOGNAME") or "unknown",
        "repo_root": str(repo_root),
        "compose_services": services,
        "docker_containers": managed_rows,
        "unmanaged_docker_containers": unmanaged_rows,
        "governance": {
            "secrets_root": "secrets/",
            "repo_tmp": str(repo_root / "tmp"),
            "ssh_config": _symlink_state(Path("/root/.ssh/config")),
            "openclaw_home": _symlink_state(Path("/root/.openclaw")),
            "openclaw_share": _symlink_state(Path("/root/.local/share/openclaw-feishu-uat")),
            "data_paths": {
                "openclaw_home": str(Path("/data/openclaw/config/home")),
                "openclaw_share": str(Path("/data/openclaw/config/openclaw-feishu-uat")),
            },
            "forbidden_paths_present": {
                "/root/.cli-proxy-api": Path("/root/.cli-proxy-api").exists(),
                "/root/8443-cutover": Path("/root/8443-cutover").exists(),
                "/tmp/1panel-src": Path("/tmp/1panel-src").exists(),
            },
        },
    }
    payload.update(_load_existing_wsl_metadata(repo_root))
    return payload


def _wsl_backend_type(host_profile: HostProfile | None = None) -> str:
    profile = host_profile or detect_host_profile()
    return str(TargetResolver(profile).resolve("wsl").execution_backend)


def _wsl_snapshot_via_backend(
    repo_root: Path,
    *,
    backend_type: str,
    runner: Any | None = None,
) -> dict[str, Any]:
    effective_runner = runner or build_backend_runner()
    plan = ExecutionPlan(
        backend_type=backend_type,  # type: ignore[arg-type]
        cwd_ref="workspace.control_root",
        argv=("python3", "-c", _WSL_SNAPSHOT_SCRIPT),
        env_refs=(),
        input_refs=(),
        expected_outputs=("snapshot-json",),
        capabilities=("python3",),
        timeout=300,
    )
    result = effective_runner.execute(
        plan,
        bindings=ExecutionBindings(
            cwd_values={"workspace.control_root": repo_root},
        ),
    )
    if not result.ok:
        raise ValueError(result.stdout or result.stderr or "failed to collect wsl inventory via backend runner")
    payload = json.loads(result.stdout)
    if not isinstance(payload, dict):
        raise ValueError("wsl inventory backend payload must be an object")
    return payload


def _tracked_wsl_snapshot(repo_root: Path) -> dict[str, Any]:
    payload = _load_json_file(_wsl_inventory_file(repo_root))
    payload.setdefault("label", "WSL 跳板机")
    payload.setdefault("target", "wsl")
    payload["collection_mode"] = "tracked-snapshot"
    payload["live_collection_required"] = (
        "Run from a separate Linux-filesystem checkout for live WSL inventory; "
        "Windows-mounted checkouts are not valid WSL working directories."
    )
    return payload


def _load_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"status": "missing", "inventory_file": str(path)}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"status": "invalid_json", "inventory_file": str(path), "error": str(exc)}
    payload.setdefault("inventory_file", str(path))
    payload.setdefault("status", "ok")
    return payload


def generate_inventory_snapshot(
    repo_root: Path,
    target: str,
    *,
    write: bool = False,
    host_profile: HostProfile | None = None,
    runner: Any | None = None,
) -> dict[str, Any]:
    resolved_root = repo_root.resolve()
    backend_type = None
    if target == "wsl":
        backend_type = _wsl_backend_type(host_profile)
        if backend_type == "windows-wsl" and runner is not None:
            payload = _wsl_snapshot_via_backend(resolved_root, backend_type=backend_type, runner=runner)
        elif backend_type == "windows-wsl":
            if write:
                raise ValueError(
                    "live WSL inventory write requires running from a separate Linux-filesystem checkout; "
                    "Windows-mounted checkouts are not valid WSL working directories."
                )
            payload = _tracked_wsl_snapshot(resolved_root)
        else:
            payload = _wsl_snapshot(resolved_root)
        inventory_file = _wsl_inventory_file(resolved_root)
    elif target == "prod0-main":
        inventory_file = _prod0_inventory_file(resolved_root)
        payload = _load_json_file(inventory_file)
    else:
        raise ValueError(f"Unsupported inventory target: {target}")

    if write:
        inventory_file.parent.mkdir(parents=True, exist_ok=True)
        inventory_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "command": "inventory",
        "target": target,
        "inventory_file": str(inventory_file),
        "payload": payload,
        "backend_type": backend_type,
    }
