#!/usr/bin/env bash
set -euo pipefail

timestamp() {
  date -u +%Y%m%dT%H%M%SZ
}

log() {
  printf '%s %s\n' "$(timestamp)" "$*"
}

fatal() {
  printf '%s ERROR: %s\n' "$(timestamp)" "$*" >&2
  exit 1
}

ensure_readable() {
  local path="$1"
  if [ ! -r "$path" ]; then
    fatal "Unreadable certificate file: ${path}"
  fi
}

ensure_container() {
  local name="$1"
  if ! docker inspect "$name" >/dev/null 2>&1; then
    fatal "Container ${name} not found"
  fi
}

ensure_container_readable() {
  local path="$1"
  if ! docker exec 1panel-openresty-prod sh -lc "test -r '$path'"; then
    fatal "Container cannot read ${path}"
  fi
}

host_certs_root="/data/1panel/www/certs"
container_certs_root="/www/certs"

host_paths=(
  "${host_certs_root}/zzzai-cloud/fullchain.pem"
  "${host_certs_root}/zzzai-cloud/privkey.pem"
  "${host_certs_root}/1panel-zzzai-cloud/fullchain.pem"
  "${host_certs_root}/1panel-zzzai-cloud/privkey.pem"
)

log "Checking host certificate readability under ${host_certs_root}"
for path in "${host_paths[@]}"; do
  ensure_readable "$path"
done

ensure_container "1panel-openresty-prod"

log "Checking container visibility under ${container_certs_root}"
container_paths=(
  "${container_certs_root}/zzzai-cloud/fullchain.pem"
  "${container_certs_root}/zzzai-cloud/privkey.pem"
  "${container_certs_root}/1panel-zzzai-cloud/fullchain.pem"
  "${container_certs_root}/1panel-zzzai-cloud/privkey.pem"
)

for path in "${container_paths[@]}"; do
  ensure_container_readable "$path"
done

log "Host and container certificate checks passed"
