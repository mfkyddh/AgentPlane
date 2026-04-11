#!/usr/bin/env bash
set -euo pipefail

if [ $# -lt 1 ]; then
  printf 'Usage: %s MODE\\n' "$0" >&2
  printf 'MODE must be rehearsal or cutover\\n' >&2
  exit 1
fi

mode="$1"
case "$mode" in
  rehearsal)
    port=2443
    ;;
  cutover)
    port=8443
    ;;
  *)
    printf 'Unknown mode: %s\\n' "$mode" >&2
    exit 1
    ;;
esac

bundle_root="/root/8443-cutover/bundles/$mode"
conf_dir="$bundle_root/conf.d"
sites_dir="$bundle_root/sites"
host_certs_root="/data/1panel/www/certs"
cert_zzzai_dir="${host_certs_root}/zzzai-cloud"
cert_1panel_dir="${host_certs_root}/1panel-zzzai-cloud"

rm -rf "$bundle_root"
mkdir -p "$conf_dir" "$sites_dir"

ensure_file() {
  local path="$1"

  if [ ! -f "$path" ]; then
    printf 'Missing SSL artifact: %s\n' "$path" >&2
    exit 1
  fi
}

bundle_site_name() {
  local site="$1"

  printf '%s-8443\n' "$site"
}

create_site_structure() {
  local site="$1"
  local bundle_site

  bundle_site="$(bundle_site_name "$site")"
  mkdir -p "$sites_dir/$bundle_site/proxy"
}

write_proxy_root_conf() {
  local site="$1"
  local upstream="$2"
  local bundle_site
  local target

  bundle_site="$(bundle_site_name "$site")"
  target="$sites_dir/$bundle_site/proxy/root.conf"

  cat <<EOF > "$target"
location / {
  proxy_http_version 1.1;
  proxy_set_header Host \$host;
  proxy_set_header X-Real-IP \$remote_addr;
  proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
  proxy_set_header X-Forwarded-Proto \$scheme;
  proxy_set_header X-Forwarded-Port \$server_port;
  proxy_set_header Upgrade \$http_upgrade;
  proxy_set_header Connection "upgrade";
  proxy_set_header X-Forwarded-Host \$host;
  proxy_set_header X-Forwarded-Server \$host;
  proxy_pass $upstream;
}
EOF
}

write_token_setup_conf() {
  local target="$sites_dir/$(bundle_site_name token)/proxy/setup.conf"

  cat <<EOF > "$target"
location = /setup {
  allow 127.0.0.1;
  allow ::1;
  deny all;
  proxy_http_version 1.1;
  proxy_set_header Host \$host;
  proxy_set_header X-Real-IP \$remote_addr;
  proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
  proxy_set_header X-Forwarded-Proto \$scheme;
  proxy_set_header X-Forwarded-Port \$server_port;
  proxy_set_header Upgrade \$http_upgrade;
  proxy_set_header Connection "upgrade";
  proxy_set_header X-Forwarded-Host \$host;
  proxy_set_header X-Forwarded-Server \$host;
  proxy_pass http://127.0.0.1:18080;
}
EOF
}

write_standard_conf() {
  local site="$1"
  local host_name="$2"
  local cert_dir="$3"
  local extra_include="${4:-}"
  local target="$conf_dir/${site}-8443.conf"
  local bundle_site

  bundle_site="$(bundle_site_name "$site")"

  cat <<EOF > "$target"
server {
  listen $port ssl;
  listen [::]:$port ssl;
  http2 on;
  server_name $host_name;
  ssl_certificate ${cert_dir}/fullchain.pem;
  ssl_certificate_key ${cert_dir}/privkey.pem;
  ssl_protocols TLSv1.2 TLSv1.3;
  ssl_ciphers HIGH:!aNULL:!MD5;
  ssl_session_cache shared:SSL:10m;
  ssl_session_timeout 1d;
  include /www/sites/$bundle_site/proxy/root.conf;
EOF

  if [ -n "$extra_include" ]; then
    printf '  include %s;\n' "$extra_include" >> "$target"
  fi

cat <<EOF >> "$target"
}
EOF
}

for site in 1panel newapi token pay; do
  create_site_structure "$site"
done

ensure_file "${cert_zzzai_dir}/fullchain.pem"
ensure_file "${cert_zzzai_dir}/privkey.pem"
ensure_file "${cert_1panel_dir}/fullchain.pem"
ensure_file "${cert_1panel_dir}/privkey.pem"

write_proxy_root_conf 1panel http://127.0.0.1:2096/
write_proxy_root_conf newapi http://127.0.0.1:3000/
write_proxy_root_conf token http://127.0.0.1:18080/
write_proxy_root_conf pay http://127.0.0.1:18091
write_token_setup_conf

write_standard_conf 1panel 1panel.zzzai.cloud /www/certs/1panel-zzzai-cloud
write_standard_conf newapi newapi.zzzai.cloud /www/certs/zzzai-cloud
write_standard_conf token token.zzzai.cloud /www/certs/zzzai-cloud /www/sites/token-8443/proxy/setup.conf
write_standard_conf pay pay.zzzai.cloud /www/certs/zzzai-cloud
