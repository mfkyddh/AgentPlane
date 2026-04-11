#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

assert_file() {
  local path="$1"
  [[ -f "$path" ]] || fail "missing file: $path"
}

assert_not_file() {
  local path="$1"
  [[ ! -f "$path" ]] || fail "unexpected legacy file: $path"
}

assert_grep() {
  local pattern="$1"
  local path="$2"
  grep -Eq "$pattern" "$path" || fail "pattern not found in $path: $pattern"
}

check_static_bind_pair() {
  local service="$1"
  local bind_pattern="$2"
  local service_dir="$ROOT_DIR/infra/compose/$service"
  local wsl_file="$service_dir/docker-compose.wsl.yml"
  local prod_file="$service_dir/docker-compose.prod0.yml"

  assert_file "$wsl_file"
  assert_file "$prod_file"
  assert_not_file "$service_dir/docker-compose.yml"

  assert_grep "$bind_pattern" "$wsl_file"
  assert_grep "$bind_pattern" "$prod_file"

  docker compose -f "$wsl_file" config >/dev/null
  docker compose -f "$prod_file" config >/dev/null
}

check_template_bind_pair() {
  local service="$1"
  local env_template="$2"
  local bind_pattern="$3"
  local service_dir="$ROOT_DIR/infra/compose/$service"
  local wsl_file="$service_dir/docker-compose.wsl.yml"
  local prod_file="$service_dir/docker-compose.prod0.yml"
  local temp_dir
  local wsl_env
  local prod_env

  assert_file "$wsl_file"
  assert_file "$prod_file"
  assert_file "$env_template"
  assert_not_file "$service_dir/docker-compose.yml"

  assert_grep "$bind_pattern" "$env_template"

  temp_dir="$(mktemp -d)"
  trap 'rm -rf "$temp_dir"' RETURN
  wsl_env="$temp_dir/cliproxyapi.wsl.env"
  prod_env="$temp_dir/cliproxyapi.prod0.env"

  cp "$env_template" "$wsl_env"
  sed 's/^CLI_PROXY_CONTAINER_NAME=.*/CLI_PROXY_CONTAINER_NAME=cli-proxy-api-prod/' "$env_template" >"$prod_env"

  docker compose --env-file "$wsl_env" -f "$wsl_file" config >/dev/null
  docker compose --env-file "$prod_env" -f "$prod_file" config >/dev/null
}

check_static_bind_pair "redis" '0\.0\.0\.0:6379:6379'
check_template_bind_pair "cliproxyapi" "$ROOT_DIR/templates/services/cliproxyapi.env.example" '^CLI_PROXY_BIND_IP=0\.0\.0\.0$'

echo "compose template layout checks passed"
