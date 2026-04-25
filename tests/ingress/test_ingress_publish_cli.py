import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]


def run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
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
    return subprocess.run(
        [sys.executable, "-m", "agentplane.cli", *args],
        cwd=cwd or REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def write_publish_files(root: Path) -> tuple[Path, Path]:
    config_file = root / "publish.env"
    config_file.write_text(
        "\n".join(
            [
                "PUBLIC_INGRESS_DOMAIN=token.zzzai.cloud",
                "PUBLIC_INGRESS_ZONE_NAME=zzzai.cloud",
                "PUBLIC_INGRESS_RECORD_CONTENT=1.2.3.4",
                "ONEPANEL_DNS_ACCOUNT_NAME=cloudflare-zzzai",
                "ONEPANEL_DNS_ACCOUNT_EMAIL=admin@zzzai.cloud",
                "ONEPANEL_WEBSITE_ALIAS=token",
                "ONEPANEL_WEBSITE_PROXY=http://127.0.0.1:18080",
                "ONEPANEL_CERT_DIR=/data/1panel/www/certs/token-zzzai-cloud",
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


class WebsitePublishCliTests(unittest.TestCase):
    def test_ingress_publish_apply_requires_execute(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file, cloudflare_env_file = write_publish_files(root)

            result = run_cli(
                "ingress",
                "publish",
                "apply",
                "--target",
                "prod0-main",
                "--config-file",
                str(config_file),
                "--cloudflare-env-file",
                str(cloudflare_env_file),
                "--repo-root",
                str(root),
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--execute", result.stderr)

    def test_ingress_publish_plan_wraps_formal_publish_surface(self) -> None:
        from agentplane.cli.ingress import handle_ingress_command

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file, cloudflare_env_file = write_publish_files(root)
            args = SimpleNamespace(
                ingress_action="publish",
                ingress_publish_action="plan",
                target="prod0-main",
                config_file=config_file.name,
                cloudflare_env_file=cloudflare_env_file.name,
                repo_root=str(root),
            )

            with patch(
                "agentplane.cli.ingress.plan_public_ingress",
                return_value={"domain": "token.zzzai.cloud", "steps": [{"kind": "cloudflare_dns"}], "execute_required": True},
            ):
                payload = handle_ingress_command(args)

        self.assertEqual("ingress", payload["command"])
        self.assertEqual("publish.plan", payload["action"])
        self.assertEqual("prod0-main", payload["target"])
        self.assertEqual("token.zzzai.cloud", payload["payload"]["domain"])
        self.assertTrue(payload["payload"]["execute_required"])

    def test_ingress_publish_apply_runs_post_verify(self) -> None:
        from agentplane.cli.ingress import handle_ingress_command

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file, cloudflare_env_file = write_publish_files(root)
            args = SimpleNamespace(
                ingress_action="publish",
                ingress_publish_action="apply",
                target="prod0-main",
                config_file=str(config_file),
                cloudflare_env_file=str(cloudflare_env_file),
                repo_root=str(root),
                execute=True,
            )

            with patch(
                "agentplane.cli.ingress.ensure_public_ingress",
                return_value={"payload": {"ingress": {"id": 9, "alias": "token"}}},
            ) as ensure_publish, patch(
                "agentplane.cli.ingress.verify_public_ingress",
                return_value={"payload": {"ok": True, "failures": [], "checks": {"ingress": {"ok": True}}}},
            ) as verify_publish:
                payload = handle_ingress_command(args)

        ensure_publish.assert_called_once()
        verify_publish.assert_called_once()
        self.assertEqual("publish.apply", payload["action"])
        self.assertTrue(payload["payload"]["ok"])
        self.assertEqual(9, payload["payload"]["result"]["ingress"]["id"])
        follow_through = payload["payload"]["follow_through"]
        self.assertEqual("projection", follow_through["owner_surface"])
        self.assertEqual("ingress.publish", follow_through["source_surface"])
        self.assertIn("projection verification run", follow_through["commands"]["verification"])
        self.assertIn("--target prod0-main", follow_through["commands"]["verification"])
        self.assertIn("projection ledger refresh", follow_through["commands"]["ledger_refresh"])
        self.assertIn("--target prod0-main", follow_through["commands"]["ledger_refresh"])

    def test_ingress_publish_verify_exposes_structured_failures(self) -> None:
        from agentplane.cli.ingress import handle_ingress_command

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file, cloudflare_env_file = write_publish_files(root)
            args = SimpleNamespace(
                ingress_action="publish",
                ingress_publish_action="verify",
                target="prod0-main",
                config_file=str(config_file),
                cloudflare_env_file=str(cloudflare_env_file),
                repo_root=str(root),
            )

            with patch(
                "agentplane.cli.ingress.verify_public_ingress",
                return_value={"payload": {"ok": False, "failures": ["dns_content"], "checks": {"dns_content": {"ok": False}}}},
            ):
                payload = handle_ingress_command(args)

        self.assertEqual("publish.verify", payload["action"])
        self.assertFalse(payload["payload"]["ok"])
        self.assertEqual(["dns_content"], payload["payload"]["failures"])
        follow_through = payload["payload"]["follow_through"]
        self.assertEqual("projection", follow_through["owner_surface"])
        self.assertEqual("ingress.publish", follow_through["source_surface"])


if __name__ == "__main__":
    unittest.main()
