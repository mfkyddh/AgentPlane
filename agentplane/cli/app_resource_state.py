from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentplane.domain.app.resource_paths import (
    app_resource_secret_dir,
    app_resource_secret_relative,
    resolve_secret_file_path,
    secrets_root,
)


APP_RESOURCE_ERROR_PREFIX = "app.resource"
ERROR_ID_REGISTRY_SECRET_FILE_SCOPE = f"{APP_RESOURCE_ERROR_PREFIX}.secret_file_scope"
ERROR_ID_SECRET_FILE_MISSING = f"{APP_RESOURCE_ERROR_PREFIX}.secret_file_missing"
ERROR_ID_REGISTRY_DUPLICATE_OWNERSHIP = f"{APP_RESOURCE_ERROR_PREFIX}.registry_duplicate_ownership"
ERROR_ID_REGISTRY_DUPLICATE_REDIS_COMBINATION = f"{APP_RESOURCE_ERROR_PREFIX}.registry_duplicate_redis_combination"
ERROR_ID_SECRET_FILE_INVALID = f"{APP_RESOURCE_ERROR_PREFIX}.secret_file_invalid"
APP_RESOURCE_SUMMARY_FIELDS: dict[str, tuple[str, ...]] = {
    "postgres": ("database", "user"),
    "redis": ("db", "key_prefix"),
    "minio": ("bucket", "access_key", "policy_name", "policy_scope", "isolation_level"),
}
FORMAL_PROD0_REDIS_REGISTRY: dict[str, dict[str, object]] = {
    "sub2api": {"db": 1, "key_prefix": "sub2api:"},
    "newapi": {"db": 2, "key_prefix": "newapi:"},
}
# `redis.user` is retained only as historical metadata in some inventories.
# The current prod0-main DB-isolation contract is `db` + canonical `key_prefix`.
HISTORICAL_REDIS_METADATA_FIELDS: tuple[str, ...] = ("user",)
PROD0_REDIS_ENV_REQUIRED_FIELDS: tuple[str, ...] = (
    "REDIS_HOST",
    "REDIS_PORT",
    "REDIS_PASSWORD",
    "REDIS_DB",
    "REDIS_KEY_PREFIX",
    "REDIS_ENABLE_TLS",
)


def registry_file(repo_root: Path, target: str) -> Path:
    return repo_root / "inventory" / "servers" / target / "app-resources.json"


def load_registry(repo_root: Path, target: str) -> tuple[Path, dict[str, Any]]:
    path = registry_file(repo_root, target)
    if not path.exists():
        raise FileNotFoundError(str(path))
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"app resource registry must be an object: {path}")
    return path, payload


