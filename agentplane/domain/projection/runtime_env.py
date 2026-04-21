from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import quote

from agentplane.cli.app_resource_state import (
    APP_RESOURCE_SUMMARY_FIELDS,
    FORMAL_PROD0_REDIS_REGISTRY,
    app_resource_secret_dir,
    is_canonical_redis_db,
    load_env_file,
    load_registry,
    normalize_key_prefix,
    parse_env_text,
    registry_secret_file,
    validate_secret_files,
)
from agentplane.domain.app.resource_paths import app_resource_secret_relative, secrets_root
from agentplane.runtime.redaction import redact_env_text


SUPPORTED_RUNTIME_ENV_TARGETS = ("wsl", "prod0-main", "prod2-main")
FORMAL_PROD0_APP_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "newapi": ("postgres", "redis", "minio"),
    "sub2api": ("postgres", "redis", "minio"),
    "sub2apipay": ("postgres",),
}
APP_RESOURCES_REGISTRY_ENTRY_LABEL = "app-resources registry entry"


def service_env_file(repo_root: Path, target: str, app_id: str) -> Path:
    resolved_secrets_root = secrets_root(repo_root)
    if target == "wsl":
        return resolved_secrets_root / "services" / f"{app_id}.wsl.env"
    if target == "prod0-main":
        return resolved_secrets_root / "services" / f"{app_id}.prod0.env"
    if target == "prod2-main":
        return resolved_secrets_root / "services" / f"{app_id}.prod2.env"
    raise ValueError(f"Unsupported target for env projection: {target}")


def _pg_url(pg_env: dict[str, str]) -> str:
    user = quote(pg_env.get("PGUSER", ""), safe="")
    password = quote(pg_env.get("PGPASSWORD", ""), safe="")
    return (
        f"postgres://{user}:{password}"
        f"@{pg_env.get('PGHOST', '')}:{pg_env.get('PGPORT', '')}/{pg_env.get('PGDATABASE', '')}"
    )


def _redis_url(redis_env: dict[str, str]) -> str:
    scheme = "rediss" if redis_env.get("REDIS_ENABLE_TLS", "").strip().lower() == "true" else "redis"
    password = quote(redis_env.get("REDIS_PASSWORD", ""), safe="")
    username = quote(redis_env.get("REDIS_USER", ""), safe="")
    userinfo = f"{username}:{password}" if username else f":{password}"
    return f"{scheme}://{userinfo}@{redis_env.get('REDIS_HOST', '')}:{redis_env.get('REDIS_PORT', '')}/{redis_env.get('REDIS_DB', '')}"


def _shared_runtime_redis_env(repo_root: Path, target: str, redis_env: dict[str, str]) -> dict[str, str]:
    if target != "prod0-main":
        return redis_env
    admin_conf = secrets_root(repo_root) / "services" / "redis" / "admin.prod0.conf"
    if not admin_conf.is_file():
        return redis_env

    shared_password = ""
    for raw_line in admin_conf.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("requirepass "):
            shared_password = line.split(None, 1)[1].strip()
            break
    if not shared_password:
        return redis_env

    projected = dict(redis_env)
    projected.pop("REDIS_USER", None)
    projected["REDIS_PASSWORD"] = shared_password
    return projected


def _newapi_sql_dsn(pg_env: dict[str, str]) -> str:
    sslmode = pg_env.get("PGSSLMODE") or "disable"
    user = quote(pg_env.get("PGUSER", ""), safe="")
    password = quote(pg_env.get("PGPASSWORD", ""), safe="")
    return (
        f"postgresql://{user}:{password}"
        f"@{pg_env.get('PGHOST', '')}:{pg_env.get('PGPORT', '')}/{pg_env.get('PGDATABASE', '')}"
        f"?sslmode={sslmode}"
    )


def _merge_sub2api_env(current: dict[str, str], pg_env: dict[str, str], redis_env: dict[str, str]) -> tuple[dict[str, str], set[str]]:
    managed = {
        "DATABASE_HOST": pg_env.get("PGHOST", ""),
        "DATABASE_PORT": pg_env.get("PGPORT", ""),
        "DATABASE_USER": pg_env.get("PGUSER", ""),
        "DATABASE_PASSWORD": pg_env.get("PGPASSWORD", ""),
        "DATABASE_DBNAME": pg_env.get("PGDATABASE", ""),
        "DATABASE_SSLMODE": pg_env.get("PGSSLMODE", ""),
        "REDIS_HOST": redis_env.get("REDIS_HOST", ""),
        "REDIS_PORT": redis_env.get("REDIS_PORT", ""),
        "REDIS_PASSWORD": redis_env.get("REDIS_PASSWORD", ""),
        "REDIS_DB": redis_env.get("REDIS_DB", ""),
        "REDIS_ENABLE_TLS": redis_env.get("REDIS_ENABLE_TLS", ""),
    }
    merged = {key: value for key, value in current.items() if key not in {"REDIS_USER", "REDIS_KEY_PREFIX"}}
    for key, value in managed.items():
        if value != "":
            merged[key] = value
    return merged, set(managed.keys())


