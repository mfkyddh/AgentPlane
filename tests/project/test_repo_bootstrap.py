from __future__ import annotations

import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

import pytest
from tests.support.cli import run_agentplane_cli as run_cli
from tests.support.paths import REPO_ROOT

pytestmark = pytest.mark.e2e


def _listed_help_commands(help_text: str) -> set[str]:
    return set(re.findall(r"(?m)^\s{2,}([a-z][a-z0-9-]*)\b(?:\s{2,}|\s*$)", help_text))


def _listed_targets(help_text: str) -> set[str]:
    targets: set[str] = set()
    for choice_group in re.findall(r"\{([^}]+)\}", help_text):
        for token in choice_group.split(","):
            candidate = token.strip()
            if candidate in {"wsl", "prod0-main", "prod0-main"}:
                targets.add(candidate)
    return targets


def _assert_help_commands(
    testcase: unittest.TestCase,
    help_text: str,
    *,
    expected: set[str] | None = None,
    absent: set[str] | None = None,
) -> set[str]:
    commands = _listed_help_commands(help_text)
    if expected is not None:
        testcase.assertTrue(expected.issubset(commands), msg=f"missing commands: {sorted(expected - commands)}")
    if absent is not None:
        testcase.assertTrue(absent.isdisjoint(commands), msg=f"unexpected commands: {sorted(absent & commands)}")
    return commands


def _write_fake_onepanel_router(source_root: Path, *, include_extra_route: bool = False) -> None:
    router_root = source_root / "agent" / "router"
    router_root.mkdir(parents=True, exist_ok=True)
    extra_route = '\n\t\tbaRouter.POST("/inspect", baseApi.Inspect)' if include_extra_route else ""
    (router_root / "ro_container.go").write_text(
        f"""package router

func (s *ContainerRouter) InitRouter(Router *gin.RouterGroup) {{
\tbaRouter := Router.Group("containers")
\tbaseApi := v2.ApiGroupApp.BaseApi
\t{{
\t\tbaRouter.POST("/search", baseApi.SearchContainer)
\t\tbaRouter.GET("/status", baseApi.LoadContainerStatus){extra_route}
\t}}
}}
""",
        encoding="utf-8",
    )
    (router_root / "ro_website.go").write_text(
        """package router

func (a *WebsiteRouter) InitRouter(Router *gin.RouterGroup) {
\twebsiteRouter := Router.Group("websites")
\tbaseApi := v2.ApiGroupApp.BaseApi
\t{
\t\twebsiteRouter.POST("", baseApi.CreateWebsite)
\t\twebsiteRouter.GET("/:id", baseApi.GetWebsite)
\t}
}
""",
        encoding="utf-8",
    )


# ======================================================================
# From: test_bootstrap_cli.py
# ======================================================================


def seed_bootstrap_templates(root: Path) -> None:
    (root / "templates" / "env").mkdir(parents=True, exist_ok=True)
    (root / "templates" / "ssh").mkdir(parents=True, exist_ok=True)
    (root / "templates" / "services").mkdir(parents=True, exist_ok=True)
    (root / "templates" / "secrets" / "local" / "control-plane").mkdir(parents=True, exist_ok=True)
    (root / "templates" / "secrets" / "targets" / "_template").mkdir(parents=True, exist_ok=True)
    (root / "inventory" / "servers" / "wsl").mkdir(parents=True, exist_ok=True)
    (root / "inventory" / "servers" / "prod0-main").mkdir(parents=True, exist_ok=True)
    (root / "inventory" / "servers" / "prod0-main").mkdir(parents=True, exist_ok=True)

    (root / "templates" / "env" / "prod-jump.env.example").write_text(
        "CLOUDFLARE_API_TOKEN=replace-with-api-token\n",
        encoding="utf-8",
    )
    (root / "templates" / "ssh" / "config.example").write_text(
        "Host prod0-main\n  HostName REPLACE_WITH_PRIMARY_IP\n",
        encoding="utf-8",
    )
    (root / "templates" / "services" / "onepanel-login.env.example").write_text(
        "ONEPANEL_USERNAME=replace-with-onepanel-username\nONEPANEL_PASSWORD=replace-with-onepanel-password\n",
        encoding="utf-8",
    )
    (root / "templates" / "secrets" / "local" / "control-plane" / "README.md").write_text(
        "local control-plane\n",
        encoding="utf-8",
    )
    (root / "templates" / "secrets" / "targets" / "_template" / "README.md").write_text(
        "target <target>\n",
        encoding="utf-8",
    )
    for target in ("wsl", "prod0-main", "prod0-main"):
        (root / "inventory" / "servers" / target / "inventory.json").write_text(
            json.dumps({"target": target}, ensure_ascii=False),
            encoding="utf-8",
        )


