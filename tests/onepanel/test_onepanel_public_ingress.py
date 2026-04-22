import argparse
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
ONEPANEL_SCRIPTS = REPO_ROOT / "agentplane" / "scripts" / "onepanel"
if str(ONEPANEL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(ONEPANEL_SCRIPTS))

from agentplane.scripts.onepanel import public_ingress  # type: ignore  # noqa: E402


class FakeCloudflareClient(public_ingress.CloudflareClient):
    def __init__(self, responses: list[dict[str, object]]) -> None:
        super().__init__("dummy-token")
        self.responses = responses
        self.calls: list[tuple[str, str, dict[str, object] | None, dict[str, object] | None]] = []

    def request(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, object] | None = None,
        body: dict[str, object] | None = None,
    ) -> dict[str, object]:
        self.calls.append((method, path, query, body))
        return self.responses.pop(0)


class FakePanelExecutor:
    def __init__(self) -> None:
        self.requests: list[tuple[str, str, dict[str, object] | None]] = []

    def request(self, method: str, path: str, body: dict[str, object] | None = None) -> object:
        self.requests.append((method, path, body))
        if path == "/api/v2/websites/acme/search":
            return {"items": [{"id": 1, "email": "acme@1paneldev.com", "type": "letsencrypt"}]}
        if path == "/api/v2/websites/dns/search":
            return {"items": [{"id": 2, "name": "cloudflare-zzzai", "type": "CloudFlare"}]}
        if path == "/api/v2/websites/ssl/search":
            return {
                "items": [
                    {
                        "id": 3,
                        "primaryDomain": "1panel.zzzai.fun",
                        "status": "ready",
                        "dir": "/data/1panel/www/certs/1panel-zzzai-fun",
                        "autoRenew": True,
                    }
                ]
            }
        if path == "/api/v2/websites/search":
            return {
                "items": [
                    {
                        "id": 4,
                        "alias": "1panel",
                        "primaryDomain": "1panel.zzzai.fun",
                        "status": "Running",
                        "proxy": "http://127.0.0.1:2096",
                    }
                ]
            }
        if path == "/api/v2/websites/4/https":
            return {
                "enable": True,
                "httpConfig": "HTTPAlso",
                "httpsPort": "443",
                "SSL": {"id": 3},
            }
        raise AssertionError(f"Unexpected request: {method} {path}")


class CreatingPanelExecutor(FakePanelExecutor):
    def __init__(self) -> None:
        super().__init__()
        self.website_created = False

    def request(self, method: str, path: str, body: dict[str, object] | None = None) -> object:
        self.requests.append((method, path, body))
        if path == "/api/v2/websites/acme/search":
            return {"items": [{"id": 1, "email": "acme@1paneldev.com", "type": "letsencrypt"}]}
        if path == "/api/v2/websites/dns/search":
            return {"items": [{"id": 2, "name": "cloudflare-zzzai", "type": "CloudFlare"}]}
        if path == "/api/v2/websites/ssl/search":
            return {
                "items": [
                    {
                        "id": 3,
                        "primaryDomain": "token.zzzai.fun",
                        "status": "ready",
                        "dir": "/data/1panel/www/certs/token-zzzai-fun",
                        "autoRenew": True,
                    }
                ]
            }
        if path == "/api/v2/websites/search":
            if self.website_created:
                return {
                    "items": [
                        {
                            "id": 5,
                            "alias": "token",
                            "primaryDomain": "token.zzzai.fun",
                            "status": "Running",
                            "proxy": "http://127.0.0.1:18080",
                        }
                    ]
                }
            return {"items": []}
        if path == "/api/v2/websites":
            self.website_created = True
            return {"id": 5}
        if path == "/api/v2/websites/5/https":
            return {
                "enable": True,
                "httpConfig": "HTTPAlso",
                "httpsPort": "443",
                "SSL": {"id": 3},
            }
        raise AssertionError(f"Unexpected request: {method} {path}")


