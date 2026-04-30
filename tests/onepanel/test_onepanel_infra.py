from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock
from unittest.mock import patch

import pytest
from agentplane.scripts.onepanel import (
    env_targets,  # type: ignore  # noqa: E402
    public_ingress,  # type: ignore  # noqa: E402
)
from agentplane.scripts.onepanel.compose_policy import (  # type: ignore  # noqa: E402
    enforce_zqf_network,
    normalize_compose_for_app,
    requires_host_network,
)
from agentplane.scripts.onepanel.fixture_manager import (
    apply_fixture,
    cleanup_fixture,
    plan_fixture,
    resolve_fixture_spec,
    resolve_suite_targets,
)
from agentplane.scripts.onepanel.verification import run_verification_suite

pytestmark = pytest.mark.e2e

from tests.support.paths import REPO_ROOT

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
ONEPANEL_SCRIPTS = REPO_ROOT / "agentplane" / "scripts" / "onepanel"
if str(ONEPANEL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(ONEPANEL_SCRIPTS))

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
            return {"items": [{"id": 2, "name": "cloudflare-example", "type": "CloudFlare"}]}
        if path == "/api/v2/websites/ssl/search":
            return {
                "items": [
                    {
                        "id": 3,
                        "primaryDomain": "1panel.example.org",
                        "status": "ready",
                        "dir": "/data/1panel/www/certs/1panel-example-org",
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
                        "primaryDomain": "1panel.example.org",
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
            return {"items": [{"id": 2, "name": "cloudflare-example", "type": "CloudFlare"}]}
        if path == "/api/v2/websites/ssl/search":
            return {
                "items": [
                    {
                        "id": 3,
                        "primaryDomain": "token.example.org",
                        "status": "ready",
                        "dir": "/data/1panel/www/certs/token-example-org",
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
                            "primaryDomain": "token.example.org",
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
                        "PUBLIC_INGRESS_DOMAIN=1panel.example.org",
                        "PUBLIC_INGRESS_ZONE_NAME=example.org",
                        "PUBLIC_INGRESS_RECORD_TYPE=A",
                        "PUBLIC_INGRESS_RECORD_CONTENT=198.51.100.20",
                        "PUBLIC_INGRESS_RECORD_PROXIED=true",
                        "ONEPANEL_DNS_ACCOUNT_NAME=cloudflare-example",
                        "ONEPANEL_DNS_ACCOUNT_PROVIDER=CloudFlare",
                        "ONEPANEL_DNS_ACCOUNT_EMAIL=admin@example.net",
                        "ONEPANEL_ACME_EMAIL=acme@1paneldev.com",
                        "ONEPANEL_WEBSITE_ALIAS=1panel",
                        "ONEPANEL_WEBSITE_PROXY=http://127.0.0.1:2096",
                        "ONEPANEL_CERT_DIR=/data/1panel/www/certs/1panel-example-org",
                        "ONEPANEL_CERT_RELOAD_SHELL=docker exec 1panel-openresty-prod nginx -t && docker exec 1panel-openresty-prod nginx -s reload",
                        "ONEPANEL_HTTPS_PORTS=443,8443",
                    ]
                ),
                encoding="utf-8",
            )

            config = public_ingress.PublicIngressConfig.from_env_file(env_file)

            self.assertEqual("1panel.example.org", config.domain)
            self.assertTrue(config.record_proxied)
            self.assertEqual([443, 8443], config.https_ports)
            self.assertEqual("cloudflare-example", config.dns_account_name)

    def test_cloudflare_client_creates_record_when_absent(self) -> None:
        client = FakeCloudflareClient(
            [
                {"success": True, "result": [{"id": "zone-1"}]},
                {"success": True, "result": []},
                {"success": True, "result": {"id": "record-1", "name": "1panel.example.org", "content": "198.51.100.20", "proxied": True}},
            ]
        )

        result = client.ensure_dns_record(
            zone_name="example.org",
            record_name="1panel.example.org",
            record_type="A",
            content="198.51.100.20",
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
                        "PUBLIC_INGRESS_DOMAIN=1panel.example.org",
                        "PUBLIC_INGRESS_ZONE_NAME=example.org",
                        "PUBLIC_INGRESS_RECORD_CONTENT=198.51.100.20",
                        "ONEPANEL_DNS_ACCOUNT_NAME=cloudflare-example",
                        "ONEPANEL_DNS_ACCOUNT_EMAIL=admin@example.net",
                        "ONEPANEL_WEBSITE_ALIAS=1panel",
                        "ONEPANEL_WEBSITE_PROXY=http://127.0.0.1:2096",
                        "ONEPANEL_CERT_DIR=/data/1panel/www/certs/1panel-example-org",
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
            domain="1panel.example.org",
            zone_name="example.org",
            record_type="A",
            record_content="198.51.100.20",
            record_proxied=True,
            dns_account_name="cloudflare-example",
            dns_account_provider="CloudFlare",
            dns_account_email="admin@example.net",
            acme_email="acme@1paneldev.com",
            acme_type="letsencrypt",
            acme_key_type="2048",
            website_alias="1panel",
            website_type="proxy",
            website_group_id=1,
            website_proxy="http://127.0.0.1:2096",
            website_remark="prod0-main 1Panel public ingress",
            website_ipv6=True,
            cert_primary_domain="1panel.example.org",
            cert_other_domains="",
            cert_dir="/data/1panel/www/certs/1panel-example-org",
            cert_description="prod0-main 1Panel public ingress",
            cert_key_type="2048",
            cert_auto_renew=True,
            cert_reload_shell="docker exec 1panel-openresty-prod nginx -t && docker exec 1panel-openresty-prod nginx -s reload",
            https_http_config="HTTPAlso",
            https_ports=[443],
        )
        cloudflare = FakeCloudflareClient(
            [
                {"success": True, "result": [{"id": "zone-1"}]},
                {"success": True, "result": [{"id": "record-1", "content": "198.51.100.20", "proxied": True}]},
            ]
        )
        manager = public_ingress.PublicIngressManager(FakePanelExecutor(), cloudflare, config)

        result = manager.ensure()

        self.assertEqual("unchanged", result["cloudflare_dns"]["action"])
        self.assertEqual(3, result["ssl"]["id"])
        self.assertEqual(4, result["ingress"]["id"])

    def test_manager_creates_new_proxy_website_with_app_type_new(self) -> None:
        config = public_ingress.PublicIngressConfig(
            domain="token.example.org",
            zone_name="example.org",
            record_type="A",
            record_content="198.51.100.20",
            record_proxied=True,
            dns_account_name="cloudflare-example",
            dns_account_provider="CloudFlare",
            dns_account_email="admin@example.net",
            acme_email="acme@1paneldev.com",
            acme_type="letsencrypt",
            acme_key_type="2048",
            website_alias="token",
            website_type="proxy",
            website_group_id=1,
            website_proxy="http://127.0.0.1:18080",
            website_remark="prod0-main sub2api public ingress",
            website_ipv6=True,
            cert_primary_domain="token.example.org",
            cert_other_domains="",
            cert_dir="/data/1panel/www/certs/token-example-org",
            cert_description="prod0-main sub2api public ingress",
            cert_key_type="2048",
            cert_auto_renew=True,
            cert_reload_shell="docker exec 1panel-openresty-prod nginx -t && docker exec 1panel-openresty-prod nginx -s reload",
            https_http_config="HTTPAlso",
            https_ports=[443],
        )
        cloudflare = FakeCloudflareClient(
            [
                {"success": True, "result": [{"id": "zone-1"}]},
                {"success": True, "result": [{"id": "record-1", "content": "198.51.100.20", "proxied": True}]},
            ]
        )
        panel = CreatingPanelExecutor()
        manager = public_ingress.PublicIngressManager(panel, cloudflare, config)

        result = manager.ensure()

        create_request = next(body for method, path, body in panel.requests if method == "POST" and path == "/api/v2/websites")
        self.assertEqual("new", create_request["appType"])
        self.assertEqual("proxy", create_request["type"])
        self.assertEqual([{"domain": "token.example.org", "port": 80, "ssl": False}], create_request["domains"])
        self.assertEqual(5, result["ingress"]["id"])

# ======================================================================
# From: test_onepanel_compose_policy.py
# ======================================================================

class ComposePolicyTests(unittest.TestCase):
    def test_openresty_requires_infra_network_mode(self) -> None:
        self.assertTrue(requires_host_network("openresty"))
        self.assertFalse(requires_host_network("new-api"))
        self.assertFalse(requires_host_network("demo-app"))

    def test_replaces_legacy_1panel_network_with_zqf_network(self) -> None:
        raw = """
services:
  demo:
    image: demo:latest
    networks:
      - 1panel-network
networks:
  1panel-network:
    external: true
""".strip()

        rendered = enforce_zqf_network(raw)

        self.assertIn("zqf_network", rendered)
        self.assertNotIn("1panel-network", rendered)

    def test_preserves_extra_networks_while_forcing_zqf_network(self) -> None:
        raw = """
services:
  demo:
    image: demo:latest
    networks:
      - app-private
networks:
  app-private:
    external: true
""".strip()

        rendered = enforce_zqf_network(raw)

        self.assertIn("zqf_network", rendered)
        self.assertIn("app-private", rendered)

    def test_openresty_is_normalized_to_infra_network_mode(self) -> None:
        raw = """
services:
  openresty:
    image: openresty:latest
    networks:
      - 1panel-network
networks:
  1panel-network:
    external: true
""".strip()

        rendered = normalize_compose_for_app("openresty", raw)

        self.assertIn("network_mode: infra", rendered)
        self.assertNotIn("zqf_network", rendered)
        self.assertNotIn("1panel-network", rendered)

    def test_non_openresty_app_never_gets_host_network_exception(self) -> None:
        raw = """
services:
  demo:
    image: demo:latest
""".strip()

        rendered = normalize_compose_for_app("demo", raw)

        self.assertIn("zqf_network", rendered)
        self.assertNotIn("network_mode: host", rendered)

# ======================================================================
# From: test_onepanel_env_targets.py
# ======================================================================

class OnePanelEnvTargetsTests(unittest.TestCase):
    def _run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "agentplane.cli", *args],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def tearDown(self) -> None:
        if hasattr(env_targets, "_resolve_remote_api_paths"):
            env_targets._resolve_remote_api_paths.cache_clear()

    def test_resolve_repo_root_falls_back_to_common_git_root_for_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            main_root = tmp_root / "main"
            worktree_root = tmp_root / "worktree"
            git_worktree_dir = main_root / ".git" / "worktrees" / "demo"
            script_path = worktree_root / "agentplane" / "scripts" / "onepanel" / "env_targets.py"

            git_worktree_dir.mkdir(parents=True, exist_ok=True)
            script_path.parent.mkdir(parents=True, exist_ok=True)
            worktree_root.mkdir(parents=True, exist_ok=True)
            (worktree_root / ".git").write_text(f"gitdir: {git_worktree_dir}\n", encoding="utf-8")

            resolved = env_targets.resolve_repo_root(script_path)

            self.assertEqual(main_root, resolved)

    def test_prod_targets_use_agentplane_remote_paths_and_support_prod2(self) -> None:
        prod0_target = env_targets.get_target("prod0-main")
        prod2_target = env_targets.get_target("prod0-main")

        self.assertEqual("ssh", prod0_target.mode)
        self.assertEqual("ssh", prod2_target.mode)
        self.assertEqual("prod0-main", prod0_target.ssh_alias)
        self.assertEqual("prod0-main", prod2_target.ssh_alias)
        self.assertEqual(Path("/opt/agentplane/secrets/services/onepanel-api.env"), prod0_target.api_env_file)
        self.assertEqual(
            Path("/opt/agentplane/agentplane/scripts/onepanel/signed_request.py"),
            prod0_target.api_request_script,
        )
        self.assertEqual(Path("/opt/agentplane/secrets/services/onepanel-api.env"), prod2_target.api_env_file)
        self.assertEqual(
            Path("/opt/agentplane/agentplane/scripts/onepanel/signed_request.py"),
            prod2_target.api_request_script,
        )

    def test_supported_targets_include_prod2(self) -> None:
        self.assertIn("prod0-main", env_targets.supported_targets())

    def test_wsl_local_api_request_command_uses_backend_paths(self) -> None:
        target = env_targets.TargetConfig(
            name="wsl",
            mode="local",
            api_env_file=Path("D:/Projects/AgentPlane/secrets/hosts/wsl/onepanel/api.env"),
            api_request_script=Path("D:/Projects/AgentPlane/agentplane/scripts/onepanel/signed_request.py"),
            linux_backend=env_targets.LinuxBackend(
                backend_type="wsl-linux",
                executable=("wsl.exe", "-e"),
                shell_executable=("wsl.exe", "-e", "bash", "-lc"),
            ),
        )

        command = env_targets.build_api_request_command(target, "GET", "/api/v2/core/settings/search")

        self.assertEqual("python3", command[0])
        self.assertEqual("/mnt/d/Projects/AgentPlane/agentplane/scripts/onepanel/signed_request.py", command[1])
        self.assertIn("/mnt/d/Projects/AgentPlane/secrets/hosts/wsl/onepanel/api.env", command)

    def test_ssh_api_request_command_preserves_remote_posix_paths(self) -> None:
        target = env_targets.TargetConfig(
            name="prod0-main",
            mode="ssh",
            api_env_file=Path("/opt/agentplane/secrets/services/onepanel-api.env"),
            api_request_script=Path("/opt/agentplane/agentplane/scripts/onepanel/signed_request.py"),
        )

        command = env_targets.build_api_request_command(target, "GET", "/api/v2/core/settings/search")

        self.assertEqual("python3", command[0])
        self.assertEqual("/opt/agentplane/agentplane/scripts/onepanel/signed_request.py", command[1])
        self.assertIn("/opt/agentplane/secrets/services/onepanel-api.env", command)

    def test_resolve_remote_api_paths_uses_declared_agentplane_remote_root(self) -> None:
        target = env_targets.get_target("prod0-main")
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="/opt/agentplane/secrets/services/onepanel-api.env\n"
            "/opt/agentplane/agentplane/scripts/onepanel/signed_request.py\n",
            stderr="",
        )

        with mock.patch.object(env_targets, "run_command", return_value=completed) as run_command:
            env_file, script = env_targets.resolve_api_paths(target)

        self.assertEqual(Path("/opt/agentplane/secrets/services/onepanel-api.env"), env_file)
        self.assertEqual(Path("/opt/agentplane/agentplane/scripts/onepanel/signed_request.py"), script)
        run_command.assert_called_once()

    def test_resolve_remote_api_paths_ignores_removed_live_root_work_repo(self) -> None:
        target = env_targets.get_target("prod0-main")
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="",
            stderr="",
        )

        with mock.patch.object(env_targets, "run_command", return_value=completed) as run_command:
            env_file, script = env_targets.resolve_api_paths(target)

        self.assertEqual(Path("/opt/agentplane/secrets/services/onepanel-api.env"), env_file)
        self.assertEqual(Path("/opt/agentplane/agentplane/scripts/onepanel/signed_request.py"), script)
        run_command.assert_called_once()

    def test_phase4_lane12_projection_fixture_apply_requires_execute_for_mutation_guardrail(self) -> None:
        result = self._run_cli(
            "projection",
            "fixture",
            "apply",
            "--target",
            "wsl",
            "--profile",
            "wsl-fixture",
            "--repo-root",
            str(REPO_ROOT),
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires --execute", result.stderr)

# ======================================================================
# From: test_onepanel_fixture_manager.py
# ======================================================================

class FakeFixtureExecutor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, object] | None]] = []
        self.website: dict[str, object] | None = None
        self.project: dict[str, object] | None = None
        self.cronjob: dict[str, object] | None = None

    def api_request(self, method: str, path: str, body: dict[str, object] | None = None) -> object:
        self.calls.append((method, path, body))
        if path == "/api/v2/apps/installed/search":
            return {"items": [{"id": 3, "name": "openresty", "appKey": "openresty", "status": "Running"}]}
        if path == "/api/v2/websites/search":
            if self.website and body and body.get("name") in {"", self.website["alias"]}:
                return {"items": [self.website]}
            return {"items": []}
        if path == "/api/v2/websites":
            assert body is not None
            domains = body.get("domains")
            domain_value = ""
            if isinstance(domains, list) and domains:
                first_domain = domains[0]
                if isinstance(first_domain, dict):
                    domain_value = str(first_domain.get("domain", ""))
            if not domain_value:
                primary_domain = body.get("primaryDomain")
                if primary_domain is not None:
                    domain_value = str(primary_domain)
            self.website = {
                "id": 21,
                "alias": body["alias"],
                "proxy": body["proxy"],
                "status": "Running",
            }
            if domain_value:
                self.website["primaryDomain"] = domain_value
            if isinstance(domains, list):
                self.website["domains"] = domains
            return {"id": 21}
        if path == "/api/v2/containers/compose/search":
            if self.project and body and body.get("info") in {"", self.project["name"]}:
                return {"items": [self.project]}
            return {"items": []}
        if path == "/api/v2/containers/compose":
            assert body is not None
            name = str(body["name"])
            self.project = {
                "name": name,
                "status": "stopped",
                "runningCount": 0,
                "createdBy": "1Panel",
                "configFile": f"/data/1panel/docker/compose/{name}/docker-compose.yml",
            }
            return {"ok": True, "name": name}
        if path == "/api/v2/containers/compose/update":
            return {"ok": True}
        if path == "/api/v2/containers/compose/operate":
            assert body is not None
            if self.project and body.get("operation") == "up":
                self.project["status"] = "running"
                self.project["runningCount"] = 1
            if self.project and body.get("operation") == "down" and body.get("withFile"):
                self.project = None
            return {"ok": True}
        if path == "/api/v2/cronjobs/search":
            if self.cronjob is None:
                return {"items": []}
            if body and body.get("info") in {"", self.cronjob["name"]}:
                return {"items": [self.cronjob]}
            return {"items": []}
        if path == "/api/v2/cronjobs":
            assert body is not None
            self.cronjob = {
                "id": 9,
                "name": body["name"],
                "status": "Enable",
                "groupID": body.get("groupID", 0),
            }
            return {"id": 9}
        if path == "/api/v2/cronjobs/status":
            assert body is not None and self.cronjob is not None
            self.cronjob["status"] = body["status"]
            return {"ok": True}
        raise AssertionError(f"Unexpected request: {method} {path} {body}")

