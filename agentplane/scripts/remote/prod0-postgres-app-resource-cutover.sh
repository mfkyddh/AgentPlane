#!/usr/bin/env bash
set -euo pipefail

ADMIN_ENV_FILE="${POSTGRES_ADMIN_ENV_FILE:-/opt/agentplane/secrets/services/postgres/admin.prod0.env}"
APP_ENV_FILE="${SUB2APIPAY_ENV_FILE:-/data/sub2apipay/config/sub2apipay-prod.env}"
POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-postgres18-prod}"
APPLY_POSTGRES_OWNER_FIX="${APPLY_POSTGRES_OWNER_FIX:-0}"
EXPECTED_POSTGRES_OWNER="${EXPECTED_POSTGRES_OWNER:-app}"

if [[ ! -r "$ADMIN_ENV_FILE" ]]; then
  echo "postgres admin env file not readable: $ADMIN_ENV_FILE" >&2
  exit 1
fi

if [[ ! -r "$APP_ENV_FILE" ]]; then
  echo "sub2apipay env file not readable: $APP_ENV_FILE" >&2
  exit 1
fi

if [[ ! "$EXPECTED_POSTGRES_OWNER" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
  echo "EXPECTED_POSTGRES_OWNER contains unsupported characters: $EXPECTED_POSTGRES_OWNER" >&2
  exit 1
fi

# shellcheck disable=SC1090
set -a
source "$ADMIN_ENV_FILE"
set +a

: "${POSTGRES_USER:?POSTGRES_USER is required in $ADMIN_ENV_FILE}"
: "${POSTGRES_DB:?POSTGRES_DB is required in $ADMIN_ENV_FILE}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required in $ADMIN_ENV_FILE}"

PGHOST="${PGHOST:-127.0.0.1}"
PGPORT="${PGPORT:-5432}"
export PGPASSWORD="${PGPASSWORD:-$POSTGRES_PASSWORD}"

if [[ "$(id -u)" -eq 0 ]]; then
  DOCKER=(docker)
else
  DOCKER=(sudo docker)
fi

psql_query() {
  local sql="$1"
  "${DOCKER[@]}" exec \
    -e "PGPASSWORD=$PGPASSWORD" \
    "$POSTGRES_CONTAINER" \
    psql \
    -v ON_ERROR_STOP=1 \
    -h "$PGHOST" \
    -p "$PGPORT" \
    -U "$POSTGRES_USER" \
    -d "$POSTGRES_DB" \
    -At \
    -F $'\t' \
    -c "$sql"
}

database_owner() {
  local database_name="$1"
  psql_query "SELECT pg_catalog.pg_get_userbyid(datdba) FROM pg_database WHERE datname = '${database_name}';" \
    | tr -d '[:space:]'
}

role_state() {
  local role_name="$1"
  if [[ -n "$(psql_query "SELECT 1 FROM pg_roles WHERE rolname = '${role_name}';")" ]]; then
    printf 'present'
  else
    printf 'missing'
  fi
}

read_database_url_fields() {
  python3 - "$APP_ENV_FILE" <<'PY'
import sys
from urllib.parse import unquote, urlparse

path = sys.argv[1]
database_url = None
with open(path, encoding="utf-8") as handle:
    for raw_line in handle:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key != "DATABASE_URL":
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        database_url = value
        break

if not database_url:
    raise SystemExit("DATABASE_URL not found in app env")

parsed = urlparse(database_url)
try:
    port = parsed.port or 5432
except ValueError as exc:
    raise SystemExit(f"invalid DATABASE_URL port: {exc}") from exc

host = parsed.hostname or ""
database = parsed.path.lstrip("/")
user = unquote(parsed.username or "")

if not host:
    raise SystemExit("DATABASE_URL host could not be parsed")
if not database:
    raise SystemExit("DATABASE_URL database could not be parsed")
if not user:
    raise SystemExit("DATABASE_URL user could not be parsed")

print(host)
print(port)
print(database)
print(user)
PY
}

postgres_owner_before="$(database_owner "postgres")"
sub2apipay_owner="$(database_owner "sub2apipay")"
database_url_fields_file="$(mktemp)"
cleanup() {
  rm -f "$database_url_fields_file"
}
trap cleanup EXIT

if ! read_database_url_fields >"$database_url_fields_file"; then
  echo "failed to parse DATABASE_URL from $APP_ENV_FILE" >&2
  exit 1
fi

mapfile -t database_url_fields <"$database_url_fields_file"

app_db_host="${database_url_fields[0]:-}"
app_db_port="${database_url_fields[1]:-}"
app_db_name="${database_url_fields[2]:-}"
app_db_user="${database_url_fields[3]:-}"

if [[ -z "$app_db_host" || -z "$app_db_port" || -z "$app_db_name" || -z "$app_db_user" ]]; then
  echo "DATABASE_URL parse from $APP_ENV_FILE returned incomplete fields" >&2
  exit 1
fi

echo "== prod0 postgres app resource live check =="
echo "admin_env_file=$ADMIN_ENV_FILE"
echo "app_env_file=$APP_ENV_FILE"
echo "postgres_container=$POSTGRES_CONTAINER"
echo "admin_binding host=$PGHOST port=$PGPORT database=$POSTGRES_DB user=$POSTGRES_USER"
echo "sub2apipay_prod_database_url host=$app_db_host port=$app_db_port database=$app_db_name user=$app_db_user"
echo "database_owner[sub2apipay]=$sub2apipay_owner"
echo "database_owner[postgres]=$postgres_owner_before"
echo "role[sub2apipay_prod0]=$(role_state "sub2apipay_prod0")"
echo "role[postgres]=$(role_state "postgres")"
echo "role[app]=$(role_state "app")"

if [[ "$APPLY_POSTGRES_OWNER_FIX" == "1" ]]; then
  if [[ "$postgres_owner_before" != "$EXPECTED_POSTGRES_OWNER" ]]; then
    echo "applying postgres database owner fix: $postgres_owner_before -> $EXPECTED_POSTGRES_OWNER"
    psql_query "ALTER DATABASE postgres OWNER TO \"$EXPECTED_POSTGRES_OWNER\";" >/dev/null
  else
    echo "postgres database owner already matches expected owner: $EXPECTED_POSTGRES_OWNER"
  fi
  echo "database_owner[postgres]=$(database_owner "postgres")"
else
  echo "readonly_mode=true"
  if [[ "$postgres_owner_before" != "$EXPECTED_POSTGRES_OWNER" ]]; then
    echo "hint=export APPLY_POSTGRES_OWNER_FIX=1 to change postgres owner to $EXPECTED_POSTGRES_OWNER"
  fi
fi