class OnePanelPublicIngressTests(unittest.TestCase):
    def test_load_shell_env_file_supports_export_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / "prod-jump.env"
            env_file.write_text(
                "export CLOUDFLARE_API_TOKEN=test-token\nCLOUDFLARE_ACCOUNT_ID=test-account\n",
                encoding="utf-8",
            )

            values = public_ingress.load_shell_env_file(env_file)

            self.assertEqual("test-token", values["CLOUDFLARE_API_TOKEN"])
            self.assertEqual("test-account", values["CLOUDFLARE_ACCOUNT_ID"])

    def test_public_ingress_config_parses_expected_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / "ingress.env"
            env_file.write_text(
                "\n".join(
                    [
                        "PUBLIC_INGRESS_DOMAIN=1panel.zzzai.fun",
                        "PUBLIC_INGRESS_ZONE_NAME=zzzai.fun",
                        "PUBLIC_INGRESS_RECORD_TYPE=A",
                        "PUBLIC_INGRESS_RECORD_CONTENT=38.12.32.94",
                        "PUBLIC_INGRESS_RECORD_PROXIED=true",
                        "ONEPANEL_DNS_ACCOUNT_NAME=cloudflare-zzzai",
                        "ONEPANEL_DNS_ACCOUNT_PROVIDER=CloudFlare",
                        "ONEPANEL_DNS_ACCOUNT_EMAIL=admin@zzzai.cloud",
                        "ONEPANEL_ACME_EMAIL=acme@1paneldev.com",
                        "ONEPANEL_WEBSITE_ALIAS=1panel",
                        "ONEPANEL_WEBSITE_PROXY=http://127.0.0.1:2096",
                        "ONEPANEL_CERT_DIR=/data/1panel/www/certs/1panel-zzzai-fun",
                        "ONEPANEL_CERT_RELOAD_SHELL=docker exec 1panel-openresty-prod nginx -t && docker exec 1panel-openresty-prod nginx -s reload",
                        "ONEPANEL_HTTPS_PORTS=443,8443",
                    ]
                ),
                encoding="utf-8",
            )

            config = public_ingress.PublicIngressConfig.from_env_file(env_file)

            self.assertEqual("1panel.zzzai.fun", config.domain)
            self.assertTrue(config.record_proxied)
            self.assertEqual([443, 8443], config.https_ports)
            self.assertEqual("cloudflare-zzzai", config.dns_account_name)

    def test_cloudflare_client_creates_record_when_absent(self) -> None:
        client = FakeCloudflareClient(
            [
                {"success": True, "result": [{"id": "zone-1"}]},
                {"success": True, "result": []},
                {"success": True, "result": {"id": "record-1", "name": "1panel.zzzai.fun", "content": "38.12.32.94", "proxied": True}},
            ]
        )

        result = client.ensure_dns_record(
            zone_name="zzzai.fun",
            record_name="1panel.zzzai.fun",
            record_type="A",
            content="38.12.32.94",
            proxied=True,
        )

        self.assertTrue(result["changed"])
        self.assertEqual("created", result["action"])
        self.assertEqual("POST", client.calls[-1][0])

    def test_cloudflare_client_verifies_token_via_account_endpoint(self) -> None:
        client = FakeCloudflareClient(
            [
                {"success": True, "result": {"id": "token-1", "status": "active"}},
            ]
        )

        result = client.verify_account_token("account-1")

        self.assertEqual({"id": "token-1", "status": "active"}, result)
        self.assertEqual(("GET", "/accounts/account-1/tokens/verify", None, None), client.calls[-1])

    @patch.object(public_ingress, "PublicIngressManager")
    @patch.object(public_ingress, "OnePanelExecutor")
    @patch.object(public_ingress, "CloudflareClient")
    def test_command_ensure_public_ingress_verifies_token_before_changes(
        self,
        cloudflare_client_cls,
        panel_cls,
        manager_cls,
    ) -> None:
        cloudflare_client = cloudflare_client_cls.return_value
        cloudflare_client.verify_account_token.return_value = {"id": "token-1", "status": "active"}
        manager = manager_cls.return_value
        manager.ensure.return_value = {"cloudflare_dns": {"action": "unchanged", "changed": False}}

        with tempfile.TemporaryDirectory() as tmp:
            config_file = Path(tmp) / "ingress.env"
            config_file.write_text(
                "\n".join(
                    [
                        "PUBLIC_INGRESS_DOMAIN=1panel.zzzai.fun",
                        "PUBLIC_INGRESS_ZONE_NAME=zzzai.fun",
                        "PUBLIC_INGRESS_RECORD_CONTENT=38.12.32.94",
                        "ONEPANEL_DNS_ACCOUNT_NAME=cloudflare-zzzai",
                        "ONEPANEL_DNS_ACCOUNT_EMAIL=admin@zzzai.cloud",
                        "ONEPANEL_WEBSITE_ALIAS=1panel",
                        "ONEPANEL_WEBSITE_PROXY=http://127.0.0.1:2096",
                        "ONEPANEL_CERT_DIR=/data/1panel/www/certs/1panel-zzzai-fun",
                        "ONEPANEL_CERT_RELOAD_SHELL=echo reload",
                    ]
                ),
                encoding="utf-8",
            )
            cloudflare_env_file = Path(tmp) / "prod-jump.env"
            cloudflare_env_file.write_text(
                "export CLOUDFLARE_API_TOKEN=test-token\nexport CLOUDFLARE_ACCOUNT_ID=test-account\n",
                encoding="utf-8",
            )

            result = public_ingress.command_ensure_public_ingress(
                argparse.Namespace(
                    env="prod0-main",
                    env_file=None,
                    config_file=str(config_file),
                    cloudflare_env_file=str(cloudflare_env_file),
                )
            )

        cloudflare_client_cls.assert_called_once_with("test-token")
        cloudflare_client.verify_account_token.assert_called_once_with("test-account")
        manager.ensure.assert_called_once_with()
        self.assertEqual("onepanel public-ingress ensure", result["command"])

    def test_manager_noops_when_everything_already_exists(self) -> None:
        config = public_ingress.PublicIngressConfig(
            domain="1panel.zzzai.fun",
            zone_name="zzzai.fun",
            record_type="A",
            record_content="38.12.32.94",
            record_proxied=True,
            dns_account_name="cloudflare-zzzai",
            dns_account_provider="CloudFlare",
            dns_account_email="admin@zzzai.cloud",
            acme_email="acme@1paneldev.com",
            acme_type="letsencrypt",
            acme_key_type="2048",
            website_alias="1panel",
            website_type="proxy",
            website_group_id=1,
            website_proxy="http://127.0.0.1:2096",
            website_remark="prod2-main 1Panel public ingress",
            website_ipv6=True,
            cert_primary_domain="1panel.zzzai.fun",
            cert_other_domains="",
            cert_dir="/data/1panel/www/certs/1panel-zzzai-fun",
            cert_description="prod2-main 1Panel public ingress",
            cert_key_type="2048",
            cert_auto_renew=True,
            cert_reload_shell="docker exec 1panel-openresty-prod nginx -t && docker exec 1panel-openresty-prod nginx -s reload",
            https_http_config="HTTPAlso",
            https_ports=[443],
        )
        cloudflare = FakeCloudflareClient(
            [
                {"success": True, "result": [{"id": "zone-1"}]},
                {"success": True, "result": [{"id": "record-1", "content": "38.12.32.94", "proxied": True}]},
            ]
        )
        manager = public_ingress.PublicIngressManager(FakePanelExecutor(), cloudflare, config)

        result = manager.ensure()

        self.assertEqual("unchanged", result["cloudflare_dns"]["action"])
        self.assertEqual(3, result["ssl"]["id"])
        self.assertEqual(4, result["website"]["id"])

    def test_manager_creates_new_proxy_website_with_app_type_new(self) -> None:
        config = public_ingress.PublicIngressConfig(
            domain="token.zzzai.fun",
            zone_name="zzzai.fun",
            record_type="A",
            record_content="38.12.32.94",
            record_proxied=True,
            dns_account_name="cloudflare-zzzai",
            dns_account_provider="CloudFlare",
            dns_account_email="admin@zzzai.cloud",
            acme_email="acme@1paneldev.com",
            acme_type="letsencrypt",
            acme_key_type="2048",
            website_alias="token",
            website_type="proxy",
            website_group_id=1,
            website_proxy="http://127.0.0.1:18080",
            website_remark="prod2-main sub2api public ingress",
            website_ipv6=True,
            cert_primary_domain="token.zzzai.fun",
            cert_other_domains="",
            cert_dir="/data/1panel/www/certs/token-zzzai-fun",
            cert_description="prod2-main sub2api public ingress",
            cert_key_type="2048",
            cert_auto_renew=True,
            cert_reload_shell="docker exec 1panel-openresty-prod nginx -t && docker exec 1panel-openresty-prod nginx -s reload",
            https_http_config="HTTPAlso",
            https_ports=[443],
        )
        cloudflare = FakeCloudflareClient(
            [
                {"success": True, "result": [{"id": "zone-1"}]},
                {"success": True, "result": [{"id": "record-1", "content": "38.12.32.94", "proxied": True}]},
            ]
        )
        panel = CreatingPanelExecutor()
        manager = public_ingress.PublicIngressManager(panel, cloudflare, config)

        result = manager.ensure()

        create_request = next(body for method, path, body in panel.requests if method == "POST" and path == "/api/v2/websites")
        self.assertEqual("new", create_request["appType"])
        self.assertEqual("proxy", create_request["type"])
        self.assertEqual([{"domain": "token.zzzai.fun", "port": 80, "ssl": False}], create_request["domains"])
        self.assertEqual(5, result["website"]["id"])


if __name__ == "__main__":
    unittest.main()