class OnePanelFixtureManagerTests(unittest.TestCase):
    def test_resolve_suite_targets_uses_wsl_fixture_defaults(self) -> None:
        targets = resolve_suite_targets(profile="wsl-fixture", env="wsl")

        self.assertEqual("oplinux-fixture", targets["website_alias"])
        self.assertEqual("oplinux-fixture-web", targets["container_name"])
        self.assertEqual("oplinux-fixture", targets["project_name"])
        self.assertEqual("oplinux-fixture", targets["cronjob_name"])
        self.assertEqual("", targets["app_name"])

    def test_plan_fixture_reports_create_actions_when_missing(self) -> None:
        executor = FakeFixtureExecutor()
        spec = resolve_fixture_spec("wsl-fixture", env="wsl")

        payload = plan_fixture(executor, spec)

        actions = {item["object"]: item["action"] for item in payload["items"]}
        self.assertEqual("create", actions["ingress"])
        self.assertEqual("create", actions["project"])
        self.assertEqual("create", actions["cronjob"])

    def test_apply_fixture_creates_resources(self) -> None:
        executor = FakeFixtureExecutor()
        spec = resolve_fixture_spec("wsl-fixture", env="wsl")

        payload = apply_fixture(executor, spec, execute=True)

        self.assertTrue(payload["ok"])
        self.assertIsNotNone(executor.website)
        website_call = next(call for call in executor.calls if call[1] == "/api/v2/websites")
        self.assertIn("domains", website_call[2])
        self.assertNotIn("primaryDomain", website_call[2])
        self.assertIsNotNone(executor.project)
        self.assertEqual(1, executor.project["runningCount"])
        self.assertIsNotNone(executor.cronjob)
        self.assertEqual("Enable", executor.cronjob["status"])

    def test_cleanup_fixture_removes_project_and_disables_cronjob(self) -> None:
        executor = FakeFixtureExecutor()
        spec = resolve_fixture_spec("wsl-fixture", env="wsl")
        apply_fixture(executor, spec, execute=True)

        payload = cleanup_fixture(executor, spec, execute=True)

        self.assertTrue(payload["ok"])
        self.assertIsNone(executor.project)
        self.assertEqual("Disable", executor.cronjob["status"])

