#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  echo "run as root" >&2
  exit 1
fi

timestamp="$(date +%Y%m%d-%H%M%S)"
backup_root="/data/backups/manual/prod0-sub2-governance-${timestamp}"
mkdir -p "$backup_root"

backup_item() {
  local source="$1"
  local name="$2"
  if [[ -e "$source" || -L "$source" ]]; then
    cp -a "$source" "$backup_root/$name"
  fi
}

ensure_dir() {
  local path="$1"
  install -d -m 0755 "$path"
}

ensure_symlink() {
  local target="$1"
  local link_path="$2"
  rm -rf "$link_path"
  ln -s "$target" "$link_path"
}

rewrite_sub2api_env() {
  local env_file="$1"
  sed -i \
    -e 's#^DATA_DIR=.*#DATA_DIR=/data/sub2api/data#' \
    -e 's#^PRICING_DATA_DIR=.*#PRICING_DATA_DIR=/data/sub2api/data/pricing#' \
    -e 's#^SORA_STORAGE_LOCAL_PATH=.*#SORA_STORAGE_LOCAL_PATH=/data/sub2api/data/sora#' \
    "$env_file"
}

backup_item /opt/sub2api opt-sub2api
backup_item /etc/sub2api etc-sub2api
backup_item /var/lib/sub2api var-lib-sub2api
backup_item /opt/sub2apipay opt-sub2apipay
backup_item /etc/sub2apipay etc-sub2apipay
backup_item /etc/systemd/system/sub2api.service sub2api.service
backup_item /etc/systemd/system/sub2apipay-prod.service sub2apipay-prod.service

ensure_dir /data/sub2api
ensure_dir /data/sub2api/config
ensure_dir /data/sub2api/data
ensure_dir /data/sub2api/logs
ensure_dir /data/sub2apipay
ensure_dir /data/sub2apipay/app
ensure_dir /data/sub2apipay/config
ensure_dir /data/sub2apipay/logs

if [[ ! -L /opt/sub2api ]]; then
  rsync -a /opt/sub2api/ /data/sub2api/app/
fi

if [[ ! -L /opt/sub2apipay ]]; then
  rsync -a /opt/sub2apipay/ /data/sub2apipay/app/
fi

systemctl stop sub2api || true
systemctl stop sub2apipay-prod.service || true

if [[ ! -L /var/lib/sub2api ]]; then
  rsync -a /var/lib/sub2api/ /data/sub2api/data/
fi

cp -aL /etc/sub2api/sub2api-prod.env /data/sub2api/config/sub2api-prod.env
rewrite_sub2api_env /data/sub2api/config/sub2api-prod.env
cp -aL /etc/sub2apipay/sub2apipay-prod.env /data/sub2apipay/config/sub2apipay-prod.env

if [[ -f /opt/sub2apipay/current/.env.runtime ]]; then
  cp -aL /opt/sub2apipay/current/.env.runtime /data/sub2apipay/config/.env.runtime
fi

if [[ ! -L /opt/sub2api ]]; then
  rm -rf /opt/sub2api
  ln -s /data/sub2api/app /opt/sub2api
fi

if [[ ! -L /var/lib/sub2api ]]; then
  rm -rf /var/lib/sub2api
  ln -s /data/sub2api/data /var/lib/sub2api
fi

if [[ ! -L /opt/sub2apipay ]]; then
  rm -rf /opt/sub2apipay
  ln -s /data/sub2apipay/app /opt/sub2apipay
fi

ensure_dir /etc/sub2api
ensure_dir /etc/sub2apipay
ensure_symlink /data/sub2api/config/sub2api-prod.env /etc/sub2api/sub2api-prod.env
ensure_symlink /data/sub2apipay/config/sub2apipay-prod.env /etc/sub2apipay/sub2apipay-prod.env

if [[ -f /data/sub2apipay/config/.env.runtime ]]; then
  current_release="$(readlink -f /opt/sub2apipay/current)"
  rm -f "${current_release}/.env.runtime"
  ln -s /data/sub2apipay/config/.env.runtime "${current_release}/.env.runtime"
fi

chown -R sub2api:sub2api /data/sub2api

systemctl daemon-reload
systemctl start sub2api
systemctl start sub2apipay-prod.service

systemctl is-active sub2api >/dev/null
systemctl is-active sub2apipay-prod.service >/dev/null

echo "backup_root=$backup_root"
readlink -f /opt/sub2api
readlink -f /var/lib/sub2api
readlink -f /opt/sub2apipay
readlink -f /etc/sub2api/sub2api-prod.env
readlink -f /etc/sub2apipay/sub2apipay-prod.env
