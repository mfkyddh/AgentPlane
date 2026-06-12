from __future__ import annotations

import json
from pathlib import Path
from typing import Any

LEGACY_PORTS = {2053, 2054}
REQUIRED_NETWORK = "zqf_network"
SUPPORTED_AUDIT_ENVS = ("wsl", "prod0-main")
RUNTIME_SERVICE_CONTROL_PLANES = {"compose", "onepanel-app", "onepanel-compose"}
FORBIDDEN_PROD0_MARKERS = (
    "nginx-ui",
    "nginxwebui",
    "/data/apps/nginx-ui-official",
    "/usr/local/sbin/renew_example_net_cert.sh",
    "2053",
    "2054",
)
LEGACY_FLAT_SECRET_FILES = (
    "secrets/services/postgres.env",
    "secrets/services/redis.conf",
    "secrets/services/minio.env",
)
_WSL_HOST_AUDIT_SCRIPT = """
import json
import pathlib
import sys

repo_root = pathlib.Path.cwd()
sys.path.insert(0, str(repo_root))
from agentplane.domain.infra.audit_wsl import _audit_wsl_host_state

print(json.dumps(_audit_wsl_host_state(), ensure_ascii=False))
""".strip()


class _TrackedJsonObject(dict):
    duplicate_keys: set[str]


def _violation(
    scope: str,
    rule_id: str,
    message: str,
    *,
    path: Path | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "scope": scope,
        "id": rule_id,
        "severity": "error",
        "message": message,
    }
    if path is not None:
        item["path"] = str(path)
    if details:
        item["details"] = details
    return item


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def _sub2api_inventory_entry(services: dict[str, Any]) -> dict[str, Any]:
    modern = services.get("sub2api")
    if isinstance(modern, dict) and modern:
        return modern
    legacy = services.get("token_backend")
    if isinstance(legacy, dict):
        return legacy
    return {}


def _load_json(path: Path, scope: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if not path.exists():
        return None, _violation(scope, f"{scope}.inventory.missing", f"缺少 {scope} inventory.json。", path=path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, _violation(
            scope,
            f"{scope}.inventory.invalid_json",
            f"{scope} inventory.json 不是合法 JSON。",
            path=path,
            details={"error": str(exc)},
        )
    if not isinstance(payload, dict):
        return None, _violation(
            scope,
            f"{scope}.inventory.invalid_shape",
            f"{scope} inventory.json 顶层必须是对象。",
            path=path,
        )
    return payload, None
