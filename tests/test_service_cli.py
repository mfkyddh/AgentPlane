import json
import os
import subprocess
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
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
  emit_container "1panel-openresty-prod" "1panel/openresty:1.27.1.2-5-1-focal" "running" "host"
  exit 0
fi
if [[ "$cmd" == *"docker inspect newapi-prod --format"* ]]; then
  emit_container "newapi-prod" "ghcr.io/example/newapi:2026.04" "running" "bridge" ',"NetworkSettings":{"Ports":{"3000/tcp":[{"HostIp":"127.0.0.1","HostPort":"3000"}]}}'
  exit 0
fi
if [[ "$cmd" == *"docker inspect relay-trojan-prod --format"* ]]; then
  emit_container "relay-trojan-prod" "ghcr.io/xtls/xray-core:25.3.6" "running" "bridge" ',"NetworkSettings":{"Ports":{"24443/tcp":[{"HostIp":"0.0.0.0","HostPort":"24443"}]}}'
  exit 0
fi
if [[ "$cmd" == *"docker inspect relay-trojan-host-prod --format"* ]]; then
  emit_container "relay-trojan-host-prod" "ghcr.io/xtls/xray-core:25.3.6" "running" "host"
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
if [[ "$cmd" == *"docker restart newapi-prod"* ]]; then
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
if [[ "$cmd" == *"cd /opt/agentplane/infra/compose/newapi && docker compose -f docker-compose.prod0.yml up -d"* ]]; then
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
                        "network_mode": "host",
                        "listen_ports": [8443],
                    },
                    "newapi": {
                        "control_plane": "compose",
                        "container_name": "newapi-prod",
                        "image": "ghcr.io/example/newapi:2026.04",
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
                        "domain": "relay.zzzai.fun",
                        "port": 24443,
                        "protocol": "trojan",
                        "transport": "tcp+tls",
                        "cloudflare_proxy": False,
                        "dns": {
                            "provider": "cloudflare",
                            "zone_name": "zzzai.fun",
                            "record_type": "A",
                            "record_content": "38.12.32.94",
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
                        "sni": "relay.zzzai.fun",
                    },
                },
                "relay-trojan-host": {
                    "control_plane": "compose",
                    "container_name": "relay-trojan-host-prod",
                    "image": "ghcr.io/xtls/xray-core:25.3.6",
                    "status": "running",
                    "host_binding": "0.0.0.0:24444",
                    "network_mode": "host",
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
            "content": "38.12.32.94",
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


class ServiceCliTests(unittest.TestCase):
    def test_service_search_lists_formal_managed_services(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)

            result = run_cli("service", "search", "--target", "prod0-main", "--repo-root", str(root))

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("service", payload["command"])
            self.assertEqual("search", payload["action"])
            self.assertEqual("prod0-main", payload["target"])
            names = {item["name"] for item in payload["payload"]["items"]}
            self.assertEqual(
                {
                    "postgres",
                    "redis",
                    "minio",
                    "mihomo",
                    "onepanel_openresty",
                    "newapi",
                    "relay-trojan",
                    "relay-trojan-host",
                    "legacy_runtime",
                    "legacy_project",
                },
                names,
            )

    def test_service_get_returns_declared_shape_and_supported_operations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            bin_dir = root / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            log_file = root / "service-get.log"
            write_fake_service_ssh(bin_dir)

            result = run_cli(
                "service",
                "get",
                "--target",
                "prod0-main",
                "--name",
                "postgres",
                "--repo-root",
                str(root),
                env_overrides={"PATH": f"{bin_dir}:{os.environ['PATH']}", "FAKE_CMD_LOG": str(log_file)},
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("service", payload["command"])
            self.assertEqual("get", payload["action"])
            self.assertEqual("postgres", payload["payload"]["service"]["name"])
            self.assertIn("restart", payload["payload"]["service"]["supported_operations"])
            self.assertIn("reconcile", payload["payload"]["service"]["supported_operations"])

    def test_service_get_supports_dynamic_compose_service_with_reconcile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            bin_dir = root / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            log_file = root / "service-get-newapi.log"
            write_fake_service_ssh(bin_dir)

            result = run_cli(
                "service",
                "get",
                "--target",
                "prod0-main",
                "--name",
                "newapi",
                "--repo-root",
                str(root),
                env_overrides={"PATH": f"{bin_dir}:{os.environ['PATH']}", "FAKE_CMD_LOG": str(log_file)},
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("newapi", payload["payload"]["service"]["name"])
            self.assertEqual("compose", payload["payload"]["service"]["control_plane"])
            self.assertEqual(["restart", "reconcile"], payload["payload"]["service"]["supported_operations"])

    def test_service_get_and_verify_relay_trojan_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            bin_dir = root / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            get_log = root / "service-get-relay-trojan.log"
            verify_log = root / "service-verify-relay-trojan.log"
            write_fake_service_ssh(bin_dir)

            get_result = run_cli(
                "service",
                "get",
                "--target",
                "prod0-main",
                "--name",
                "relay-trojan",
                "--repo-root",
                str(root),
                env_overrides={"PATH": f"{bin_dir}:{os.environ['PATH']}", "FAKE_CMD_LOG": str(get_log)},
            )

            self.assertEqual(get_result.returncode, 0, msg=get_result.stderr)
            payload = json.loads(get_result.stdout)
            self.assertEqual("relay-trojan", payload["payload"]["service"]["name"])
            declared = payload["payload"]["service"]["declared"]
            self.assertEqual("0.0.0.0:24443", declared["host_binding"])
            endpoint = declared["public_endpoint"]
            self.assertEqual("relay.zzzai.fun", endpoint["domain"])

            verify_result = run_cli(
                "service",
                "verify",
                "--target",
                "prod0-main",
                "--name",
                "relay-trojan",
                "--repo-root",
                str(root),
                env_overrides={"PATH": f"{bin_dir}:{os.environ['PATH']}", "FAKE_CMD_LOG": str(verify_log)},
            )

            self.assertEqual(verify_result.returncode, 0, msg=verify_result.stderr)
            verify_payload = json.loads(verify_result.stdout)
            host_binding_check = verify_payload["payload"]["checks"]["host_binding"]
            self.assertTrue(host_binding_check["ok"])

    def test_service_verify_allows_host_network_without_ports_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            bin_dir = root / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            log_file = root / "service-verify-relay-trojan-host.log"
            write_fake_service_ssh(bin_dir)

            result = run_cli(
                "service",
                "verify",
                "--target",
                "prod0-main",
                "--name",
                "relay-trojan-host",
                "--repo-root",
                str(root),
                env_overrides={"PATH": f"{bin_dir}:{os.environ['PATH']}", "FAKE_CMD_LOG": str(log_file)},
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            host_binding_check = payload["payload"]["checks"]["host_binding"]
            self.assertTrue(host_binding_check["ok"])
            self.assertEqual("host", payload["payload"]["checks"]["network_mode"]["actual"])

    def test_service_materialize_renders_relay_clash_profile_from_service_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            source_file = root / "source.yaml"
            merge_file = root / "merge.yaml"
            output_file = root / "relay-local.yaml"
            source_file.write_text(
                yaml.safe_dump(
                    {
                        "proxies": [
                            {"name": "旧节点A", "type": "ss", "server": "a.example.com", "port": 443, "cipher": "aes-128-gcm", "password": "x"},
                            {"name": "旧节点B", "type": "ss", "server": "b.example.com", "port": 443, "cipher": "aes-128-gcm", "password": "y"},
                        ],
                        "proxy-groups": [
                            {"name": "国外流量", "type": "select", "proxies": ["旧节点A", "旧节点B", "直接连接"]},
                            {"name": "GPT", "type": "select", "proxies": ["国外流量", "旧节点A", "DIRECT"]},
                        ],
                        "rules": ["DOMAIN-SUFFIX,openai.com,GPT", "MATCH,国外流量"],
                    },
                    allow_unicode=True,
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
            merge_file.write_text(
                yaml.safe_dump(
                    {"prepend__rules": ["DOMAIN-SUFFIX,zzzai.fun,DIRECT"]},
                    allow_unicode=True,
                    sort_keys=False,
                ),
                encoding="utf-8",
            )

            result = run_cli(
                "service",
                "materialize",
                "--target",
                "prod0-main",
                "--name",
                "relay-trojan",
                "--artifact",
                "clash-local-profile",
                "--source",
                str(source_file),
                "--merge-template",
                str(merge_file),
                "--output",
                str(output_file),
                "--password",
                "test-password",
                "--repo-root",
                str(root),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("service", payload["command"])
            self.assertEqual("materialize", payload["action"])
            self.assertEqual("clash-local-profile", payload["payload"]["artifact"])
            self.assertEqual("relay.zzzai.fun", payload["payload"]["resolved"]["server"])
            self.assertEqual(24443, payload["payload"]["resolved"]["port"])
            self.assertEqual("Prod2|Relay", payload["payload"]["resolved"]["node_name"])

            rendered = yaml.safe_load(output_file.read_text(encoding="utf-8"))
            self.assertEqual("Prod2|Relay", rendered["proxies"][0]["name"])
            self.assertEqual("relay.zzzai.fun", rendered["proxies"][0]["server"])
            self.assertEqual(["Prod2|Relay", "直接连接"], rendered["proxy-groups"][0]["proxies"])
            self.assertEqual(
                ["DOMAIN-SUFFIX,zzzai.fun,DIRECT", "DOMAIN-SUFFIX,openai.com,GPT", "MATCH,国外流量"],
                rendered["rules"],
            )

    def test_service_public_endpoint_verify_checks_dns_and_certificate_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            bin_dir = root / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            log_file = root / "service-public-endpoint-verify.log"
            env_file = root / "cloudflare.env"
            env_file.write_text("CLOUDFLARE_API_TOKEN=test-token\n", encoding="utf-8")
            write_fake_service_ssh(bin_dir)

            with patch("agentplane.domain.service.public_endpoint.CloudflareClient", _FakeCloudflareClient), patch.dict(
                os.environ,
                {"PATH": f"{bin_dir}:{os.environ['PATH']}", "FAKE_CMD_LOG": str(log_file)},
                clear=False,
            ):
                exit_code, stdout, stderr = run_cli_inline(
                    "service",
                    "public-endpoint",
                    "verify",
                    "--target",
                    "prod0-main",
                    "--name",
                    "relay-trojan",
                    "--cloudflare-env-file",
                    str(env_file),
                    "--repo-root",
                    str(root),
                )

            self.assertEqual(exit_code, 0, msg=stderr)
            payload = json.loads(stdout)
            self.assertEqual("public-endpoint.verify", payload["action"])
            self.assertTrue(payload["payload"]["ok"])
            self.assertTrue(payload["payload"]["checks"]["dns_exists"]["ok"])
            self.assertTrue(payload["payload"]["checks"]["dns_content"]["ok"])
            self.assertTrue(payload["payload"]["checks"]["cert_fullchain_readable"]["ok"])
            self.assertTrue(payload["payload"]["checks"]["cert_privkey_readable"]["ok"])
            self.assertTrue(payload["payload"]["checks"]["renew_script_executable"]["ok"])
            self.assertTrue(payload["payload"]["checks"]["renew_cron_present"]["ok"])

    def test_service_public_endpoint_plan_and_apply_reconcile_dns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            env_file = root / "cloudflare.env"
            env_file.write_text("CLOUDFLARE_API_TOKEN=test-token\n", encoding="utf-8")

            plan_result = run_cli(
                "service",
                "public-endpoint",
                "plan",
                "--target",
                "prod0-main",
                "--name",
                "relay-trojan",
                "--cloudflare-env-file",
                str(env_file),
                "--repo-root",
                str(root),
            )

            self.assertEqual(plan_result.returncode, 0, msg=plan_result.stderr)
            plan_payload = json.loads(plan_result.stdout)
            self.assertEqual("public-endpoint.plan", plan_payload["action"])
            self.assertEqual("reconcile", plan_payload["payload"]["operation"])
            step = plan_payload["payload"]["steps"][0]
            self.assertIn("ensure_cloudflare_dns_record.py", step["display"])
            self.assertIn("relay.zzzai.fun", step["display"])

            bin_dir = root / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            log_file = root / "service-public-endpoint-apply.log"
            write_fake_service_ssh(bin_dir)
            with patch("agentplane.domain.service.public_endpoint.CloudflareClient", _FakeCloudflareClient), patch(
                "agentplane.scripts.internal.ensure_cloudflare_dns_record.CloudflareClient",
                _FakeCloudflareClient,
            ), patch.dict(
                os.environ,
                {"PATH": f"{bin_dir}:{os.environ['PATH']}", "FAKE_CMD_LOG": str(log_file)},
                clear=False,
            ):
                exit_code, stdout, stderr = run_cli_inline(
                    "service",
                    "public-endpoint",
                    "apply",
                    "--target",
                    "prod0-main",
                    "--name",
                    "relay-trojan",
                    "--cloudflare-env-file",
                    str(env_file),
                    "--execute",
                    "--repo-root",
                    str(root),
                )

            self.assertEqual(exit_code, 0, msg=stderr)
            apply_payload = json.loads(stdout)
            self.assertEqual("public-endpoint.apply", apply_payload["action"])
            self.assertTrue(apply_payload["payload"]["ok"])
            self.assertEqual("created", apply_payload["payload"]["results"][0]["parsed"]["action"])
            self.assertTrue(apply_payload["payload"]["verified"]["ok"])

    def test_service_get_supports_onepanel_backed_runtime_with_restart_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            bin_dir = root / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            log_file = root / "service-get-legacy-runtime.log"
            write_fake_service_ssh(bin_dir)

            result = run_cli(
                "service",
                "get",
                "--target",
                "prod0-main",
                "--name",
                "legacy_runtime",
                "--repo-root",
                str(root),
                env_overrides={"PATH": f"{bin_dir}:{os.environ['PATH']}", "FAKE_CMD_LOG": str(log_file)},
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("legacy_runtime", payload["payload"]["service"]["name"])
            self.assertEqual("onepanel-app", payload["payload"]["service"]["control_plane"])
            self.assertEqual(["restart"], payload["payload"]["service"]["supported_operations"])

    def test_service_verify_checks_live_state_for_container_service(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            bin_dir = root / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            log_file = root / "service-verify.log"
            write_fake_service_ssh(bin_dir)

            result = run_cli(
                "service",
                "verify",
                "--target",
                "prod0-main",
                "--name",
                "onepanel_openresty",
                "--repo-root",
                str(root),
                env_overrides={"PATH": f"{bin_dir}:{os.environ['PATH']}", "FAKE_CMD_LOG": str(log_file)},
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("service", payload["command"])
            self.assertEqual("verify", payload["action"])
            self.assertTrue(payload["payload"]["ok"])
            self.assertEqual("host", payload["payload"]["checks"]["network_mode"]["actual"])
            self.assertFalse(payload["payload"]["projection_handoff"]["required"])
            self.assertEqual("projection", payload["payload"]["projection_handoff"]["steps"][0]["command"])
            self.assertEqual("ledger.refresh", payload["payload"]["projection_handoff"]["steps"][0]["action"])

    def test_service_plan_rejects_unsupported_operation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)

            result = run_cli(
                "service",
                "plan",
                "--target",
                "prod0-main",
                "--name",
                "postgres",
                "--operation",
                "reload",
                "--repo-root",
                str(root),
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unsupported", result.stderr.lower())

    def test_service_plan_rejects_reconcile_for_onepanel_app_service(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)

            result = run_cli(
                "service",
                "plan",
                "--target",
                "prod0-main",
                "--name",
                "legacy_runtime",
                "--operation",
                "reconcile",
                "--repo-root",
                str(root),
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unsupported", result.stderr.lower())

    def test_service_apply_restarts_systemd_service_and_verifies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            bin_dir = root / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            log_file = root / "service-apply-mihomo.log"
            write_fake_service_ssh(bin_dir)

            result = run_cli(
                "service",
                "apply",
                "--target",
                "prod0-main",
                "--name",
                "mihomo",
                "--operation",
                "restart",
                "--execute",
                "--repo-root",
                str(root),
                env_overrides={"PATH": f"{bin_dir}:{os.environ['PATH']}", "FAKE_CMD_LOG": str(log_file)},
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            plan = json.loads(
                run_cli(
                    "service",
                    "plan",
                    "--target",
                    "prod0-main",
                    "--name",
                    "mihomo",
                    "--operation",
                    "restart",
                    "--repo-root",
                    str(root),
                ).stdout
            )
            self.assertEqual("service", payload["command"])
            self.assertEqual("apply", payload["action"])
            self.assertTrue(payload["payload"]["ok"])
            self.assertTrue(payload["payload"]["verified"]["ok"])
            self.assertEqual(
                plan["payload"]["steps"][0]["argv"],
                payload["payload"]["results"][0]["argv"],
            )
            log_text = log_file.read_text(encoding="utf-8")
            self.assertIn("systemctl restart mihomo", log_text)
            self.assertIn("systemctl is-active mihomo", log_text)

    def test_service_apply_reconcile_uses_remote_compose_path_and_verifies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            bin_dir = root / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            log_file = root / "service-apply-postgres.log"
            write_fake_service_ssh(bin_dir)

            result = run_cli(
                "service",
                "apply",
                "--target",
                "prod0-main",
                "--name",
                "postgres",
                "--operation",
                "reconcile",
                "--execute",
                "--repo-root",
                str(root),
                env_overrides={"PATH": f"{bin_dir}:{os.environ['PATH']}", "FAKE_CMD_LOG": str(log_file)},
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            plan = json.loads(
                run_cli(
                    "service",
                    "plan",
                    "--target",
                    "prod0-main",
                    "--name",
                    "postgres",
                    "--operation",
                    "reconcile",
                    "--repo-root",
                    str(root),
                ).stdout
            )
            self.assertTrue(payload["payload"]["ok"])
            self.assertTrue(payload["payload"]["verified"]["ok"])
            self.assertEqual(
                plan["payload"]["steps"][0]["argv"],
                payload["payload"]["results"][0]["argv"],
            )
            self.assertTrue(plan["payload"]["projection_handoff"]["required"])
            self.assertTrue(payload["payload"]["projection_handoff"]["required"])
            self.assertEqual("projection", payload["payload"]["projection_handoff"]["steps"][0]["command"])
            self.assertEqual("ledger.refresh", payload["payload"]["projection_handoff"]["steps"][0]["action"])
            log_text = log_file.read_text(encoding="utf-8")
            self.assertIn("cd /opt/agentplane/infra/compose/postgres && docker compose -f docker-compose.prod0.yml up -d", log_text)
            self.assertIn("docker inspect postgres18-prod", log_text)


if __name__ == "__main__":
    unittest.main()
