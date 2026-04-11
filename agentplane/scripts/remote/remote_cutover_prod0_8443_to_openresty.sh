#!/usr/bin/env bash
set -euo pipefail

timestamp() {
  date -u +%Y-%m-%dT%H:%M:%SZ
}

log() {
  printf '%s %s\n' "$(timestamp)" "$*"
}

fatal() {
  printf '%s ERROR: %s\n' "$(timestamp)" "$*" >&2
  exit 1
}

ensure_container_cert() {
  local path="$1"
  if ! docker exec 1panel-openresty-prod sh -lc "test -r '$path'"; then
    fatal "OpenResty container cannot read ${path}"
  fi
}

restore_openresty_backup() {
  local backup_conf="$backup_root/rollback/conf.d"
  local backup_sites="$backup_root/rollback/sites"

  if [ ! -d "$backup_conf" ] || [ ! -d "$backup_sites" ]; then
    log "Recovery: rollback backup not found under ${backup_root}/rollback"
    return 1
  fi

  log "Recovery: restoring OpenResty conf.d from ${backup_conf}"
  docker cp "$backup_conf/." 1panel-openresty-prod:/usr/local/openresty/nginx/conf/conf.d/
  log "Recovery: restoring OpenResty sites from ${backup_sites}"
  docker cp "$backup_sites/." 1panel-openresty-prod:/www/sites/
  docker exec 1panel-openresty-prod sh -lc 'nginx -t'
  docker exec 1panel-openresty-prod sh -lc 'nginx -s reload'
}

cleanup() {
  local exit_code="$?"
  if [ -n "${tmp_conf_dir-}" ] && [ -d "$tmp_conf_dir" ]; then
    rm -rf "$tmp_conf_dir"
  fi

  if [ "$exit_code" -ne 0 ] && [ "$cutover_succeeded" -eq 0 ]; then
    set +e
    if [ "$openresty_config_applied" -eq 1 ]; then
      restore_openresty_backup || log "Recovery: failed to restore OpenResty backup (check manually)"
    fi
    set -e
  fi

  return "$exit_code"
}

check_url() {
  local prefix="$1"
  local host="$2"
  local path="$3"
  local port="$4"
  local expected="$5"
  local output_dir="$backup_root/$prefix"
  local output_file="$output_dir/curl-${host}-${port}.txt"

  log "curl --resolve ${host}:${port}:127.0.0.1 https://${host}:${port}${path} (expect ${expected})"
  mkdir -p "$output_dir"
  local status
  if ! status=$(curl -sS --resolve "${host}:${port}:127.0.0.1" \
    --connect-timeout 5 \
    --max-time 15 \
    "https://${host}:${port}${path}" \
    -o "$output_file" \
    -w '%{http_code}'); then
    fatal "curl failure for ${host}:${port}${path} (check ${output_file})"
  fi

  if [ "$expected" = "2xx" ]; then
    case "$status" in
      2* | 3*)
        log "${host}:${port}${path} returned ${status}"
        ;;
      *)
        fatal "${host}:${port}${path} returned ${status}, expected 2xx (body saved to ${output_file})"
        ;;
    esac
    return
  fi

  if [ "$status" != "$expected" ]; then
    fatal "${host}:${port}${path} returned ${status}, expected ${expected} (body saved to ${output_file})"
  fi
  log "${host}:${port}${path} returned expected ${expected}"
}

backup_root="/root/8443-cutover/backups/$(date -u +%Y%m%dT%H%M%SZ)"
bundle_root="/root/8443-cutover/bundles/cutover"
bundle_conf="$bundle_root/conf.d"
bundle_sites="$bundle_root/sites"
tmp_conf_dir=""
cutover_succeeded=0
openresty_config_applied=0
container_certs_root="/www/certs"

trap cleanup EXIT

log "Starting cutover: backup directory ${backup_root}"
mkdir -p "$backup_root/preflight" "$backup_root/postcutover" "$backup_root/rollback"

log "Saving docker inspect output"
docker inspect 1panel-openresty-prod > "$backup_root/preflight/1panel-openresty-prod.inspect"

log "Capturing nginx -T for 1panel-openresty-prod"
docker exec 1panel-openresty-prod sh -lc 'nginx -T' > "$backup_root/preflight/1panel-openresty-prod.nginx-T"

log "Preflight gate: validating 8443 endpoints before applying new bundle"
preflight_checks=(
  "1panel.zzzai.cloud|/0f0e8602e3|2xx"
  "newapi.zzzai.cloud|/v1/models|401"
  "token.zzzai.cloud|/|2xx"
  "pay.zzzai.cloud|/pay|2xx"
)

for entry in "${preflight_checks[@]}"; do
  IFS='|' read -r host path expected <<< "$entry"
  check_url preflight "$host" "$path" 8443 "$expected"
done

log "Backing up current OpenResty configuration tree"
mkdir -p "$backup_root/rollback"
docker cp 1panel-openresty-prod:/usr/local/openresty/nginx/conf/conf.d "$backup_root/rollback/"
docker cp 1panel-openresty-prod:/www/sites "$backup_root/rollback/"

if [ ! -d "$bundle_conf" ] || [ ! -d "$bundle_sites" ]; then
  fatal "Cutover bundle missing at $bundle_root"
fi

log "Validating OpenResty container can read host-managed certificates"
ensure_container_cert "${container_certs_root}/zzzai-cloud/fullchain.pem"
ensure_container_cert "${container_certs_root}/zzzai-cloud/privkey.pem"
ensure_container_cert "${container_certs_root}/1panel-zzzai-cloud/fullchain.pem"
ensure_container_cert "${container_certs_root}/1panel-zzzai-cloud/privkey.pem"

tmp_conf_dir=$(mktemp -d)
log "Staging cutover conf.d in $tmp_conf_dir"
cp -a "$bundle_conf/." "$tmp_conf_dir/"

log "Removing existing 8443 conf and site bundles in OpenResty"
openresty_config_applied=1
docker exec 1panel-openresty-prod sh -lc 'rm -f /usr/local/openresty/nginx/conf/conf.d/*-8443.conf'
docker exec 1panel-openresty-prod sh -lc 'rm -rf /www/sites/*-8443'
docker exec 1panel-openresty-prod sh -lc 'mkdir -p /www/sites'

log "Copying conf.d bundle into 1panel-openresty-prod"
docker cp "$tmp_conf_dir/." 1panel-openresty-prod:/usr/local/openresty/nginx/conf/conf.d/
log "Copying sites bundle (proxy includes only) into 1panel-openresty-prod"
docker cp "$bundle_sites/." 1panel-openresty-prod:/www/sites/

log "Validating OpenResty configuration before reload"
docker exec 1panel-openresty-prod sh -lc 'nginx -t'

log "Reloading OpenResty to pick up the new 8443 listeners"
docker exec 1panel-openresty-prod sh -lc 'nginx -s reload'
log "Waiting for OpenResty to bind :8443"
if ! timeout 20 sh -c 'until ss -ltnp | grep -q ":8443 .*openresty"; do sleep 1; done'; then
  fatal "Timed out waiting for OpenResty to bind :8443"
fi

post_checks=(
  "1panel.zzzai.cloud|/0f0e8602e3|2xx"
  "newapi.zzzai.cloud|/v1/models|401"
  "token.zzzai.cloud|/|2xx"
  "pay.zzzai.cloud|/pay|2xx"
)

for entry in "${post_checks[@]}"; do
  IFS='|' read -r host path expected <<< "$entry"
  check_url postcutover "$host" "$path" 8443 "$expected"
done

cutover_succeeded=1
log "Cutover verification succeeded"