def _merge_newapi_env(current: dict[str, str], pg_env: dict[str, str], redis_env: dict[str, str]) -> tuple[dict[str, str], set[str]]:
    managed = {
        "SQL_DSN": _newapi_sql_dsn(pg_env),
        "REDIS_CONN_STRING": _redis_url(redis_env),
        "DATABASE_URL": _pg_url(pg_env),
        "REDIS_URL": _redis_url(redis_env),
    }
    merged = {key: value for key, value in current.items() if key not in {"REDIS_USER", "REDIS_KEY_PREFIX"}}
    for key, value in managed.items():
        if value:
            merged[key] = value
    return merged, set(managed.keys())


def _format_env_text(values: dict[str, str], preferred_order: list[str]) -> str:
    ordered_keys: list[str] = []
    seen: set[str] = set()
    for key in preferred_order:
        if key in values and key not in seen:
            ordered_keys.append(key)
            seen.add(key)
    for key in sorted(values):
        if key not in seen:
            ordered_keys.append(key)
            seen.add(key)
    return "\n".join(f"{key}={values[key]}" for key in ordered_keys) + "\n"


def formal_prod0_required_kinds(app_id: str) -> tuple[str, ...]:
    return FORMAL_PROD0_APP_REQUIREMENTS.get(app_id, ())


def _render_env_formal_required_kinds(app_id: str) -> tuple[str, ...]:
    return tuple(kind for kind in formal_prod0_required_kinds(app_id) if kind in {"postgres", "redis"})