def write_takeover_ready_ssh_contract(root: Path) -> None:
    (root / "secrets" / "ssh" / "keys").mkdir(parents=True, exist_ok=True)
    (root / "secrets" / "ssh" / "config").write_text(
        "Host prod0-main 1.2.3.4\n"
        "  HostName 1.2.3.4\n"
        "  User root\n"
        "  IdentityFile <repo-root>/secrets/ssh/keys/prod0-main.pem\n"
        "\n"
        "Host prod0-main 5.6.7.8\n"
        "  HostName 5.6.7.8\n"
        "  User root\n"
        "  IdentityFile <repo-root>/secrets/ssh/keys/prod0-main.pem\n",
        encoding="utf-8",
    )
    (root / "secrets" / "ssh" / "keys" / "prod0-main.pem").write_text("demo-prod0", encoding="utf-8")
    (root / "secrets" / "ssh" / "keys" / "prod0-main.pem").write_text("demo-prod2", encoding="utf-8")


class BootstrapCliTests(unittest.TestCase):
    def test_bootstrap_init_secrets_creates_only_takeover_truth_scaffold(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed_bootstrap_templates(root)

            result = run_cli("infra", "bootstrap", "init-secrets", "--repo-root", str(root))

            self.assertEqual(0, result.returncode, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("infra", payload["command"])
            self.assertEqual("bootstrap.init-secrets", payload["action"])
            self.assertTrue((root / "secrets" / "local" / "control-plane").is_dir())
            self.assertTrue((root / "secrets" / "targets" / "wsl").is_dir())
            self.assertTrue((root / "secrets" / "targets" / "prod0-main").is_dir())
            self.assertTrue((root / "secrets" / "targets" / "prod0-main").is_dir())
            self.assertTrue((root / "secrets" / "ssh" / "config").is_file())
            self.assertTrue((root / "secrets" / "ssh" / "keys").is_dir())
            self.assertFalse((root / "secrets" / "env" / "prod-jump.env").exists())
            self.assertFalse((root / "secrets" / "services" / "onepanel-login.prod0-main.env").exists())

    def test_bootstrap_verify_secrets_does_not_print_secret_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed_bootstrap_templates(root)
            write_takeover_ready_ssh_contract(root)

            result = run_cli("infra", "bootstrap", "verify-secrets", "--repo-root", str(root))

            self.assertEqual(0, result.returncode, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["payload"]["ok"])

    def test_bootstrap_inspect_local_reports_host_profile_and_path_policy(self) -> None:
        result = run_cli("infra", "bootstrap", "inspect-local", "--repo-root", str(REPO_ROOT))

        self.assertEqual(0, result.returncode, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual("infra", payload["command"])
        self.assertEqual("bootstrap.inspect-local", payload["action"])
        self.assertEqual("canonical-ref-only", payload["payload"]["path_policy"]["truth"])
        self.assertIn("host_profile", payload["payload"])
        self.assertIn("required_truths", payload["payload"]["contract"])
        self.assertIn("projection_only", payload["payload"]["contract"])
        cli_entrypoint = payload["payload"]["cli_entrypoint"]
        self.assertEqual("agentplane", cli_entrypoint["command"])
        self.assertIn("uv run python -m agentplane.cli", cli_entrypoint["fallback_commands"])
        self.assertIn("uv tool install -e", cli_entrypoint["install_command"])

    def test_bootstrap_verify_secrets_requires_structured_ssh_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed_bootstrap_templates(root)
            (root / "secrets" / "ssh").mkdir(parents=True, exist_ok=True)
            (root / "secrets" / "ssh" / "config").write_text(
                "Host prod0-main\n"
                "  HostName 1.2.3.4\n"
                "  User root\n"
                "  IdentityFile <repo-root>/secrets/ssh/keys/prod0-main.pem\n",
                encoding="utf-8",
            )

            result = run_cli("infra", "bootstrap", "verify-secrets", "--repo-root", str(root))

            self.assertEqual(0, result.returncode, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["payload"]["ok"])
            issues = payload["payload"]["checks"][0]["issues"]
            self.assertIn("missing-ssh-key:prod0-main.pem", issues)

    def test_bootstrap_doctor_reports_projection_warnings_without_blocking_takeover(self) -> None:
        from unittest.mock import patch

        from agentplane.domain.infra.handlers import run_doctor

        def _fake_inspect_local(repo_root: Path) -> dict:
            return {
                "linux_backend": {"available": True, "backend_type": "linux-native"},
                "cli_entrypoint": {"available": True, "command": "agentplane"},
                "workspace": {},
                "bootstrap_targets": [],
                "contract": {},
                "path_policy": {},
            }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed_bootstrap_templates(root)
            write_takeover_ready_ssh_contract(root)
            (root / "secrets" / "env").mkdir(parents=True, exist_ok=True)
            (root / "secrets" / "env" / "prod-jump.env").write_text(
                "export PROJECT_SSH_CONFIG=<repo-root>/secrets/ssh/config\n",
                encoding="utf-8",
            )

            with patch("agentplane.runtime.bootstrap.inspect_local_bootstrap", _fake_inspect_local):
                payload = run_doctor(root)

            self.assertTrue(payload["ok"])
            self.assertTrue(payload["secrets"]["ok"])
            self.assertFalse(payload["projections"]["ok"])
            readiness = {check["name"]: check for check in payload["readiness_checks"]}
            self.assertEqual("warning", readiness["projection-compat"]["severity"])
            self.assertEqual("warning", readiness["global-cli-entrypoint"]["severity"])


