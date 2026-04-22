import unittest

from agentplane.scripts.onepanel.fixture_manager import (
    apply_fixture,
    cleanup_fixture,
    plan_fixture,
    resolve_fixture_spec,
    resolve_suite_targets,
)


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
        self.assertEqual("create", actions["website"])
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

