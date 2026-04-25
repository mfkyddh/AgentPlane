import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]


def run_cli(*args: str, cwd: Path | None = None, env_overrides: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = None
    if cwd is None:
        repo_root: Path | None = None
        for idx, token in enumerate(args):
            if token == "--repo-root" and idx + 1 < len(args):
                repo_root = Path(args[idx + 1])
                break
            if token.startswith("--repo-root="):
                repo_root = Path(token.split("=", 1)[1])
                break
        if repo_root is not None:
            cwd = repo_root
            env = os.environ.copy()
            repo_path = str(REPO_ROOT)
            existing = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = repo_path if not existing else f"{repo_path}:{existing}"
    if env_overrides:
        env = dict(env or os.environ.copy())
        env.update(env_overrides)
    return subprocess.run(
        [sys.executable, "-m", "agentplane.cli", *args],
        cwd=cwd or REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def write_inventory(root: Path) -> None:
    server_root = root / "inventory" / "servers" / "prod2-main"
    server_root.mkdir(parents=True, exist_ok=True)
    (server_root / "README.md").write_text("# prod2-main 摘要\n", encoding="utf-8")
    (server_root / "inventory.json").write_text(
        json.dumps(
            {
                "services": {
                    "public_ingresses": [
                        {
                            "alias": "token",
                            "primary_domain": "token.zzzai.fun",
                            "public_url": "https://token.zzzai.fun",
                            "proxy": "http://127.0.0.1:18080",
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


class FakeWebsiteExecutor:
    def __init__(self, *, existing: dict[str, object] | None, https: dict[str, object] | None = None) -> None:
        self.requests: list[tuple[str, str, dict[str, object] | None]] = []
        self._existing = existing
        self._https = https or {}
        self._created = False

    def api_request(self, method: str, path: str, body: dict[str, object] | None = None) -> object:
        self.requests.append((method, path, body))
        if path == "/api/v2/websites/search":
            if self._existing is None and not self._created:
                return {"items": []}
            website_id = 9 if self._existing is None else int(self._existing["id"])
            alias = "token" if self._existing is None else str(self._existing["alias"])
            primary_domain = "token.zzzai.fun" if self._existing is None else str(self._existing["primaryDomain"])
            proxy = "http://127.0.0.1:18080" if self._existing is None else str(self._existing["proxy"])
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
                "primaryDomain": "token.zzzai.fun",
                "proxy": "http://127.0.0.1:18080",
                "status": "Running",
            }
        if path == "/api/v2/websites/9/https":
            return {"enable": True, "httpsPort": "443", "SSL": {"id": 3}}
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
                "prod2-main",
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

            payload = search_ingresses(root, "prod2-main")

            self.assertEqual(
                [
                    {
                        "alias": "token",
                        "primary_domain": "token.zzzai.fun",
                        "public_url": "https://token.zzzai.fun",
                        "proxy": "http://127.0.0.1:18080",
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
                    "primaryDomain": "token.zzzai.fun",
                    "proxy": "http://127.0.0.1:18080",
                    "status": "Running",
                },
                https={"enable": True, "httpsPort": "443", "SSL": {"id": 3}},
            )

            with patch("agentplane.domain.ingress.handlers._executor_for_target", return_value=executor):
                payload = get_ingress(root, "prod2-main", "token")

            self.assertEqual("token", payload["ingress"]["alias"])
            self.assertEqual("token.zzzai.fun", payload["ingress"]["primary_domain"])
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
                    "primaryDomain": "token.zzzai.fun",
                    "proxy": "http://127.0.0.1:19090",
                    "status": "Running",
                },
                https={"enable": False, "httpsPort": "", "SSL": {"id": 99}},
            )

            with patch("agentplane.domain.ingress.handlers._executor_for_target", return_value=executor):
                payload = verify_ingress(root, "prod2-main", "token")

            self.assertFalse(payload["ok"])
            self.assertTrue(payload["checks"]["alias"]["ok"])
            self.assertFalse(payload["checks"]["proxy"]["ok"])
            self.assertFalse(payload["checks"]["https"]["ok"])
            self.assertEqual(["proxy", "https", "ssl_id"], payload["failures"])

    def test_ingress_plan_reconcile_builds_create_step_for_missing_site(self) -> None:
        from agentplane.domain.ingress.handlers import plan_ingress_operation

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            executor = FakeWebsiteExecutor(existing=None)

            with patch("agentplane.domain.ingress.handlers._executor_for_target", return_value=executor):
                payload = plan_ingress_operation(root, "prod2-main", "token", "reconcile")

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
                target="prod2-main",
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
                target="prod2-main",
                repo_root=str(root),
                write=True,
            )

            payload = handle_ingress_command(args)

            self.assertEqual("ingress", payload["command"])
            self.assertEqual(1, payload["payload"]["counts"]["websites"])
            self.assertTrue((root / "inventory" / "servers" / "prod2-main" / "ledgers" / "websites.json").is_file())
            persisted_inventory = json.loads((root / "inventory" / "servers" / "prod2-main" / "inventory.json").read_text(encoding="utf-8"))
            self.assertEqual("token", persisted_inventory["services"]["public_ingresses"][0]["alias"])
            self.assertEqual(1, persisted_inventory["object_ledgers"]["counts"]["websites"])


if __name__ == "__main__":
    unittest.main()

