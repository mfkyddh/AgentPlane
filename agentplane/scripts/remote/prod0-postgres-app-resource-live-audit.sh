#!/usr/bin/env bash
set -euo pipefail

# Internal remote helper reused by the formal app-resource/PostgreSQL CLI flows.

admin_env_file="${POSTGRES_ADMIN_ENV_FILE:-/opt/agentplane/secrets/services/postgres/admin.prod0.env}"
if [[ ! -r "$admin_env_file" ]]; then
  echo "postgres admin env file not readable: $admin_env_file" >&2
  exit 1
fi

set -a
source "$admin_env_file"
set +a

python3 - <<'PY'
import json
import os
import subprocess
from urllib.parse import unquote, urlparse


APP_CONTAINERS = {
    "newapi": "newapi-prod",
    "sub2api": "sub2api-prod",
    "sub2apipay": "sub2apipay-prod",
}
PG_RUNTIME_DATABASE_KEYS = (
    "DATABASE_DBNAME",
    "DATABASE_NAME",
    "DATABASE_DB",
    "DB_DATABASE",
    "DB_NAME",
    "POSTGRES_DB",
    "PGDATABASE",
)
PG_RUNTIME_USER_KEYS = (
    "DATABASE_USER",
    "DATABASE_USERNAME",
    "DB_USER",
    "DB_USERNAME",
    "POSTGRES_USER",
    "PGUSER",
)
PG_RUNTIME_DSN_KEYS = (
    "DATABASE_URL",
    "SQL_DSN",
    "POSTGRES_URL",
    "POSTGRES_DSN",
    "DB_URL",
    "DB_DSN",
    "DATABASE_DSN",
)


def run(command: list[str]) -> str:
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or f"command failed with exit code {result.returncode}"
        raise RuntimeError(message)
    return result.stdout


def inspect_env(container_name: str) -> dict[str, str]:
    raw = run(DOCKER + ["inspect", "--format", "{{json .Config.Env}}", container_name]).strip()
    payload = json.loads(raw)
    if not isinstance(payload, list):
        return {}
    values: dict[str, str] = {}
    for item in payload:
        if not isinstance(item, str) or "=" not in item:
            continue
        key, value = item.split("=", 1)
        values[key] = value
    return values


def env_value(values: dict[str, str], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = values.get(key)
        if value:
            return value
    return None


def parse_url(value: str) -> tuple[str | None, str | None]:
    parsed = urlparse(value)
    database = parsed.path.lstrip("/") or None
    username = unquote(parsed.username) if parsed.username else None
    return database, username


def runtime_pg_binding(values: dict[str, str]) -> dict[str, str | None]:
    database = env_value(values, PG_RUNTIME_DATABASE_KEYS)
    user = env_value(values, PG_RUNTIME_USER_KEYS)
    if database is None or user is None:
        dsn = env_value(values, PG_RUNTIME_DSN_KEYS)
        if dsn is not None:
            dsn_database, dsn_user = parse_url(dsn)
            if database is None:
                database = dsn_database
            if user is None:
                user = dsn_user
    return {
        "database": database,
        "user": user,
        "env": values,
    }


def psql_query(sql: str) -> str:
    env = os.environ.copy()
    password = env.get("PGPASSWORD") or env.get("POSTGRES_PASSWORD")
    user = env.get("PGUSER") or env.get("POSTGRES_USER") or "postgres"
    database = env.get("PGDATABASE") or env.get("POSTGRES_DB") or "postgres"
    host = env.get("PGHOST") or "127.0.0.1"
    port = env.get("PGPORT") or "5432"

    command = DOCKER + ["exec"]
    if password:
        command.extend(["-e", f"PGPASSWORD={password}"])
    command.extend(
        [
            "postgres18-prod",
            "psql",
            "-h",
            host,
            "-p",
            port,
            "-U",
            user,
            "-d",
            database,
            "-At",
            "-F",
            "\t",
            "-c",
            sql,
        ]
    )
    return run(command)


DOCKER = (["sudo"] if os.geteuid() != 0 else []) + ["docker"]

apps = {
    app_id: runtime_pg_binding(inspect_env(container_name))
    for app_id, container_name in APP_CONTAINERS.items()
}

database_rows = psql_query(
    "SELECT datname, pg_catalog.pg_get_userbyid(datdba) "
    "FROM pg_database WHERE datistemplate = false ORDER BY datname;"
)
databases: dict[str, str] = {}
for raw_line in database_rows.splitlines():
    line = raw_line.strip()
    if not line:
        continue
    name, owner = (line.split("\t", 1) + [""])[:2]
    databases[name] = owner

role_rows = psql_query("SELECT rolname FROM pg_roles ORDER BY rolname;")
roles = [line.strip() for line in role_rows.splitlines() if line.strip()]

print(
    json.dumps(
        {
            "apps": apps,
            "catalog": {
                "databases": databases,
                "roles": roles,
            },
        },
        ensure_ascii=False,
    )
)
PY
