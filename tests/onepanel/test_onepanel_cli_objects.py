from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from agentplane.domain.infra.onepanel import (
    handle_cronjob_action,
    handle_firewall_action,
    handle_panel_action,
    handle_task_action,
    onepanel_skeleton,
)
from agentplane.scripts.onepanel.object_api import (
    FakeLikeExecutorProtocol,
    build_app_install_params,
    get_panel_summary,
    load_firewall_base,
    plan_app_install,
    plan_firewall_operation,
    plan_installed_app_operation,
    search_cronjobs,
    search_firewall_rules,
)
from tests.support.cli import run_agentplane_cli as run_cli
from tests.support.paths import REPO_ROOT

from tests.support.constants import DOMAIN_1PANEL, DOMAIN_MIGRATED, DOMAIN_NGINX, DOMAIN_PANEL_NET, DOMAIN_PROXY, DOMAIN_TOKEN_ORG

pytestmark = pytest.mark.e2e


class FakeExecutor(FakeLikeExecutorProtocol):
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, object] | None]] = []

    def api_request(self, method: str, path: str, body: dict[str, object] | None = None) -> object:
        self.calls.append((method, path, body))
        if path == "/api/v2/core/settings/search":
            return {"systemVersion": "v2.1.7", "bindDomain": DOMAIN_1PANEL, "apiKey": "panel-secret-key"}
        if path == "/api/v2/core/settings/update":
            return {"ok": True}
        if path == "/api/v2/cronjobs/search":
            return {"items": [{"id": 2, "name": "backup-secrets", "status": "Enable"}]}
        if path == "/api/v2/hosts/firewall/base":
            return {
                "name": "ufw",
                "isExist": True,
                "isActive": True,
                "isInit": False,
                "isBind": False,
                "version": "0.36.2",
                "pingStatus": "1",
            }
        if path == "/api/v2/hosts/firewall/search":
            return {
                "items": [{"port": "22", "protocol": "tcp", "strategy": "accept", "description": "ssh"}],
                "total": 1,
            }
        if path == "/api/v2/hosts/firewall/operate":
            return {"ok": True}
        if path == "/api/v2/logs/tasks/executing/count":
            return {"executing": 0}
        if path == "/api/v2/logs/tasks/search":
            return {"items": [{"id": 1, "status": "success", "type": "cronjob"}], "total": 1}
        raise AssertionError(f"Unexpected request: {method} {path} {body}")


class OnePanelObjectApiTests(unittest.TestCase):
    def test_get_panel_summary_uses_v2_settings_endpoint(self) -> None:
        executor = FakeExecutor()

        result = get_panel_summary(executor)

        self.assertEqual("v2.1.7", result["systemVersion"])
        self.assertEqual(("POST", "/api/v2/core/settings/search", {}), executor.calls[0])

    def test_search_cronjobs_uses_expected_payload(self) -> None:
        executor = FakeExecutor()

        result = search_cronjobs(executor, info="backup")

        self.assertEqual("backup-secrets", result["items"][0]["name"])
        self.assertEqual(
            (
                "POST",
                "/api/v2/cronjobs/search",
                {
                    "page": 1,
                    "pageSize": 20,
                    "info": "backup",
                    "groupIDs": [],
                    "orderBy": "createdAt",
                    "order": "descending",
                },
            ),
            executor.calls[0],
        )

    def test_firewall_base_and_search_use_expected_payloads(self) -> None:
        executor = FakeExecutor()

        base = load_firewall_base(executor, name="port")
        search = search_firewall_rules(executor, rule_type="port", info="22")

        self.assertTrue(base["isActive"])
        self.assertEqual("22", search["items"][0]["port"])
        self.assertEqual(("POST", "/api/v2/hosts/firewall/base", {"name": "port"}), executor.calls[0])
        self.assertEqual(
            (
                "POST",
                "/api/v2/hosts/firewall/search",
                {
                    "page": 1,
                    "pageSize": 20,
                    "info": "22",
                    "status": "",
                    "strategy": "",
                    "type": "port",
                },
            ),
            executor.calls[1],
        )

    def test_plan_firewall_operation_uses_official_operate_endpoint(self) -> None:
        plan = plan_firewall_operation(operation="stop", with_docker_restart=False)

        self.assertEqual("/api/v2/hosts/firewall/operate", plan.path)
        self.assertEqual({"operation": "stop", "withDockerRestart": False}, plan.body)



