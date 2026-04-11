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

ensure_file() {
  local path="$1"
  if [ ! -f "$path" ] || [ ! -r "$path" ]; then
    fatal "Missing or unreadable certificate file: ${path}"
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
    fatal "OpenResty container cannot read ${path}"
  fi
}

host_certs_root="/data/1panel/www/certs"
cert_zzzai_dir="${host_certs_root}/zzzai-cloud"
cert_1panel_dir="${host_certs_root}/1panel-zzzai-cloud"
backup_root="${host_certs_root}/_backup/$(timestamp)"
backup_canonical_root="${backup_root}/canonical"

mkdir -p "$cert_zzzai_dir" "$cert_1panel_dir"

zzzai_cert_src="${cert_zzzai_dir}/fullchain.pem"
zzzai_key_src="${cert_zzzai_dir}/privkey.pem"
panel_cert_src="${cert_1panel_dir}/fullchain.pem"
panel_key_src="${cert_1panel_dir}/privkey.pem"

ensure_file "$zzzai_cert_src"
ensure_file "$zzzai_key_src"
ensure_file "$panel_cert_src"
ensure_file "$panel_key_src"

mkdir -p "$backup_canonical_root"

backup_existing() {
  local source="$1"
  local backup_path="${backup_canonical_root}${source#${host_certs_root}}"
  if [ -f "$source" ]; then
    mkdir -p "$(dirname "$backup_path")"
    cp -a "$source" "$backup_path"
  fi
}

backup_existing "${cert_zzzai_dir}/fullchain.pem"
backup_existing "${cert_zzzai_dir}/privkey.pem"
backup_existing "${cert_1panel_dir}/fullchain.pem"
backup_existing "${cert_1panel_dir}/privkey.pem"

log "Normalizing certificate file permissions under ${host_certs_root}"
chmod 644 "$zzzai_cert_src" "$panel_cert_src"
chmod 640 "$zzzai_key_src" "$panel_key_src"

ensure_container "1panel-openresty-prod"
ensure_container_readable "/www/certs/zzzai-cloud/fullchain.pem"
ensure_container_readable "/www/certs/zzzai-cloud/privkey.pem"
ensure_container_readable "/www/certs/1panel-zzzai-cloud/fullchain.pem"
ensure_container_readable "/www/certs/1panel-zzzai-cloud/privkey.pem"

log "Host certificates already canonical under ${host_certs_root}; backup at ${backup_root}"
