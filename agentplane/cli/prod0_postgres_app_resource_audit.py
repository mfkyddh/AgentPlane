from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, unquote

from agentplane.cli.remote import execute_remote_bash

_PG_RUNTIME_DATABASE_KEYS = (
    "DATABASE_DBNAME",
    "DATABASE_NAME",
    "DATABASE_DB",
    "DB_DATABASE",
    "DB_NAME",
    "POSTGRES_DB",
    "PGDATABASE",
)
_PG_RUNTIME_USER_KEYS = (
    "DATABASE_USER",
    "DATABASE_USERNAME",
    "DB_USER",
    "DB_USERNAME",
    "POSTGRES_USER",
    "PGUSER",
)
_PG_RUNTIME_DSN_KEYS = (
    "DATABASE_URL",
    "SQL_DSN",
    "POSTGRES_URL",
    "POSTGRES_DSN",
    "DB_URL",
    "DB_DSN",
    "DATABASE_DSN",
)


def _env_value(values: Any, keys: tuple[str, ...]) -> str | None:
    if not isinstance(values, dict):
        return None
    for key in keys:
        value = values.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _pg_binding_from_dsn(value: str) -> tuple[str | None, str | None]:
    parsed = urlparse(value)
    database = parsed.path.lstrip("/") or None
    user = unquote(parsed.username) if parsed.username else None
    return database, user


def _live_runtime_binding(runtime: Any) -> tuple[str | None, str | None]:
    if not isinstance(runtime, dict):
        return None, None

    runtime_env = runtime.get("env")
    database = _env_value(runtime_env, _PG_RUNTIME_DATABASE_KEYS)
    user = _env_value(runtime_env, _PG_RUNTIME_USER_KEYS)

    if database is None or user is None:
        dsn = _env_value(runtime_env, _PG_RUNTIME_DSN_KEYS)
        if dsn is not None:
            dsn_database, dsn_user = _pg_binding_from_dsn(dsn)
            if database is None:
                database = dsn_database
            if user is None:
                user = dsn_user

    if database is None:
        value = runtime.get("database")
        if isinstance(value, str) and value:
            database = value
    if user is None:
        value = runtime.get("user")
        if isinstance(value, str) and value:
            user = value
    return database, user


def _prod0_app_resource_live_audit_snapshot(repo_root: Path) -> dict[str, Any]:
    audit_script = repo_root / "agentplane" / "scripts" / "remote" / "prod0-postgres-app-resource-live-audit.sh"
    try:
        payload = execute_remote_bash(
            repo_root=repo_root,
            target="prod0-main",
            script_file=audit_script,
        )
    except (ValueError, OSError) as exc:
        raise RuntimeError(str(exc)) from exc
    result = payload["result"]
    returncode = result["returncode"]
    stdout = result["stdout"]
    if returncode != 0:
        raise RuntimeError(json.dumps(payload, ensure_ascii=False, indent=2))
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("prod0 app resource live audit stdout must be a JSON object") from exc
    if not isinstance(payload, dict):
        raise ValueError("prod0 app resource live audit stdout must be a JSON object")
    return payload