class OnePanelObjectCliHandlerTests(unittest.TestCase):
    def test_panel_verify_redacts_sensitive_settings(self) -> None:
        args = type(
            "Args",
            (),
            {
                "env": "wsl",
                "onepanel_panel_action": "verify",
                "key": "",
            },
        )()

        with patch("agentplane.domain.infra.onepanel._executor_for", return_value=FakeExecutor()):
            payload = handle_panel_action(args)

        self.assertEqual("panel", payload["scope"])
        self.assertEqual("<redacted>", payload["payload"]["summary"]["apiKey"])
        self.assertNotIn("panel-secret-key", json.dumps(payload))

    def test_panel_apply_executes_setting_update(self) -> None:
        executor = FakeExecutor()
        args = type(
            "Args",
            (),
            {
                "env": "wsl",
                "onepanel_panel_action": "apply",
                "key": "bindDomain",
                "value": DOMAIN_PANEL_NET,
                "execute": True,
            },
        )()

        with patch("agentplane.domain.infra.onepanel._executor_for", return_value=executor):
            payload = handle_panel_action(args)

        self.assertEqual("panel", payload["scope"])
        self.assertEqual("apply", payload["action"])
        self.assertTrue(payload["payload"]["verified"]["ok"])
        self.assertIn(
            ("POST", "/api/v2/core/settings/update", {"key": "bindDomain", "value": DOMAIN_PANEL_NET}),
            executor.calls,
        )

    def test_firewall_verify_reports_expected_active(self) -> None:
        args = type(
            "Args",
            (),
            {
                "env": "wsl",
                "onepanel_firewall_action": "verify",
                "tab": "port",
                "expected_active": "true",
                "expected_name": "ufw",
            },
        )()

        with patch("agentplane.domain.infra.onepanel._executor_for", return_value=FakeExecutor()):
            payload = handle_firewall_action(args)

        self.assertEqual("firewall", payload["scope"])
        self.assertTrue(payload["payload"]["ok"])

    def test_cronjob_plan_wraps_status_operation(self) -> None:
        args = type(
            "Args",
            (),
            {
                "env": "wsl",
                "onepanel_cronjob_action": "plan",
                "mode": "status",
                "body_json": '{"id": 2, "status": "Disable"}',
                "execute": False,
            },
        )()

        with patch("agentplane.domain.infra.onepanel._executor_for", return_value=FakeExecutor()):
            payload = handle_cronjob_action(args)

        self.assertEqual("cronjob", payload["scope"])
        self.assertEqual("/api/v2/cronjobs/status", payload["payload"]["plan"]["path"])
        self.assertEqual({"id": 2, "status": "Disable"}, payload["payload"]["plan"]["body"])

    def test_task_verify_checks_executing_count(self) -> None:
        args = type(
            "Args",
            (),
            {
                "env": "wsl",
                "onepanel_task_action": "verify",
                "expected_count": 0,
            },
        )()

        with patch("agentplane.domain.infra.onepanel._executor_for", return_value=FakeExecutor()):
            payload = handle_task_action(args)

        self.assertEqual("task", payload["scope"])
        self.assertTrue(payload["payload"]["ok"])

    def test_skeleton_hint_points_only_to_remaining_object_faces(self) -> None:
        payload = onepanel_skeleton("wsl")

        self.assertEqual("onepanel", payload["command"])
        self.assertIn("<panel|firewall|cronjob|task>", payload["hint"])
        self.assertNotIn("ingress", payload["hint"])
        self.assertNotIn("container", payload["hint"])
        self.assertNotIn("app", payload["hint"])
        self.assertNotIn("project", payload["hint"])

    def test_removed_onepanel_subcommands_are_rejected_by_argparse(self) -> None:
        for scope in ("ingress", "container", "app", "project", "ledger", "suite", "fixture", "ingress"):
            with self.subTest(scope=scope):
                result = run_cli("onepanel", "--env", "wsl", scope, "--help")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("invalid choice", result.stderr)


# ======================================================================
# From: test_onepanel_plugin_and_skills.py
# ======================================================================

CATALOG_FILE = REPO_ROOT / ".agents" / "skills" / "catalog.yaml"
REQUIRED_DOMAINS = {"infra", "service", "ingress", "app", "project"}
