import json
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


from agentplane.scripts.internal import ensure_cloudflare_dns_record  # type: ignore  # noqa: E402


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
                        "zzzai.fun",
                        "--record-name",
                        "relay.zzzai.fun",
                        "--record-content",
                        "38.12.32.94",
                    ]
                )

        self.assertEqual(0, exit_code)
        payload = json.loads(stdout.getvalue())
        self.assertTrue(payload["ok"])
        self.assertEqual("zzzai.fun", payload["zone_name"])
        self.assertEqual("relay.zzzai.fun", payload["record_name"])
        self.assertEqual("A", payload["record_type"])
        self.assertEqual("38.12.32.94", payload["record_content"])
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


if __name__ == "__main__":
    unittest.main()
