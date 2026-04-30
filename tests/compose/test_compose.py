from __future__ import annotations

import json
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from agentplane.domain.service.materialize import render_clash_local_profile
from agentplane.scripts.internal import ensure_cloudflare_dns_record  # type: ignore  # noqa: E402

pytestmark = pytest.mark.e2e

from tests.support.paths import REPO_ROOT
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

class _FakeCloudflareClient:
    def __init__(self, token: str) -> None:
        self.token = token
        self.calls: list[dict[str, object]] = []

    def ensure_dns_record(
        self,
        *,
        zone_name: str,
        record_name: str,
        record_type: str,
        content: str,
        proxied: bool,
    ) -> dict[str, object]:
        self.calls.append(
            {
                "zone_name": zone_name,
                "record_name": record_name,
                "record_type": record_type,
                "content": content,
                "proxied": proxied,
            }
        )
        return {
            "action": "unchanged",
            "changed": False,
            "record": {
                "id": "rec-1",
                "name": record_name,
                "type": record_type,
                "content": content,
                "proxied": proxied,
            },
        }

class RelayTrojanDnsCliTests(unittest.TestCase):
    def test_cli_supports_prod2_relay_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / "cloudflare.env"
            env_file.write_text("export CLOUDFLARE_API_TOKEN=test-token\n", encoding="utf-8")
            stdout = StringIO()

            with patch.object(ensure_cloudflare_dns_record, "CloudflareClient", _FakeCloudflareClient), patch("sys.stdout", stdout):
                exit_code = ensure_cloudflare_dns_record.main(
                    [
                        "--cloudflare-env-file",
                        str(env_file),
                        "--zone-name",
                        "example.org",
                        "--record-name",
                        "relay.example.org",
                        "--record-content",
                        "198.51.100.20",
                    ]
                )

        self.assertEqual(0, exit_code)
        payload = json.loads(stdout.getvalue())
        self.assertTrue(payload["ok"])
        self.assertEqual("example.org", payload["zone_name"])
        self.assertEqual("relay.example.org", payload["record_name"])
        self.assertEqual("A", payload["record_type"])
        self.assertEqual("198.51.100.20", payload["record_content"])
        self.assertFalse(payload["proxied"])
        self.assertEqual("unchanged", payload["action"])

    def test_cli_supports_overrides_and_proxied_true(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / "cloudflare.env"
            env_file.write_text("CLOUDFLARE_API_TOKEN=another-token\n", encoding="utf-8")
            stdout = StringIO()

            with patch.object(ensure_cloudflare_dns_record, "CloudflareClient", _FakeCloudflareClient), patch("sys.stdout", stdout):
                exit_code = ensure_cloudflare_dns_record.main(
                    [
                        "--cloudflare-env-file",
                        str(env_file),
                        "--zone-name",
                        "example.com",
                        "--record-name",
                        "relay.example.com",
                        "--record-type",
                        "AAAA",
                        "--record-content",
                        "2001:db8::1",
                        "--proxied",
                        "true",
                    ]
                )

        self.assertEqual(0, exit_code)
        payload = json.loads(stdout.getvalue())
        self.assertEqual("example.com", payload["zone_name"])
        self.assertEqual("relay.example.com", payload["record_name"])
        self.assertEqual("AAAA", payload["record_type"])
        self.assertEqual("2001:db8::1", payload["record_content"])
        self.assertTrue(payload["proxied"])
        self.assertEqual("unchanged", payload["action"])

# ======================================================================
# From: test_relay_trojan_profile_renderer.py
# ======================================================================

class RelayTrojanProfileRendererTests(unittest.TestCase):
    def test_render_profile_keeps_effective_rules_and_rewrites_proxy_sets(self) -> None:
        source = {
            "mode": "rule",
            "proxies": [
                {"name": "旧节点A", "type": "ss", "server": "a.example.com", "port": 443, "cipher": "aes-128-gcm", "password": "x"},
                {"name": "旧节点B", "type": "ss", "server": "b.example.com", "port": 443, "cipher": "aes-128-gcm", "password": "y"},
            ],
            "proxy-groups": [
                {"name": "国外流量", "type": "select", "proxies": ["旧节点A", "旧节点B", "直接连接"]},
                {"name": "GPT", "type": "select", "proxies": ["国外流量", "旧节点A", "直接连接"]},
                {"name": "Steam_API", "type": "select", "proxies": ["国外流量", "DIRECT", "旧节点B"]},
            ],
            "rules": ["DOMAIN-SUFFIX,openai.com,GPT", "MATCH,国外流量"],
        }
        merge = {
            "prepend__rules": [
                "DOMAIN-SUFFIX,example.org,DIRECT",
                "DOMAIN-SUFFIX,cloudflare.com,GPT",
            ]
        }

        rendered = render_clash_local_profile(
            source,
            merge_template=merge,
            node_name="Prod2|Relay",
            server="relay.example.org",
            port=24443,
            password="test-password",
            sni="relay.example.org",
        )

        self.assertEqual(
            {
                "name": "Prod2|Relay",
                "type": "trojan",
                "server": "relay.example.org",
                "port": 24443,
                "password": "test-password",
                "sni": "relay.example.org",
                "udp": True,
                "skip-cert-verify": False,
            },
            rendered["proxies"][0],
        )
        self.assertEqual(["Prod2|Relay", "直接连接"], rendered["proxy-groups"][0]["proxies"])
        self.assertEqual(["国外流量", "Prod2|Relay", "直接连接"], rendered["proxy-groups"][1]["proxies"])
        self.assertEqual(["国外流量", "DIRECT", "Prod2|Relay"], rendered["proxy-groups"][2]["proxies"])
        self.assertEqual(
            [
                "DOMAIN-SUFFIX,example.org,DIRECT",
                "DOMAIN-SUFFIX,cloudflare.com,GPT",
                "DOMAIN-SUFFIX,openai.com,GPT",
                "MATCH,国外流量",
            ],
            rendered["rules"],
        )

# ======================================================================
# From: test_sub2api_compose_layout.py
# ======================================================================

OFFICIAL_IMAGE = "${SUB2API_IMAGE_REF:-ghcr.io/wei-shaw/sub2api:latest}"


def load_compose(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


class Sub2ApiComposeLayoutTests(unittest.TestCase):
    def test_wsl_template_matches_contract(self) -> None:
        compose = load_compose(REPO_ROOT / "infra" / "compose" / "sub2api" / "docker-compose.wsl.yml")
        service = compose["services"]["sub2api"]

        self.assertEqual(OFFICIAL_IMAGE, service["image"])
        self.assertEqual("always", service["pull_policy"])
        self.assertEqual("sub2api-dev", service["container_name"])
        self.assertIn("0.0.0.0:18080:8080", service["ports"])
        self.assertIn("/data/sub2api/data:/app/data", service["volumes"])
        self.assertEqual(["zqf_network"], service["networks"])

    def test_wsl_env_template_uses_isolated_database(self) -> None:
        env_template = (REPO_ROOT / "templates" / "services" / "sub2api.wsl.env.example").read_text(encoding="utf-8")

        self.assertIn("DATABASE_USER=sub2api_wsl", env_template)
        self.assertIn("DATABASE_DBNAME=sub2api_wsl", env_template)
        self.assertIn("REDIS_DB=1", env_template)
        self.assertIn("REDIS_PASSWORD=<redis_password>", env_template)
