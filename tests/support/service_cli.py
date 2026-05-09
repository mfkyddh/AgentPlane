import json
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from tests.support.cli import run_agentplane_cli
from tests.support.constants import (
    CONTAINER_MINIO,
    CONTAINER_OPENRESTY,
    CONTAINER_POSTGRES,
    CONTAINER_REDIS,
    DOMAIN_RELAY,
    FAKE_BINDING_3000,
    IP_CLOUDFLARE_RECORD,
    TARGET_PROD,
)
from tests.support.fake_scripts import write_fake_command, write_fake_service_ssh  # noqa: F401
from tests.support.paths import REPO_ROOT

run_cli = run_agentplane_cli

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agentplane.cli.app import main as cli_main  # noqa: E402


def run_cli_inline(*args: str) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()
    with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
        exit_code = cli_main(list(args))
    return exit_code, stdout.getvalue(), stderr.getvalue()


def write_inventory(root: Path) -> None:
    (root / "inventory" / "servers" / TARGET_PROD).mkdir(parents=True, exist_ok=True)
    (root / "inventory" / "servers" / TARGET_PROD / "inventory.json").write_text(
        json.dumps(
            {
                "ssh": {"aliases": [TARGET_PROD], "user": "root"},
                "services": {
                    "postgres": {
                        "image": "postgres:18.3",
                        "container_name": CONTAINER_POSTGRES,
                        "status": "running",
                        "host_binding": "0.0.0.0:5432",
                        "data_dir": "/data/postgres/data",
                    },
                    "redis": {
                        "image": "redis:7.4.7",
                        "container_name": CONTAINER_REDIS,
                        "status": "running",
                        "host_binding": "0.0.0.0:6379",
                        "data_dir": "/data/redis/data",
                    },
                    "minio": {
                        "image": "minio/minio:RELEASE.2025-04-22T22-12-26Z",
                        "container_name": CONTAINER_MINIO,
                        "status": "running",
                        "host_bindings": ["0.0.0.0:9000", "0.0.0.0:9001"],
                        "data_dir": "/data/minio/data",
                        "config_dir": "/data/minio/config",
                    },
                    "onepanel_openresty": {
                        "container_name": CONTAINER_OPENRESTY,
                        "status": "running",
                        "network_mode": "infra",
                        "listen_ports": [8443],
                    },
                    "sampleapi": {
                        "control_plane": "compose",
                        "container_name": "sampleapi-prod",
                        "project_name": "sampleapi",
                        "compose_file": "/opt/agentplane/infra/compose/sampleapi/docker-compose.prod0.yml",
                        "image": "ghcr.io/example/sampleapi:2026.04",
                        "status": "running",
                        "host_binding": FAKE_BINDING_3000,
                    },
                    "relay-trojan": {
                        "control_plane": "compose",
                        "container_name": "relay-trojan-prod",
                        "image": "ghcr.io/xtls/xray-core:25.3.6",
                        "status": "running",
                        "host_binding": "0.0.0.0:24443",
                        "runtime_root": "/data/relay-trojan",
                        "public_endpoint": {
                            "domain": DOMAIN_RELAY,
                            "port": 24443,
                            "protocol": "trojan",
                            "transport": "tcp+tls",
                            "cloudflare_proxy": False,
                            "dns": {
                                "provider": "cloudflare",
                                "zone_name": "example.org",
                                "record_type": "A",
                                "record_content": IP_CLOUDFLARE_RECORD,
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
                            "sni": DOMAIN_RELAY,
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
                        "project_name": "legacy-project-prod",
                        "compose_file": "/data/1panel/docker/compose/legacy-project-prod/docker-compose.yml",
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
    (root / "secrets" / "ssh" / "config").write_text(f"Host {TARGET_PROD}\n", encoding="utf-8")


class _FakeCloudflareClient:
    def __init__(self, token: str) -> None:
        self.token = token

    def find_dns_record(self, *, zone_name: str, record_name: str, record_type: str) -> dict[str, object] | None:
        return {
            "id": "rec-1",
            "name": record_name,
            "type": record_type,
            "content": IP_CLOUDFLARE_RECORD,
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
