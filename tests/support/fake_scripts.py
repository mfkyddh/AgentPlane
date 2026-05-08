"""Shared fake script templates for test SSH/Docker simulation.

Provides reusable bash script bodies and installer functions for creating
fake SSH commands in temporary bin/ directories.
"""

from __future__ import annotations

from pathlib import Path


def write_fake_command(bin_dir: Path, name: str, body: str) -> None:
    """Write an executable fake command script to *bin_dir*."""
    script = bin_dir / name
    script.write_text(body, encoding="utf-8")
    script.chmod(0o755)


FAKE_SERVICE_SSH_BODY = """\
#!/usr/bin/env bash
set -euo pipefail
printf 'ssh %s\\n' "$*" >> "$FAKE_CMD_LOG"
cmd="$*"

emit_container() {
  local name="$1"
  local image="$2"
  local running="$3"
  local network_mode="${4:-bridge}"
  local labels="${5:-{}}"
  local extra="${6:-}"
  cat <<JSON
{"Name":"${name}","Config":{"Image":"${image}","Labels":${labels}},"State":{"Status":"${running}","Running":true},"HostConfig":{"NetworkMode":"${network_mode}"}${extra}}
JSON
}

if [[ "$cmd" == *"docker inspect postgres18-prod --format"* ]]; then
  emit_container "postgres18-prod" "postgres:18.3" "running" "bridge" '{}' ',"NetworkSettings":{"Ports":{"5432/tcp":[{"HostIp":"0.0.0.0","HostPort":"5432"}]}}'
  exit 0
fi
if [[ "$cmd" == *"docker inspect redis7-prod --format"* ]]; then
  emit_container "redis7-prod" "redis:7.4.7" "running" "bridge" '{}' ',"NetworkSettings":{"Ports":{"6379/tcp":[{"HostIp":"0.0.0.0","HostPort":"6379"}]}}'
  exit 0
fi
if [[ "$cmd" == *"docker inspect minio-prod --format"* ]]; then
  emit_container "minio-prod" "minio/minio:RELEASE.2025-04-22T22-12-26Z" "running"
  exit 0
fi
if [[ "$cmd" == *"docker inspect 1panel-openresty-prod --format"* ]]; then
  emit_container "1panel-openresty-prod" "1panel/openresty:1.27.1.2-5-1-focal" "running" "infra"
  exit 0
fi
if [[ "$cmd" == *"docker inspect sampleapi-prod --format"* ]]; then
  emit_container "sampleapi-prod" "ghcr.io/example/sampleapi:2026.04" "running" "bridge" '{"com.docker.compose.project":"sampleapi","com.docker.compose.project.config_files":"/opt/agentplane/infra/compose/sampleapi/docker-compose.prod0.yml"}' ',"NetworkSettings":{"Ports":{"3000/tcp":[{"HostIp":"127.0.0.1","HostPort":"3000"}]}}'
  exit 0
fi
if [[ "$cmd" == *"docker inspect relay-trojan-prod --format"* ]]; then
  emit_container "relay-trojan-prod" "ghcr.io/xtls/xray-core:25.3.6" "running" "bridge" '{}' ',"NetworkSettings":{"Ports":{"24443/tcp":[{"HostIp":"0.0.0.0","HostPort":"24443"}]}}'
  exit 0
fi
if [[ "$cmd" == *"docker inspect relay-trojan-host-prod --format"* ]]; then
  emit_container "relay-trojan-host-prod" "ghcr.io/xtls/xray-core:25.3.6" "running" "infra"
  exit 0
fi
if [[ "$cmd" == *"docker inspect legacy-runtime-prod --format"* ]]; then
  emit_container "legacy-runtime-prod" "ghcr.io/example/legacy-runtime:1.0" "running"
  exit 0
fi
if [[ "$cmd" == *"docker inspect legacy-project-prod --format"* ]]; then
  emit_container "legacy-project-prod" "ghcr.io/example/legacy-project:1.0" "running" "bridge" '{"com.docker.compose.project":"legacy-project-prod","com.docker.compose.project.config_files":"/data/1panel/docker/compose/legacy-project-prod/docker-compose.yml"}'
  exit 0
fi
if [[ "$cmd" == *"systemctl is-active mihomo"* ]]; then
  echo active
  exit 0
fi
if [[ "$cmd" == *"systemctl is-enabled mihomo"* ]]; then
  echo enabled
  exit 0
fi
if [[ "$cmd" == *"ss -ltnp | grep 7890"* ]]; then
  echo 'LISTEN 0 4096 172.18.0.1:7890 0.0.0.0:* users:(("mihomo",pid=1,fd=10))'
  exit 0
fi
if [[ "$cmd" == *"docker restart postgres18-prod"* ]]; then
  exit 0
fi
if [[ "$cmd" == *"docker restart sampleapi-prod"* ]]; then
  exit 0
fi
if [[ "$cmd" == *"docker restart legacy-runtime-prod"* ]]; then
  exit 0
fi
if [[ "$cmd" == *"docker restart legacy-project-prod"* ]]; then
  exit 0
fi
if [[ "$cmd" == *"cd /opt/agentplane/infra/compose/postgres && docker compose -f docker-compose.prod0.yml up -d"* ]]; then
  exit 0
fi
if [[ "$cmd" == *"cd /opt/agentplane/infra/compose/sampleapi && docker compose -f docker-compose.prod0.yml up -d"* ]]; then
  exit 0
fi
if [[ "$cmd" == *"systemctl restart mihomo"* ]]; then
  exit 0
fi
if [[ "$cmd" == *"systemctl reload mihomo"* ]]; then
  exit 0
fi
if [[ "$cmd" == *"docker exec 1panel-openresty-prod nginx -t && docker exec 1panel-openresty-prod nginx -s reload"* ]]; then
  exit 0
fi
if [[ "$cmd" == *"test -r /data/relay-trojan/certs/fullchain.pem"* ]]; then
  exit 0
fi
if [[ "$cmd" == *"test -r /data/relay-trojan/certs/privkey.pem"* ]]; then
  exit 0
fi
if [[ "$cmd" == *"test -x /usr/local/bin/renew-relay-trojan-cert.sh"* ]]; then
  exit 0
fi
if [[ "$cmd" == *"crontab -l | grep -F -- '17 3 1 * * /usr/local/bin/renew-relay-trojan-cert.sh >> /var/log/relay-trojan-cert-renew.log 2>&1'"* ]]; then
  echo '17 3 1 * * /usr/local/bin/renew-relay-trojan-cert.sh >> /var/log/relay-trojan-cert-renew.log 2>&1'
  exit 0
fi
exit 0
"""


