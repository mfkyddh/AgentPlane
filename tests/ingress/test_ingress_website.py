from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from agentplane.domain.ingress.lifecycle import (
    apply_ingress_truth_offboard,
    apply_ingress_truth_onboard,
    plan_ingress_truth_offboard,
    plan_ingress_truth_onboard,
)
from agentplane.domain.ingress.models import IngressDefinition
from tests.support.cli import run_agentplane_cli as run_cli
from tests.support.constants import (
    DOMAIN_LANE5,
    DOMAIN_TOKEN,
    DOMAIN_TOKEN_ORG,
    FAKE_HOST_BINDING,
    FAKE_PROXY_8080,
    FAKE_PROXY_18080,
    TARGET_PROD,
)

pytestmark = pytest.mark.e2e


def write_inventory(root: Path) -> None:
    server_root = root / "inventory" / "servers" / "prod0-main"
    server_root.mkdir(parents=True, exist_ok=True)
    (server_root / "README.md").write_text("# prod0-main 摘要\n", encoding="utf-8")
    (server_root / "inventory.json").write_text(
        json.dumps(
            {
                "services": {
                    "public_ingresses": [
                        {
                            "alias": "token",
                            "primary_domain": DOMAIN_TOKEN_ORG,
                            "public_url": f"https://{DOMAIN_TOKEN_ORG}",
                            "proxy": f"http://{FAKE_HOST_BINDING}",
                            "config_file": "/data/1panel/www/conf.d/token.conf",
                            "ssl_id": 3,
                            "status": "Running",
                        }
                    ]
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def write_publish_files(root: Path) -> tuple[Path, Path]:
    config_file = root / "publish.env"
    config_file.write_text(
        "\n".join(
            [
                f"PUBLIC_INGRESS_DOMAIN={DOMAIN_TOKEN}",
                "PUBLIC_INGRESS_ZONE_NAME=example.net",
                "PUBLIC_INGRESS_RECORD_CONTENT=1.2.3.4",
                "ONEPANEL_DNS_ACCOUNT_NAME=cloudflare-example",
                "ONEPANEL_DNS_ACCOUNT_EMAIL=admin@example.net",
                "ONEPANEL_WEBSITE_ALIAS=token",
                f"ONEPANEL_WEBSITE_PROXY=http://{FAKE_HOST_BINDING}",
                "ONEPANEL_CERT_DIR=/data/1panel/www/certs/token-example-net",
                "ONEPANEL_CERT_RELOAD_SHELL=echo reload",
            ]
        ),
        encoding="utf-8",
    )
    cloudflare_env_file = root / "cloudflare.env"
    cloudflare_env_file.write_text(
        "export CLOUDFLARE_API_TOKEN=test-token\nexport CLOUDFLARE_ACCOUNT_ID=test-account\n",
        encoding="utf-8",
    )
    return config_file, cloudflare_env_file


def _inventory_file(tmp_path: Path, target: str) -> Path:
    inventory_dir = tmp_path / "inventory" / "servers" / target
    inventory_dir.mkdir(parents=True, exist_ok=True)
    return inventory_dir / "inventory.json"


def _write_inventory(tmp_path: Path, target: str, payload: dict) -> Path:
    inventory_file = _inventory_file(tmp_path, target)
    inventory_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return inventory_file


def _definition() -> IngressDefinition:
    return IngressDefinition(
        alias="lane5",
        primary_domain=DOMAIN_LANE5,
        public_url=f"https://{DOMAIN_LANE5}",
        proxy=FAKE_PROXY_8080,
        status="Running",
        config_file="/data/lane5/www/conf.d/lane5.conf",
        ssl_id=77,
    )


def _entry_from(definition: IngressDefinition) -> dict:
    return {
        "alias": definition.alias,
        "primary_domain": definition.primary_domain,
        "public_url": definition.public_url,
        "proxy": definition.proxy,
        "status": definition.status,
        "config_file": definition.config_file,
        "ssl_id": definition.ssl_id,
    }




class FakeWebsiteExecutor:
    def __init__(
        self,
        *,
        existing: dict[str, object] | None,
        https: dict[str, object] | None = None,
        ssl_detail: dict[str, object] | None = None,
        openresty_status: dict[str, object] | None = None,
    ) -> None:
        self.requests: list[tuple[str, str, dict[str, object] | None]] = []
        self._existing = existing
        self._https = https or {}
        self._ssl_detail = ssl_detail or {"id": 3, "status": "ready", "primaryDomain": DOMAIN_TOKEN_ORG}
        self._openresty_status = openresty_status or {"id": 3, "name": "openresty", "status": "Running"}
        self._created = False

    def api_request(self, method: str, path: str, body: dict[str, object] | None = None) -> object:
        self.requests.append((method, path, body))
        if path == "/api/v2/websites/search":
            if self._existing is None and not self._created:
                return {"items": []}
            website_id = 9 if self._existing is None else int(self._existing["id"])
            alias = "token" if self._existing is None else str(self._existing["alias"])
            primary_domain = DOMAIN_TOKEN_ORG if self._existing is None else str(self._existing["primaryDomain"])
            proxy = FAKE_PROXY_18080 if self._existing is None else str(self._existing["proxy"])
            return {
                "items": [
                    {
                        "id": website_id,
                        "alias": alias,
                        "primaryDomain": primary_domain,
                        "status": "Running",
                        "proxy": proxy,
                    }
                ]
            }
        if path == "/api/v2/websites/7":
            if self._existing is None:
                raise AssertionError("Unexpected detail request when website is missing")
            return dict(self._existing)
        if path == "/api/v2/websites/7/https":
            if self._existing is None:
                raise AssertionError("Unexpected https request when website is missing")
            return dict(self._https)
        if path == "/api/v2/websites/9":
            return {
                "id": 9,
                "alias": "token",
                "primaryDomain": DOMAIN_TOKEN_ORG,
                "proxy": f"http://{FAKE_HOST_BINDING}",
                "status": "Running",
            }
        if path == "/api/v2/websites/9/https":
            return {"enable": True, "httpsPort": "443", "SSL": {"id": 3}}
        if path.startswith("/api/v2/websites/ssl/"):
            return dict(self._ssl_detail)
        if path == "/api/v2/apps/installed/info/3":
            return dict(self._openresty_status)
        if path == "/api/v2/websites":
            self._created = True
            return {"id": 9}
        raise AssertionError(f"Unexpected request: {method} {path} {body}")


class WebsiteCliTests(unittest.TestCase):
    def test_ingress_apply_requires_execute(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)

            result = run_cli(
                "ingress",
                "apply",
                "--target",
                "prod0-main",
                "--alias",
                "token",
                "--operation",
                "reconcile",
                "--repo-root",
                str(root),
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--execute", result.stderr)

    def test_ingress_search_lists_declared_public_ingresses(self) -> None:
        from agentplane.domain.ingress.handlers import search_ingresses

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)

            payload = search_ingresses(root, "prod0-main")

            self.assertEqual(
                [
                    {
                        "alias": "token",
                        "primary_domain": DOMAIN_TOKEN_ORG,
                        "public_url": f"https://{DOMAIN_TOKEN_ORG}",
                        "proxy": f"http://{FAKE_HOST_BINDING}",
                        "status": "Running",
                        "config_file": "/data/1panel/www/conf.d/token.conf",
                        "ssl_id": 3,
                        "certificate_mode": "",
                        "control_plane": "onepanel",
                    }
                ],
                payload["items"],
            )

    def test_ingress_get_aggregates_declared_and_live_state(self) -> None:
        from agentplane.domain.ingress.handlers import get_ingress

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            executor = FakeWebsiteExecutor(
                existing={
                    "id": 7,
                    "alias": "token",
                    "primaryDomain": DOMAIN_TOKEN_ORG,
                    "proxy": f"http://{FAKE_HOST_BINDING}",
                    "status": "Running",
                },
                https={"enable": True, "httpsPort": "443", "SSL": {"id": 3}},
            )

            with patch("agentplane.domain.ingress.handlers._executor_for_target", return_value=executor):
                payload = get_ingress(root, "prod0-main", "token")

            self.assertEqual("token", payload["ingress"]["alias"])
            self.assertEqual(DOMAIN_TOKEN_ORG, payload["ingress"]["primary_domain"])
            self.assertEqual(7, payload["live"]["ingress"]["id"])
            self.assertTrue(payload["live"]["https"]["enable"])

    def test_ingress_verify_reports_structured_checks_for_drift(self) -> None:
        from agentplane.domain.ingress.handlers import verify_ingress

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            executor = FakeWebsiteExecutor(
                existing={
                    "id": 7,
                    "alias": "token",
                    "primaryDomain": DOMAIN_TOKEN_ORG,
                    "proxy": "http://127.0.0.1:19090",
                    "status": "Running",
                },
                https={"enable": False, "httpsPort": "", "SSL": {"id": 99}},
                ssl_detail={"id": 99, "status": "ready", "primaryDomain": DOMAIN_TOKEN_ORG},
                openresty_status={"id": 3, "name": "openresty", "status": "Running"},
            )

            with patch("agentplane.domain.ingress.handlers._executor_for_target", return_value=executor):
                payload = verify_ingress(root, "prod0-main", "token")

            self.assertFalse(payload["ok"])
            self.assertTrue(payload["checks"]["alias"]["ok"])
            self.assertFalse(payload["checks"]["proxy"]["ok"])
            self.assertFalse(payload["checks"]["https"]["ok"])
            self.assertTrue(payload["checks"]["ssl_status"]["ok"])
            self.assertTrue(payload["checks"]["openresty"]["ok"])
            self.assertEqual(["proxy", "https", "ssl_id"], payload["failures"])

    def test_ingress_plan_reconcile_builds_create_step_for_missing_site(self) -> None:
        from agentplane.domain.ingress.handlers import plan_ingress_operation

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            executor = FakeWebsiteExecutor(existing=None)

            with patch("agentplane.domain.ingress.handlers._executor_for_target", return_value=executor):
                payload = plan_ingress_operation(root, "prod0-main", "token", "reconcile")

            self.assertEqual("reconcile", payload["operation"])
            self.assertEqual("missing", payload["drift"]["status"])
            self.assertEqual("/api/v2/websites", payload["steps"][0]["path"])
            self.assertEqual("create", payload["steps"][0]["kind"])
            self.assertEqual("token", payload["steps"][0]["body"]["website_alias"])

    def test_ingress_apply_reconcile_creates_missing_site_and_post_verifies(self) -> None:
        from agentplane.cli.ingress import handle_ingress_command

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            executor = FakeWebsiteExecutor(existing=None)

            args = SimpleNamespace(
                ingress_action="apply",
                target="prod0-main",
                alias="token",
                operation="reconcile",
                repo_root=str(root),
                execute=True,
                write=False,
            )

            with patch("agentplane.domain.ingress.handlers._executor_for_target", return_value=executor):
                payload = handle_ingress_command(args)

            self.assertEqual("ingress", payload["command"])
            self.assertEqual("apply", payload["action"])
            self.assertTrue(payload["payload"]["ok"])
            self.assertEqual("created", payload["payload"]["result"]["action"])
            self.assertTrue(payload["payload"]["verified"]["ok"])
            follow_through = payload["payload"]["follow_through"]
            self.assertEqual("projection", follow_through["owner_surface"])
            self.assertEqual("ingress", follow_through["source_surface"])
            self.assertIn("projection verification run", follow_through["commands"]["verification"])
            self.assertIn("--website-alias token", follow_through["commands"]["verification"])
            self.assertIn("projection ledger refresh", follow_through["commands"]["ledger_refresh"])

    def test_ingress_refresh_ledger_updates_projection_without_mutating_declared_rows(self) -> None:
        from agentplane.cli.ingress import handle_ingress_command

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)

            args = SimpleNamespace(
                ingress_action="refresh-ledger",
                target="prod0-main",
                repo_root=str(root),
                write=True,
            )

            payload = handle_ingress_command(args)

            self.assertEqual("ingress", payload["command"])
            self.assertEqual(1, payload["payload"]["counts"]["websites"])
            self.assertTrue((root / "inventory" / "servers" / "prod0-main" / "ledgers" / "websites.json").is_file())
            persisted_inventory = json.loads(
                (root / "inventory" / "servers" / "prod0-main" / "inventory.json").read_text(encoding="utf-8")
            )
            self.assertEqual("token", persisted_inventory["services"]["public_ingresses"][0]["alias"])
            self.assertEqual(1, persisted_inventory["object_ledgers"]["counts"]["websites"])


# ======================================================================
# From: test_ingress_publish_cli.py
# ======================================================================


def write_publish_files(root: Path) -> tuple[Path, Path]:
    config_file = root / "publish.env"
    config_file.write_text(
        "\n".join(
            [
                f"PUBLIC_INGRESS_DOMAIN={DOMAIN_TOKEN}",
                "PUBLIC_INGRESS_ZONE_NAME=example.net",
                "PUBLIC_INGRESS_RECORD_CONTENT=1.2.3.4",
                "ONEPANEL_DNS_ACCOUNT_NAME=cloudflare-example",
                "ONEPANEL_DNS_ACCOUNT_EMAIL=admin@example.net",
                "ONEPANEL_WEBSITE_ALIAS=token",
                f"ONEPANEL_WEBSITE_PROXY=http://{FAKE_HOST_BINDING}",
                "ONEPANEL_CERT_DIR=/data/1panel/www/certs/token-example-net",
                "ONEPANEL_CERT_RELOAD_SHELL=echo reload",
            ]
        ),
        encoding="utf-8",
    )
    cloudflare_env_file = root / "cloudflare.env"
    cloudflare_env_file.write_text(
        "export CLOUDFLARE_API_TOKEN=test-token\nexport CLOUDFLARE_ACCOUNT_ID=test-account\n",
        encoding="utf-8",
    )
    return config_file, cloudflare_env_file