# ======================================================================
# From: test_onepanel_verification_suite.py
# ======================================================================

class FakeExecutor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, object] | None]] = []

    def api_request(self, method: str, path: str, body: dict[str, object] | None = None) -> object:
        self.calls.append((method, path, body))
        if path == "/api/v2/core/settings/search":
            return {
                "systemVersion": "v2.1.7",
                "bindDomain": "1panel.example.com",
                "apiKey": "raw-panel-api-key",
                "proxyPasswd": "raw-proxy-password",
            }
        if path == "/api/v2/websites/search":
            return {"items": [{"id": 4, "alias": "token", "primaryDomain": "token.example.org"}]}
        if path == "/api/v2/websites/4":
            return {"id": 4, "alias": "token", "proxy": "http://127.0.0.1:18080"}
        if path == "/api/v2/websites/4/https":
            return {"enable": True}
        if path == "/api/v2/containers/info":
            return {"name": "sub2api-prod", "state": "running"}
        if path == "/api/v2/containers/compose/search":
            return {"items": [{"name": "sub2api-prod", "status": "running", "runningCount": 1}]}
        if path == "/api/v2/cronjobs/load/info":
            return {"id": 2, "status": "Enable"}
        if path == "/api/v2/hosts/firewall/base":
            return {"name": "ufw", "isActive": True}
        if path == "/api/v2/apps/installed/search":
            return {"items": [{"id": 3, "name": "new-api", "status": "Running", "appKey": "new-api"}]}
        if path == "/api/v2/apps/installed/info/3":
            return {"id": 3, "name": "new-api", "status": "Running"}
        if path == "/api/v2/logs/tasks/executing/count":
            return {"executing": 0}
        raise AssertionError(f"Unexpected request: {method} {path} {body}")

