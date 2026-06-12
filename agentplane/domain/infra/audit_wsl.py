from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentplane.domain.infra.audit_common import _WSL_HOST_AUDIT_SCRIPT, _violation
from agentplane.runtime.backends import build_backend_runner
from agentplane.runtime.execution import CommandSpec
from agentplane.runtime.host_profile import HostProfile, detect_host_profile
from agentplane.runtime.target_resolver import TargetResolver


def _audit_wsl_templates(repo_root: Path) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    compose_root = repo_root / "infra" / "compose"
    if not compose_root.is_dir():
        return violations
    expected_targets = _wsl_required_compose_targets(repo_root)

    for service_dir in sorted(path for path in compose_root.iterdir() if path.is_dir()):
        service_name = service_dir.name
        legacy_compose = service_dir / "docker-compose.yml"
        legacy_env = service_dir / ".env"
        required_wsl = service_dir / "docker-compose.wsl.yml"
        required_prod0 = service_dir / "docker-compose.prod0.yml"

        if legacy_compose.exists():
            violations.append(
                _violation(
                    "wsl",
                    "wsl.legacy.compose_entrypoint",
                    "发现 legacy docker-compose.yml；仓库规范要求使用 docker-compose.wsl.yml 与 docker-compose.prod0.yml。",
                    path=legacy_compose,
                )
            )
        if legacy_env.exists():
            violations.append(
                _violation(
                    "wsl",
                    "wsl.legacy.env_file",
                    "发现 legacy .env；仓库规范要求使用环境专用文件（如 .env.wsl / .env.prod0）。",
                    path=legacy_env,
                )
            )
        for private_env in sorted(service_dir.glob(".env.*")):
            if private_env.name.endswith(".example"):
                continue
            violations.append(
                _violation(
                    "wsl",
                    "wsl.compose.private_env_file",
                    "发现 compose 目录内的环境专用私有 env 文件；仓库规范要求将其收口到 secrets/services/。",
                    path=private_env,
                )
            )
        if service_name in expected_targets["wsl"] and not required_wsl.exists():
            violations.append(
                _violation(
                    "wsl",
                    "wsl.missing.compose_wsl",
                    "缺少 docker-compose.wsl.yml。",
                    path=required_wsl,
                )
            )
        if service_name in expected_targets["prod0-main"] and not required_prod0.exists():
            violations.append(
                _violation(
                    "wsl",
                    "wsl.missing.compose_prod0",
                    "缺少 docker-compose.prod0.yml。",
                    path=required_prod0,
                )
            )
    return violations


def _inventory_compose_service_names(inventory_file: Path, *, target: str) -> set[str]:
    if not inventory_file.exists():
        return set()
    try:
        payload = json.loads(inventory_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return set()
    services = payload.get("services")
    if not isinstance(services, dict):
        return set()

    names: set[str] = set()
    for service_name, service_payload in services.items():
        if not isinstance(service_name, str) or not isinstance(service_payload, dict):
            continue
        if target == "wsl":
            names.add(service_name)
            continue
        if service_payload.get("control_plane") == "compose":
            names.add(service_name)
    return names


def _wsl_required_compose_targets(repo_root: Path) -> dict[str, set[str]]:
    return {
        "wsl": _inventory_compose_service_names(
            repo_root / "inventory" / "servers" / "wsl" / "inventory.json",
            target="wsl",
        ),
        "prod0-main": _inventory_compose_service_names(
            repo_root / "inventory" / "servers" / "prod0-main" / "inventory.json",
            target="prod0-main",
        ),
    }


def _host_path_exists(path: Path) -> bool:
    try:
        return path.exists()
    except OSError:
        return False


def _host_path_is_symlink(path: Path) -> bool:
    try:
        return path.is_symlink()
    except OSError:
        return False


def _audit_wsl_host_state(repo_root: Path | None = None) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    resolved_repo_root = (repo_root or Path.cwd()).resolve(strict=False)
    forbidden_paths = (
        Path("/root/.cli-proxy-api"),
        Path("/root/8443-cutover"),
        Path("/tmp/1panel-src"),
    )
    for path in forbidden_paths:
        if _host_path_exists(path):
            violations.append(
                _violation(
                    "wsl",
                    "wsl.host.legacy_path",
                    "发现应已清理的 WSL legacy 运行态目录。",
                    path=path,
                )
            )

    expected_symlinks = {
        Path("/root/.ssh/config"): resolved_repo_root / "secrets" / "ssh" / "config",
        Path("/root/.openclaw"): Path("/data/openclaw/config/home"),
        Path("/root/.local/share/openclaw-feishu-uat"): Path("/data/openclaw/config/openclaw-feishu-uat"),
    }
    for path, expected_target in expected_symlinks.items():
        path_exists = _host_path_exists(path)
        path_is_symlink = _host_path_is_symlink(path)
        if path_exists and not path_is_symlink:
            violations.append(
                _violation(
                    "wsl",
                    "wsl.host.expected_symlink",
                    "发现应为符号链接的治理路径仍为实体文件或目录。",
                    path=path,
                    details={"expected_target": str(expected_target)},
                )
            )
        elif path_is_symlink:
            actual_target = path.resolve(strict=False)
            if actual_target != expected_target:
                violations.append(
                    _violation(
                        "wsl",
                        "wsl.host.symlink_target",
                        "治理路径的符号链接目标不符合规范。",
                        path=path,
                        details={"expected_target": str(expected_target), "actual_target": str(actual_target)},
                    )
                )

    for path in (
        Path("/data/openclaw/config/home"),
        Path("/data/openclaw/config/openclaw-feishu-uat"),
    ):
        if not _host_path_exists(path):
            violations.append(
                _violation(
                    "wsl",
                    "wsl.host.required_data_path",
                    "缺少规范要求的 /data 持久化目录。",
                    path=path,
                )
            )
    return violations


def _wsl_backend_type(host_profile: HostProfile | None = None) -> str:
    profile = host_profile or detect_host_profile()
    return str(TargetResolver(profile).resolve("wsl").execution_backend)


def _audit_wsl_host_state_via_backend(
    repo_root: Path,
    *,
    backend_type: str,
    runner: Any | None = None,
) -> list[dict[str, Any]]:
    effective_runner = runner or build_backend_runner()
    spec = CommandSpec(
        backend_type=backend_type,  # type: ignore[arg-type]
        argv=("python3", "-c", _WSL_HOST_AUDIT_SCRIPT),
        cwd=repo_root,
        expected_outputs=("violations-json",),
        capabilities=("python3",),
        timeout=300,
    )
    result = effective_runner.execute_spec(spec)
    if not result.ok:
        raise ValueError(result.stdout or result.stderr or "failed to audit wsl host state via backend runner")
    payload = json.loads(result.stdout)
    if not isinstance(payload, list):
        raise ValueError("wsl audit backend payload must be a list")
    return [item for item in payload if isinstance(item, dict)]
