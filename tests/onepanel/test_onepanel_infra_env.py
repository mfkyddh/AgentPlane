from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pytest
from agentplane.scripts.onepanel import (
    env_targets,  # type: ignore  # noqa: E402
    )
from agentplane.scripts.onepanel.fixture_manager import (
    apply_fixture,
    cleanup_fixture,
    plan_fixture,
    resolve_fixture_spec,
    resolve_suite_targets,
)
from tests.support.paths import REPO_ROOT

pytestmark = pytest.mark.integration

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
ONEPANEL_SCRIPTS = REPO_ROOT / "agentplane" / "scripts" / "onepanel"
if str(ONEPANEL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(ONEPANEL_SCRIPTS))


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
        self.assertIn("onepanel-api.env", str(prod0_target.api_env_file))
        self.assertIn("onepanel-api.env", str(prod2_target.api_env_file))

    def test_supported_targets_include_prod2(self) -> None:
        self.assertIn("prod0-main", env_targets.supported_targets())

    def test_phase4_lane12_projection_fixture_apply_requires_execute_for_mutation_guardrail(self) -> None:
        result = self._run_cli(
            "project",
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
