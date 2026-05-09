from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from agentplane.adapters.service import docker_runtime
from agentplane.domain.service import lifecycle as service_lifecycle
from agentplane.domain.service.models import ServiceDefinition
from tests.support.service_cli import (
    _FakeCloudflareClient,
    run_cli,
    run_cli_inline,
    write_fake_service_ssh,
    write_inventory,
)

pytestmark = pytest.mark.e2e


# ======================================================================
# From: test_service_public_endpoint_cli.py
# ======================================================================


class ServicePublicEndpointCliTests(unittest.TestCase):
    def test_service_public_endpoint_verify_checks_dns_and_certificate_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            bin_dir = root / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            log_file = root / "service-public-endpoint-verify.log"
            env_file = root / "cloudflare.env"
            env_file.write_text("CLOUDFLARE_API_TOKEN=test-token\n", encoding="utf-8")
            write_fake_service_ssh(bin_dir)

            with (
                patch("agentplane.domain.service.public_endpoint.CloudflareClient", _FakeCloudflareClient),
                patch.dict(
                    os.environ,
                    {"PATH": f"{bin_dir}:{os.environ['PATH']}", "FAKE_CMD_LOG": str(log_file)},
                    clear=False,
                ),
            ):
                exit_code, stdout, stderr = run_cli_inline(
                    "service",
                    "public-endpoint",
                    "verify",
                    "--target",
                    "prod0-main",
                    "--name",
                    "relay-trojan",
                    "--cloudflare-env-file",
                    str(env_file),
                    "--repo-root",
                    str(root),
                )

            self.assertEqual(exit_code, 0, msg=stderr)
            payload = json.loads(stdout)
            self.assertEqual("public-endpoint.verify", payload["action"])
            self.assertTrue(payload["payload"]["ok"])
            self.assertTrue(payload["payload"]["checks"]["dns_exists"]["ok"])
            self.assertTrue(payload["payload"]["checks"]["dns_content"]["ok"])
            self.assertTrue(payload["payload"]["checks"]["cert_fullchain_readable"]["ok"])
            self.assertTrue(payload["payload"]["checks"]["cert_privkey_readable"]["ok"])
            self.assertTrue(payload["payload"]["checks"]["renew_script_executable"]["ok"])
            self.assertTrue(payload["payload"]["checks"]["renew_cron_present"]["ok"])

    def test_service_public_endpoint_plan_and_apply_reconcile_dns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            env_file = root / "cloudflare.env"
            env_file.write_text("CLOUDFLARE_API_TOKEN=test-token\n", encoding="utf-8")

            plan_result = run_cli(
                "service",
                "public-endpoint",
                "plan",
                "--target",
                "prod0-main",
                "--name",
                "relay-trojan",
                "--cloudflare-env-file",
                str(env_file),
                "--repo-root",
                str(root),
            )

            self.assertEqual(plan_result.returncode, 0, msg=plan_result.stderr)
            plan_payload = json.loads(plan_result.stdout)
            self.assertEqual("public-endpoint.plan", plan_payload["action"])
            self.assertEqual("reconcile", plan_payload["payload"]["operation"])
            step = plan_payload["payload"]["steps"][0]
            self.assertIn("ensure_cloudflare_dns_record.py", step["display"])
            self.assertIn("relay.example.org", step["display"])

            bin_dir = root / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            log_file = root / "service-public-endpoint-apply.log"
            write_fake_service_ssh(bin_dir)
            with (
                patch("agentplane.domain.service.public_endpoint.CloudflareClient", _FakeCloudflareClient),
                patch(
                    "agentplane.scripts.internal.ensure_cloudflare_dns_record.CloudflareClient",
                    _FakeCloudflareClient,
                ),
                patch.dict(
                    os.environ,
                    {"PATH": f"{bin_dir}:{os.environ['PATH']}", "FAKE_CMD_LOG": str(log_file)},
                    clear=False,
                ),
            ):
                exit_code, stdout, stderr = run_cli_inline(
                    "service",
                    "public-endpoint",
                    "apply",
                    "--target",
                    "prod0-main",
                    "--name",
                    "relay-trojan",
                    "--cloudflare-env-file",
                    str(env_file),
                    "--execute",
                    "--repo-root",
                    str(root),
                )

            self.assertEqual(exit_code, 0, msg=stderr)
            apply_payload = json.loads(stdout)
            self.assertEqual("public-endpoint.apply", apply_payload["action"])
            self.assertTrue(apply_payload["payload"]["ok"])
            self.assertEqual("created", apply_payload["payload"]["results"][0]["parsed"]["action"])
            self.assertTrue(apply_payload["payload"]["verified"]["ok"])