class ComposeSearchFailExecutor(FakeExecutor):
    def api_request(self, method: str, path: str, body: dict[str, object] | None = None) -> object:
        if path == "/api/v2/containers/compose/search":
            raise RuntimeError("API command failed: POST /api/v2/containers/compose/search")
        if path == "/api/v2/apps/installed/search":
            return {"items": [{"id": 9, "name": "sub2api", "status": "Running", "appKey": "sub2api"}]}
        if path == "/api/v2/apps/installed/info/9":
            return {"id": 9, "name": "sub2api", "status": "Running"}
        return super().api_request(method, path, body)

class CronjobByNameExecutor(FakeExecutor):
    def api_request(self, method: str, path: str, body: dict[str, object] | None = None) -> object:
        if path == "/api/v2/cronjobs/search":
            return {"items": [{"id": 7, "name": "oplinux-fixture", "status": "Enable"}]}
        if path == "/api/v2/cronjobs/load/info":
            assert body is not None
            return {"id": int(body["id"]), "status": "Enable"}
        return super().api_request(method, path, body)

class OnePanelVerificationSuiteTests(unittest.TestCase):
    def test_wsl_fixture_profile_runs_expected_checks(self) -> None:
        executor = FakeExecutor()

        payload = run_verification_suite(
            executor,
            profile="wsl-fixture",
            website_alias="token",
            container_name="sub2api-prod",
            project_name="sub2api-prod",
            cronjob_id=2,
            app_name="new-api",
        )

        self.assertTrue(payload["ok"])
        self.assertEqual("wsl-fixture", payload["profile"])
        scopes = [item["scope"] for item in payload["checks"]]
        self.assertEqual(
            ["panel", "ingress", "container", "project", "cronjob", "firewall", "app", "task"],
            scopes,
        )

    def test_suite_can_write_report_files(self) -> None:
        executor = FakeExecutor()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)

            payload = run_verification_suite(
                executor,
                profile="prod0-readonly",
                env="prod0-main",
                repo_root=root,
                write_report=True,
            )

            report = payload["report"]
            self.assertTrue((root / "inventory" / "servers" / "prod0-main" / "ledgers" / "verification-prod0-readonly.json").is_file())
            self.assertTrue((root / "inventory" / "servers" / "prod0-main" / "ledgers" / "verification-prod0-readonly.md").is_file())
            self.assertEqual("prod0-readonly", report["profile"])
            self.assertEqual("raw-panel-api-key", payload["checks"][0]["payload"]["apiKey"])
            self.assertEqual("raw-proxy-password", payload["checks"][0]["payload"]["proxyPasswd"])

            json_text = (
                root / "inventory" / "servers" / "prod0-main" / "ledgers" / "verification-prod0-readonly.json"
            ).read_text(encoding="utf-8")
            self.assertNotIn("raw-panel-api-key", json_text)
            self.assertNotIn("raw-proxy-password", json_text)

            persisted = json.loads(json_text)
            self.assertEqual("[REDACTED]", persisted["checks"][0]["payload"]["apiKey"])
            self.assertEqual("[REDACTED]", persisted["checks"][0]["payload"]["proxyPasswd"])

    def test_suite_writes_failed_report_when_one_scope_errors(self) -> None:
        executor = ComposeSearchFailExecutor()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)

            payload = run_verification_suite(
                executor,
                profile="prod2-readonly",
                env="prod0-main",
                repo_root=root,
                write_report=True,
                website_alias="token",
                container_name="sub2api-prod",
                project_name="sub2api-prod",
                app_name="sub2api",
            )

            self.assertFalse(payload["ok"])
            checks = {item["scope"]: item for item in payload["checks"]}
            self.assertFalse(checks["project"]["ok"])
            self.assertEqual(
                "API command failed: POST /api/v2/containers/compose/search",
                checks["project"]["payload"]["error"]["message"],
            )
            self.assertTrue(checks["app"]["ok"])
            self.assertTrue((root / "inventory" / "servers" / "prod0-main" / "ledgers" / "verification-prod2-readonly.json").is_file())
            self.assertTrue((root / "inventory" / "servers" / "prod0-main" / "ledgers" / "verification-prod2-readonly.md").is_file())

    def test_suite_can_resolve_cronjob_by_name(self) -> None:
        executor = CronjobByNameExecutor()

        payload = run_verification_suite(
            executor,
            profile="wsl-fixture",
            cronjob_name="oplinux-fixture",
        )

        checks = {item["scope"]: item for item in payload["checks"]}
        self.assertTrue(checks["cronjob"]["ok"])
        self.assertEqual(7, checks["cronjob"]["payload"]["id"])
