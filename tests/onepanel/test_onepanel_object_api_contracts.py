from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

import pytest
from agentplane.scripts.onepanel.object_api import (
    FakeLikeExecutorProtocol,
    get_app_catalog,
    get_app_catalog_detail,
    get_compose_project,
    get_container,
    get_ingress,
    get_installed_app,
    get_panel_summary,
    get_task_count,
    load_cronjob,
    load_firewall_base,
    search_containers,
    search_cronjobs,
    search_firewall_rules,
    search_ingresses,
    search_installed_apps,
    search_tasks,
)

pytestmark = pytest.mark.unit

FIXTURE_FILE = Path(__file__).with_name("fixtures") / "object_api_contracts.json"


class ContractFixtureExecutor(FakeLikeExecutorProtocol):
    def __init__(self) -> None:
        payload = json.loads(FIXTURE_FILE.read_text(encoding="utf-8"))
        responses = payload.get("responses")
        if not isinstance(responses, dict):
            raise ValueError("object API contract fixture must define responses")
        self.responses = responses
        self.calls: list[tuple[str, str, dict[str, object] | None]] = []

    def api_request(self, method: str, path: str, body: dict[str, object] | None = None) -> object:
        self.calls.append((method, path, body))
        key = f"{method} {path}"
        if key not in self.responses:
            raise AssertionError(f"Missing contract response for {key}")
        return copy.deepcopy(self.responses[key])

    @property
    def called_keys(self) -> set[str]:
        return {f"{method} {path}" for method, path, _body in self.calls}


class OnePanelObjectApiContractTests(unittest.TestCase):
    def test_provider_read_helpers_match_contract_response_shapes(self) -> None:
        executor = ContractFixtureExecutor()

        panel = get_panel_summary(executor)
        ingresses = search_ingresses(executor, name="token")
        ingress = get_ingress(executor, website_id=4)
        containers = search_containers(executor, name="sub2api-prod", state="running")
        container = get_container(executor, name="sub2api-prod")
        project = get_compose_project(executor, name="sub2api-prod")
        cronjobs = search_cronjobs(executor, info="backup-secrets")
        cronjob = load_cronjob(executor, cronjob_id=2)
        firewall = load_firewall_base(executor, name="port")
        firewall_rules = search_firewall_rules(executor, rule_type="port", info="24443")
        apps = search_installed_apps(executor, name="openresty")
        installed_app = get_installed_app(executor, install_id=3)
        app_catalog = get_app_catalog(executor, app_key="openresty")
        app_detail = get_app_catalog_detail(executor, app_id=91, version="1.27.1", app_type="website")
        tasks = search_tasks(executor, task_type="cronjob", status="success")
        task_count = get_task_count(executor)

        self.assertEqual("v2.1.7", panel["systemVersion"])
        self.assertEqual("token", ingresses["items"][0]["alias"])
        self.assertTrue(ingress["https"]["enable"])
        self.assertEqual("running", containers["items"][0]["state"])
        self.assertEqual("sub2api-prod", container["name"])
        self.assertEqual("sub2api-prod", project["name"])
        self.assertEqual("backup-secrets", cronjobs["items"][0]["name"])
        self.assertEqual("Enable", cronjob["status"])
        self.assertTrue(firewall["isActive"])
        self.assertEqual("24443", firewall_rules["items"][0]["port"])
        self.assertEqual("openresty", apps["items"][0]["appKey"])
        self.assertEqual("Running", installed_app["status"])
        self.assertEqual("OpenResty", app_catalog["name"])
        self.assertIn("dockerCompose", app_detail)
        self.assertEqual("success", tasks["items"][0]["status"])
        self.assertEqual({"executing": 0}, task_count)

        self.assertEqual(set(executor.responses), executor.called_keys)

    def test_provider_read_helpers_send_stable_request_payloads(self) -> None:
        executor = ContractFixtureExecutor()

        search_ingresses(executor, name="token", website_group_id=1, page=2, page_size=50)
        search_containers(executor, name="sub2api-prod", state="running")
        search_cronjobs(executor, info="backup-secrets", group_ids=[7])
        search_firewall_rules(executor, rule_type="port", info="24443", status="accept", strategy="accept")
        search_installed_apps(executor, name="openresty", app_type="website")
        search_tasks(executor, task_type="cronjob", status="success")

        self.assertEqual(
            (
                "POST",
                "/api/v2/websites/search",
                {
                    "page": 2,
                    "pageSize": 50,
                    "name": "token",
                    "websiteGroupId": 1,
                    "orderBy": "created_at",
                    "order": "descending",
                },
            ),
            executor.calls[0],
        )
        self.assertEqual("created_at", executor.calls[1][2]["orderBy"])
        self.assertEqual([7], executor.calls[2][2]["groupIDs"])
        self.assertEqual("port", executor.calls[3][2]["type"])
        self.assertEqual("website", executor.calls[4][2]["type"])
        self.assertEqual({"page": 1, "pageSize": 20, "type": "cronjob", "status": "success"}, executor.calls[5][2])
