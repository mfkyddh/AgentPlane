from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from agentplane.scripts.onepanel.verification import run_verification_suite
from tests.support.constants import (
    CONTAINER_SUB2API,
    DOMAIN_1PANEL,
    DOMAIN_TOKEN_ORG,
    FAKE_HOST_BINDING,
)
from tests.support.paths import REPO_ROOT

pytestmark = pytest.mark.integration

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
ONEPANEL_SCRIPTS = REPO_ROOT / "agentplane" / "scripts" / "onepanel"
if str(ONEPANEL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(ONEPANEL_SCRIPTS))


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
                "bindDomain": DOMAIN_1PANEL,
                "apiKey": "raw-panel-api-key",
                "proxyPasswd": "raw-proxy-password",
            }
        if path == "/api/v2/websites/search":
            return {"items": [{"id": 4, "alias": "token", "primaryDomain": DOMAIN_TOKEN_ORG}]}
        if path == "/api/v2/websites/4":
            return {"id": 4, "alias": "token", "proxy": f"http://{FAKE_HOST_BINDING}"}
        if path == "/api/v2/websites/4/https":
            return {"enable": True}
        if path == "/api/v2/containers/info":
            return {"name": CONTAINER_SUB2API, "state": "running"}
        if path == "/api/v2/containers/compose/search":
            return {"items": [{"name": CONTAINER_SUB2API, "status": "running", "runningCount": 1}]}
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
            container_name=CONTAINER_SUB2API,
            project_name=CONTAINER_SUB2API,
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
            self.assertTrue(
                (
                    root / "inventory" / "servers" / "prod0-main" / "ledgers" / "verification-prod0-readonly.json"
                ).is_file()
            )
            self.assertTrue(
                (root / "inventory" / "servers" / "prod0-main" / "ledgers" / "verification-prod0-readonly.md").is_file()
            )
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
            self.assertTrue(
                (
                    root / "inventory" / "servers" / "prod0-main" / "ledgers" / "verification-prod2-readonly.json"
                ).is_file()
            )
            self.assertTrue(
                (root / "inventory" / "servers" / "prod0-main" / "ledgers" / "verification-prod2-readonly.md").is_file()
            )

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