def formal_registry_entry_errors(
    target: str,
    app_id: str,
    raw_entry: Any,
    *,
    required_kinds: tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    if target != "prod0-main":
        return []

    formal_required = formal_prod0_required_kinds(app_id)
    if not formal_required:
        return []
    checked_kinds = formal_required if required_kinds is None else required_kinds

    issues: list[str] = []
    if not isinstance(raw_entry, dict):
        issues.append("missing registry entry")
    else:
        owner_app = raw_entry.get("owner_app")
        if owner_app != app_id:
            issues.append(f"owner_app={owner_app!r} expected {app_id!r}")

        redis_contract = FORMAL_PROD0_REDIS_REGISTRY.get(app_id, {})
        for kind in checked_kinds:
            fields = APP_RESOURCE_SUMMARY_FIELDS[kind]
            spec = raw_entry.get(kind)
            if not isinstance(spec, dict):
                issues.append(f"{APP_RESOURCES_REGISTRY_ENTRY_LABEL} missing {kind} specification")
                continue
            for field in fields:
                value = spec.get(field)
                if value is None or value == "":
                    issues.append(
                        f"{APP_RESOURCES_REGISTRY_ENTRY_LABEL} summary field {kind}.{field} missing"
                    )
            if kind == "redis":
                redis_db = spec.get("db")
                expected_db = redis_contract.get("db")
                if expected_db is not None and (
                    not is_canonical_redis_db(redis_db) or redis_db != expected_db
                ):
                    issues.append(f"redis.db={redis_db!r} expected {expected_db!r}")

                key_prefix = spec.get("key_prefix")
                normalized_key_prefix = normalize_key_prefix(key_prefix)
                expected_key_prefix = redis_contract.get("key_prefix")
                if expected_key_prefix is not None and (
                    key_prefix != expected_key_prefix or normalized_key_prefix != expected_key_prefix
                ):
                    issues.append(f"redis.key_prefix={key_prefix!r} expected {expected_key_prefix!r}")
            expected_secret_file = app_resource_secret_relative(target, app_id, kind)
            actual_secret_file = registry_secret_file(raw_entry, kind)
            if actual_secret_file != expected_secret_file:
                issues.append(f"{kind}.secret_file={actual_secret_file!r} expected {expected_secret_file!r}")

    if not issues:
        return []
    return [
        {
            "id": "app.resource.registry_entry_incomplete",
            "app": app_id,
            "issues": issues,
            "message": f"formal {APP_RESOURCES_REGISTRY_ENTRY_LABEL} must be complete and internally consistent",
        }
    ]


def render_env_validation_errors(repo_root: Path, target: str, app_id: str, entry: dict[str, Any]) -> list[dict[str, Any]]:
    formal_errors = formal_registry_entry_errors(
        target,
        app_id,
        entry,
        required_kinds=_render_env_formal_required_kinds(app_id),
    )
    if formal_errors:
        return formal_errors
    return validate_secret_files(repo_root, target, app_id, entry)


def _projection_state(repo_root: Path, target: str, app_id: str) -> dict[str, Any]:
    registry_path, registry = load_registry(repo_root, target)
    env_file = service_env_file(repo_root, target, app_id)
    payload: dict[str, Any] = {
        "registry_file": str(registry_path),
        "target": target,
        "app": app_id,
        "env_file": str(env_file),
        "written": False,
    }

    if app_id not in registry:
        payload["ok"] = False
        payload["error"] = {"id": "app.resource.registry_missing_app", "app": app_id}
        return payload

    raw_entry = registry.get(app_id)
    if not isinstance(raw_entry, dict):
        payload["ok"] = False
        payload["errors"] = [
            {
                "id": "app.resource.registry_invalid_app_entry",
                "app": app_id,
                "message": "app-resources registry entry must be an object",
            }
        ]
        return payload

    validation_errors = render_env_validation_errors(repo_root, target, app_id, raw_entry)
    if validation_errors:
        payload["ok"] = False
        payload["errors"] = validation_errors
        return payload

    secret_root = app_resource_secret_dir(repo_root, target, app_id)
    formal_required = formal_prod0_required_kinds(app_id) if target == "prod0-main" else ()
    pg_env = load_env_file(secret_root / "postgres.env") if "postgres" in formal_required or app_id in {"sub2api", "newapi"} else {}
    redis_env = load_env_file(secret_root / "redis.env") if "redis" in formal_required or app_id in {"sub2api", "newapi"} else {}
    redis_runtime_env = _shared_runtime_redis_env(repo_root, target, redis_env)

    current_text = env_file.read_text(encoding="utf-8") if env_file.exists() else ""
    current_values = parse_env_text(current_text)
    preferred_order = list(current_values.keys())

    if app_id == "sub2api":
        merged, managed_keys = _merge_sub2api_env(current_values, pg_env, redis_runtime_env)
    elif app_id == "newapi":
        merged, managed_keys = _merge_newapi_env(current_values, pg_env, redis_runtime_env)
    else:
        merged = dict(current_values)
        managed_keys = set()

    rendered = _format_env_text(merged, preferred_order)
    payload.update(
        {
            "ok": True,
            "managed_keys": sorted(managed_keys),
            "rendered_env": rendered,
            "current_env": current_text,
            "env_exists": env_file.exists(),
            "changed": current_text != rendered,
        }
    )
    return payload


def _redact_drift_payload(drift: dict[str, Any]) -> dict[str, Any]:
    redacted = dict(drift)
    expected = redacted.pop("expected", None)
    actual = redacted.pop("actual", None)
    if isinstance(expected, str):
        redacted["expected_redacted"] = redact_env_text(expected)
    if isinstance(actual, str):
        redacted["actual_redacted"] = redact_env_text(actual)
    return redacted


def _public_projection_payload(payload: dict[str, Any], *, reveal_secrets: bool = False) -> dict[str, Any]:
    public = dict(payload)
    public.pop("env_exists", None)
    if not reveal_secrets:
        public.pop("current_env", None)
        public.pop("rendered_env", None)
        drift = public.get("drift")
        if isinstance(drift, dict):
            public["drift"] = _redact_drift_payload(drift)
    return public


def plan_runtime_env_projection(repo_root: Path, target: str, app_id: str, *, reveal_secrets: bool = False) -> dict[str, Any]:
    return _public_projection_payload(_projection_state(repo_root.resolve(), target, app_id), reveal_secrets=reveal_secrets)


def apply_runtime_env_projection(repo_root: Path, target: str, app_id: str, *, reveal_secrets: bool = False) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    payload = _projection_state(repo_root, target, app_id)
    if not payload.get("ok"):
        return _public_projection_payload(payload, reveal_secrets=reveal_secrets)

    env_path = Path(payload["env_file"])
    if payload.get("changed"):
        env_path.parent.mkdir(parents=True, exist_ok=True)
        env_path.write_text(str(payload["rendered_env"]), encoding="utf-8")
        payload["written"] = True
    return _public_projection_payload(payload, reveal_secrets=reveal_secrets)


def verify_runtime_env_projection(repo_root: Path, target: str, app_id: str, *, reveal_secrets: bool = False) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    payload = _projection_state(repo_root, target, app_id)
    if not payload.get("ok"):
        return _public_projection_payload(payload, reveal_secrets=reveal_secrets)

    current_text = str(payload.get("current_env", ""))
    if not payload.get("env_exists"):
        payload["ok"] = False
        payload["error"] = {
            "id": "projection.runtime_env_missing",
            "message": "runtime env file is missing",
        }
        return _public_projection_payload(payload, reveal_secrets=reveal_secrets)

    if payload.get("changed"):
        payload["ok"] = False
        payload["error"] = {
            "id": "projection.runtime_env_drift",
            "message": "runtime env file differs from projected managed content",
        }
        payload["drift"] = {
            "managed_keys": list(payload.get("managed_keys", [])),
            "expected": str(payload.get("rendered_env", "")),
            "actual": current_text,
        }
        return _public_projection_payload(payload, reveal_secrets=reveal_secrets)

    return _public_projection_payload(payload, reveal_secrets=reveal_secrets)