FAKE_BRIDGE_NETWORK_SSH_BODY = """\
#!/usr/bin/env bash
set -euo pipefail
printf 'ssh %s\\n' "$*" >> "$FAKE_CMD_LOG"
cmd="$*"
state_dir="${FAKE_NETWORK_STATE_DIR:?}"
bridge="br-66f7da1be943"
if [[ "$cmd" == *"docker network inspect zqf_network --format"* ]]; then
  cat <<'JSON'
{"Name":"zqf_network","Id":"66f7da1be943bc160d7df638561fe15ccc1ceea6912e9c753dd40d087e23d8b3","Driver":"bridge","IPAM":{"Config":[{"Subnet":"172.19.0.0/16","Gateway":"172.19.0.1"}]},"Containers":{"sub2api":{"Name":"sub2api-prod"}}}
JSON
  exit 0
fi
if [[ "$cmd" == *"ip -json -4 addr show dev ${bridge}"* ]]; then
  if [[ -f "${state_dir}/gateway_present" ]]; then
    echo '[{"ifname":"br-66f7da1be943","addr_info":[{"local":"172.19.0.1","prefixlen":16}]}]'
  else
    echo '[{"ifname":"br-66f7da1be943","addr_info":[]}]'
  fi
  exit 0
fi
if [[ "$cmd" == *"ip -json route show 172.19.0.0/16"* ]]; then
  if [[ -f "${state_dir}/route_present" ]]; then
    echo '[{"dst":"172.19.0.0/16","dev":"br-66f7da1be943","prefsrc":"172.19.0.1"}]'
  else
    echo '[]'
  fi
  exit 0
fi
if [[ "$cmd" == *"ip addr add 172.19.0.1/16 dev ${bridge}"* ]]; then
  touch "${state_dir}/gateway_present"
  exit 0
fi
if [[ "$cmd" == *"ip route replace 172.19.0.0/16 dev ${bridge} src 172.19.0.1"* ]]; then
  touch "${state_dir}/route_present"
  exit 0
fi
if [[ "$cmd" == *"docker inspect sub2api-prod"* ]]; then
  cat <<'JSON'
[{"Config":{"Env":["DATABASE_PASSWORD=db-secret","REDIS_PASSWORD=redis-secret","SERVER_PORT=8080"]}}]
JSON
  exit 0
fi
if [[ "$cmd" == *"curl -fsS http://127.0.0.1:18080/health"* ]]; then
  echo '{"status":"ok"}'
  exit 0
fi
exit 0
"""


def write_fake_service_ssh(bin_dir: Path) -> None:
    """Install a fake SSH script that simulates service inspection commands."""
    write_fake_command(bin_dir, "ssh", FAKE_SERVICE_SSH_BODY)


def write_fake_bridge_network_ssh(bin_dir: Path) -> None:
    """Install a fake SSH script that simulates bridge network commands."""
    write_fake_command(bin_dir, "ssh", FAKE_BRIDGE_NETWORK_SSH_BODY)