def parse_env_text(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        values[key] = value.strip()
    return values


def build_app_resource_summary(app_resources: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(app_resources, dict):
        return {}

    summary: dict[str, dict[str, Any]] = {}
    for kind, fields in APP_RESOURCE_SUMMARY_FIELDS.items():
        resource_spec = app_resources.get(kind)
        if not isinstance(resource_spec, dict):
            continue
        kind_summary: dict[str, Any] = {}
        for field in fields:
            value = resource_spec.get(field)
            if value is None or value == "":
                continue
            kind_summary[field] = value
        secret_file = resource_spec.get("secret_file")
        if isinstance(secret_file, str) and secret_file.strip():
            kind_summary["secret_file"] = secret_file
        if kind_summary:
            summary[kind] = kind_summary
    return summary


def registry_secret_file(entry: dict[str, Any], kind: str) -> str | None:
    resource = entry.get(kind)
    if isinstance(resource, dict):
        direct = resource.get("secret_file")
        if isinstance(direct, str) and direct.strip():
            return direct

    secret_files = entry.get("secret_files")
    if not isinstance(secret_files, list):
        return None
    for item in secret_files:
        if not isinstance(item, str):
            continue
        if f"/{kind}." in item or item.endswith(f"/{kind}.env") or item.endswith(f"{kind}.env"):
            return item
    return None


def load_env_file(path: Path) -> dict[str, str]:
    return parse_env_text(path.read_text(encoding="utf-8"))


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def normalize_key_prefix(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    if not normalized.endswith(":"):
        normalized = f"{normalized}:"
    return normalized


def is_canonical_redis_db(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _missing_prod0_redis_env_fields(redis_env: dict[str, str]) -> list[str]:
    missing_fields: list[str] = []
    for field in PROD0_REDIS_ENV_REQUIRED_FIELDS:
        if field == "REDIS_KEY_PREFIX":
            if normalize_key_prefix(redis_env.get(field)) is None:
                missing_fields.append(field)
            continue

        value = redis_env.get(field)
        if value is None or value.strip() == "":
            missing_fields.append(field)
    return missing_fields


def _prod0_redis_registry_drift_issues(entry: dict[str, Any], redis_env: dict[str, str]) -> list[str]:
    redis = entry.get("redis")
    if not isinstance(redis, dict):
        return []

    issues: list[str] = []
    expected_db = redis.get("db")
    actual_db = redis_env.get("REDIS_DB")
    if expected_db is not None and actual_db not in {None, ""}:
        expected_db_text = str(expected_db)
        if actual_db != expected_db_text:
            issues.append(f"REDIS_DB={actual_db!r} expected {expected_db_text!r}")

    expected_key_prefix = normalize_key_prefix(redis.get("key_prefix"))
    actual_key_prefix = redis_env.get("REDIS_KEY_PREFIX")
    if expected_key_prefix is not None and actual_key_prefix not in {None, ""}:
        if actual_key_prefix != expected_key_prefix:
            issues.append(f"REDIS_KEY_PREFIX={actual_key_prefix!r} expected {expected_key_prefix!r}")

    return issues


def _error_id(prefix: str, suffix: str) -> str:
    return f"{prefix}.{suffix}"


def validate_secret_files(
    repo_root: Path,
    target: str,
    app_id: str,
    entry: dict[str, Any],
    *,
    error_prefix: str = APP_RESOURCE_ERROR_PREFIX,
) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    secret_files = entry.get("secret_files")
    if not isinstance(secret_files, list):
        return errors

    scoped_root = app_resource_secret_dir(repo_root, target, app_id).resolve(strict=False)
    for item in secret_files:
        if not isinstance(item, str) or not item.strip():
            continue
        normalized = resolve_secret_file_path(repo_root, item)
        if not _is_relative_to(normalized, scoped_root):
            errors.append(
                {
                    "id": _error_id(error_prefix, "secret_file_scope"),
                    "app": app_id,
                    "secret_file": item,
                    "message": "app resource registry secret_files must stay within secrets/hosts/<target>/apps/<app>/resources/",
                }
            )
            continue
        if not normalized.is_file():
            errors.append(
                {
                    "id": _error_id(error_prefix, "secret_file_missing"),
                    "app": app_id,
                    "secret_file": item,
                    "message": "app resource secret file is missing",
                }
            )
            continue
        if target == "prod0-main" and normalized.name == "redis.env":
            redis_env = load_env_file(normalized)
            missing_fields = _missing_prod0_redis_env_fields(redis_env)
            if missing_fields:
                errors.append(
                    {
                        "id": _error_id(error_prefix, "secret_file_invalid"),
                        "app": app_id,
                        "secret_file": item,
                        "fields": missing_fields,
                        "message": f"app resource redis secret is missing required fields: {', '.join(missing_fields)}",
                    }
                )
            else:
                drift_issues = _prod0_redis_registry_drift_issues(entry, redis_env)
                if drift_issues:
                    errors.append(
                        {
                            "id": _error_id(error_prefix, "secret_file_invalid"),
                            "app": app_id,
                            "secret_file": item,
                            "issues": drift_issues,
                            "message": "app resource redis secret disagrees with registry redis.db/key_prefix",
                        }
                    )
    return errors


@dataclass(frozen=True)
class _OwnershipKey:
    kind: str
    value: tuple[object, ...]


def validate_duplicate_ownership(
    registry: dict[str, Any],
    *,
    error_prefix: str = APP_RESOURCE_ERROR_PREFIX,
) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    seen: dict[_OwnershipKey, str] = {}
    for app_id, raw_entry in registry.items():
        if not isinstance(app_id, str) or not isinstance(raw_entry, dict):
            continue

        postgres = raw_entry.get("postgres")
        if isinstance(postgres, dict):
            key = _OwnershipKey("postgres", (postgres.get("database"), postgres.get("user")))
            if key.value != (None, None):
                owner = seen.get(key)
                if owner is None:
                    seen[key] = app_id
                elif owner != app_id:
                    errors.append(
                        {
                            "id": _error_id(error_prefix, "registry_duplicate_ownership"),
                            "kind": "postgres",
                            "owner_a": owner,
                            "owner_b": app_id,
                            "database": postgres.get("database"),
                            "user": postgres.get("user"),
                            "message": "duplicate postgres database/user ownership across apps",
                        }
                    )

        minio = raw_entry.get("minio")
        if isinstance(minio, dict):
            key = _OwnershipKey("minio", (minio.get("bucket"), minio.get("access_key")))
            if key.value != (None, None):
                owner = seen.get(key)
                if owner is None:
                    seen[key] = app_id
                elif owner != app_id:
                    errors.append(
                        {
                            "id": _error_id(error_prefix, "registry_duplicate_ownership"),
                            "kind": "minio",
                            "owner_a": owner,
                            "owner_b": app_id,
                            "bucket": minio.get("bucket"),
                            "access_key": minio.get("access_key"),
                            "message": "duplicate minio bucket/access_key ownership across apps",
                        }
                    )
    return errors


def validate_duplicate_redis_combination(
    registry: dict[str, Any],
    *,
    error_prefix: str = APP_RESOURCE_ERROR_PREFIX,
) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    seen_db: dict[object, str] = {}
    seen_key_prefix: dict[str, str] = {}
    for app_id, raw_entry in registry.items():
        if not isinstance(app_id, str) or not isinstance(raw_entry, dict):
            continue
        redis = raw_entry.get("redis")
        if not isinstance(redis, dict):
            continue

        db = redis.get("db")
        if db is not None:
            owner = seen_db.get(db)
            if owner is None:
                seen_db[db] = app_id
            elif owner != app_id:
                errors.append(
                    {
                        "id": _error_id(error_prefix, "registry_duplicate_redis_combination"),
                        "owner_a": owner,
                        "owner_b": app_id,
                        "db": db,
                        "message": "duplicate redis db ownership across apps",
                    }
                )

        key_prefix = normalize_key_prefix(redis.get("key_prefix"))
        if key_prefix is not None:
            owner = seen_key_prefix.get(key_prefix)
            if owner is None:
                seen_key_prefix[key_prefix] = app_id
            elif owner != app_id:
                errors.append(
                    {
                        "id": _error_id(error_prefix, "registry_duplicate_redis_combination"),
                        "owner_a": owner,
                        "owner_b": app_id,
                        "key_prefix": key_prefix,
                        "message": "duplicate normalized redis key_prefix across apps",
                    }
                )
    return errors
