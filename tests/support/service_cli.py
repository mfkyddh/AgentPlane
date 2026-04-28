import json
import os
import subprocess
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agentplane.cli.app import main as cli_main  # noqa: E402


def run_cli(*args: str, cwd: Path | None = None, env_overrides: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = None
    if cwd is None:
        repo_root: Path | None = None
        for idx, token in enumerate(args):
            if token == "--repo-root" and idx + 1 < len(args):
                repo_root = Path(args[idx + 1])
                break
            if token.startswith("--repo-root="):
                repo_root = Path(token.split("=", 1)[1])
                break
        if repo_root is not None:
            cwd = repo_root
            env = os.environ.copy()
            repo_path = str(REPO_ROOT)
            existing = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = repo_path if not existing else f"{repo_path}:{existing}"
    if env_overrides:
        env = dict(env or os.environ.copy())
        env.update(env_overrides)
        if "FAKE_CMD_LOG" in env_overrides:
            env.setdefault("AGENTPLANE_DISABLE_WSL_SSH", "1")
    return subprocess.run(
        [sys.executable, "-m", "agentplane.cli", *args],
        cwd=cwd or REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def run_cli_inline(*args: str) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()
    with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
        exit_code = cli_main(list(args))
    return exit_code, stdout.getvalue(), stderr.getvalue()


def write_fake_command(bin_dir: Path, name: str, body: str) -> None:
    script = bin_dir / name
    script.write_text(body, encoding="utf-8")
    script.chmod(0o755)


def write_fake_service_ssh(bin_dir: Path) -> None:
    write_fake_command(
        bin_dir,
        "ssh",
        """#!/usr/bin/env bash
set -euo pipefail
printf 'ssh %s\\n' "$*" >> "$FAKE_CMD_LOG"
cmd="$*"

emit_container() {
  local name="$1"
  local image="$2"
  local running="$3"
  local network_mode="${4:-bridge}"
  local extra="${5:-}"
  cat <<JSON
{"Name":"${name}","Config":{"Image":"${image}"},"State":{"Status":"${running}","Running":true},"HostConfig":{"NetworkMode":"${network_mode}"}${extra}}
JSON
}

if [[ "$cmd" == *"docker inspect postgres18-prod --format"* ]]; then
  emit_container "postgres18-prod" "postgres:18.3" "running" "bridge" ',"NetworkSettings":{"Ports":{"5432/tcp":[{"HostIp":"0.0.0.0","HostPort":"5432"}]}}'
  exit 0
fi
if [[ "$cmd" == *"docker inspect redis7-prod --format"* ]]; then
  emit_container "redis7-prod" "redis:7.4.7" "running" "bridge" ',"NetworkSettings":{"Ports":{"6379/tcp":[{"HostIp":"0.0.0.0","HostPort":"6379"}]}}'
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
  emit_container "sampleapi-prod" "ghcr.io/example/sampleapi:2026.04" "running" "bridge" ',"NetworkSettings":{"Ports":{"3000/tcp":[{"HostIp":"127.0.0.1","HostPort":"3000"}]}}'
  exit 0
fi
if [[ "$cmd" == *"docker inspect relay-trojan-prod --format"* ]]; then
  emit_container "relay-trojan-prod" "ghcr.io/xtls/xray-core:25.3.6" "running" "bridge" ',"NetworkSettings":{"Ports":{"24443/tcp":[{"HostIp":"0.0.0.0","HostPort":"24443"}]}}'
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
  emit_container "legacy-project-prod" "ghcr.io/example/legacy-project:1.0" "running"
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
""",
    )


def write_inventory(root: Path) -> None:
    (root / "inventory" / "servers" / "prod0-main").mkdir(parents=True, exist_ok=True)
    (root / "inventory" / "servers" / "prod0-main" / "inventory.json").write_text(
        json.dumps(
            {
                "ssh": {"aliases": ["prod0-main"], "user": "root"},
                "services": {
                    "postgres": {
                        "image": "postgres:18.3",
                        "container_name": "postgres18-prod",
                        "status": "running",
                        "host_binding": "0.0.0.0:5432",
                        "data_dir": "/data/postgres/data",
                    },
                    "redis": {
                        "image": "redis:7.4.7",
                        "container_name": "redis7-prod",
                        "status": "running",
                        "host_binding": "0.0.0.0:6379",
                        "data_dir": "/data/redis/data",
                    },
                    "minio": {
                        "image": "minio/minio:RELEASE.2025-04-22T22-12-26Z",
                        "container_name": "minio-prod",
                        "status": "running",
                        "host_bindings": ["0.0.0.0:9000", "0.0.0.0:9001"],
                        "data_dir": "/data/minio/data",
                        "config_dir": "/data/minio/config",
                    },
                    "onepanel_openresty": {
                        "container_name": "1panel-openresty-prod",
                        "status": "running",
                        "network_mode": "infra",
                        "listen_ports": [8443],
                    },
                    "sampleapi": {
                        "control_plane": "compose",
                        "container_name": "sampleapi-prod",
                        "image": "ghcr.io/example/sampleapi:2026.04",
                        "status": "running",
                        "host_binding": "127.0.0.1:3000",
                    },
                "relay-trojan": {
                    "control_plane": "compose",
                    "container_name": "relay-trojan-prod",
                    "image": "ghcr.io/xtls/xray-core:25.3.6",
                    "status": "running",
                    "host_binding": "0.0.0.0:24443",
                    "runtime_root": "/data/relay-trojan",
                    "public_endpoint": {
                        "domain": "relay.example.org",
                        "port": 24443,
                        "protocol": "trojan",
                        "transport": "tcp+tls",
                        "cloudflare_proxy": False,
                        "dns": {
                            "provider": "cloudflare",
                            "zone_name": "example.org",
                            "record_type": "A",
                            "record_content": "198.51.100.20",
                            "proxied": False,
                        },
                        "certificate": {
                            "fullchain_path": "/data/relay-trojan/certs/fullchain.pem",
                            "privkey_path": "/data/relay-trojan/certs/privkey.pem",
                            "renew_script_path": "/usr/local/bin/renew-relay-trojan-cert.sh",
                            "renew_cron": "17 3 1 * * /usr/local/bin/renew-relay-trojan-cert.sh >> /var/log/relay-trojan-cert-renew.log 2>&1",
                        },
                    },
                    "client_profile": {
                        "format": "clash-local-profile",
                        "node_name": "Prod2|Relay",
                        "sni": "relay.example.org",
                    },
                },
                "relay-trojan-host": {
                    "control_plane": "compose",
                    "container_name": "relay-trojan-host-prod",
                    "image": "ghcr.io/xtls/xray-core:25.3.6",
                    "status": "running",
                    "host_binding": "0.0.0.0:24444",
                    "network_mode": "infra",
                },
                    "legacy_runtime": {
                        "control_plane": "onepanel-app",
                        "container_name": "legacy-runtime-prod",
                        "image": "ghcr.io/example/legacy-runtime:1.0",
                        "status": "running",
                    },
                    "legacy_project": {
                        "control_plane": "onepanel-compose",
                        "container_name": "legacy-project-prod",
                        "image": "ghcr.io/example/legacy-project:1.0",
                        "status": "running",
                    },
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (root / "secrets" / "ssh").mkdir(parents=True, exist_ok=True)
    (root / "secrets" / "ssh" / "config").write_text("Host prod0-main\n", encoding="utf-8")


class _FakeCloudflareClient:
    def __init__(self, token: str) -> None:
        self.token = token

    def find_dns_record(self, *, zone_name: str, record_name: str, record_type: str) -> dict[str, object] | None:
        return {
            "id": "rec-1",
            "name": record_name,
            "type": record_type,
            "content": "198.51.100.20",
            "proxied": False,
        }

    def ensure_dns_record(
        self,
        *,
        zone_name: str,
        record_name: str,
        record_type: str,
        content: str,
        proxied: bool,
    ) -> dict[str, object]:
        return {
            "action": "created",
            "changed": True,
            "record": {
                "id": "rec-1",
                "name": record_name,
                "type": record_type,
                "content": content,
                "proxied": proxied,
            },
        }
    def verify_account_token(self, account_id: str) -> dict[str, object]:
        return {"id": "token-1", "status": "active"}
