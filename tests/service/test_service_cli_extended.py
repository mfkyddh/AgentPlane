from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pytest
from agentplane.adapters.service import docker_runtime
from agentplane.domain.service.models import ServiceDefinition
from tests.support.service_cli import (
    run_cli,
    write_fake_service_ssh,
    write_inventory,
)

pytestmark = pytest.mark.integration


class ServiceCliTests(unittest.TestCase):
    def test_service_get_supports_onepanel_backed_runtime_with_restart_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            bin_dir = root / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            log_file = root / "service-get-legacy-runtime.log"
            write_fake_service_ssh(bin_dir)

            result = run_cli(
                "service",
                "get",
                "--target",
                "prod0-main",
                "--name",
                "legacy_runtime",
                "--repo-root",
                str(root),
                env_overrides={"PATH": f"{bin_dir}:{os.environ['PATH']}", "FAKE_CMD_LOG": str(log_file)},
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("legacy_runtime", payload["payload"]["service"]["name"])
            self.assertEqual("onepanel-app", payload["payload"]["service"]["control_plane"])
            self.assertEqual(["restart"], payload["payload"]["service"]["supported_operations"])

    def test_service_verify_checks_onepanel_compose_identity_labels(self) -> None:
        definition = ServiceDefinition(
            name="legacy_project",
            runtime_kind="docker",
            control_plane="onepanel-compose",
            supported_operations=("restart",),
            supported_targets=("prod0-main",),
        )
        inspect_payload = {
            "Name": "legacy-project-prod",
            "Config": {
                "Image": "ghcr.io/example/legacy-project:1.0",
                "Labels": {
                    "com.docker.compose.project": "legacy-project-prod",
                    "com.docker.compose.project.config_files": (
                        "/data/1panel/docker/compose/legacy-project-prod/docker-compose.yml"
                    ),
                },
            },
            "State": {"Status": "running", "Running": True},
            "HostConfig": {"NetworkMode": "bridge"},
        }
        probe = {
            "argv": ["ssh", "prod0-main", "docker inspect legacy-project-prod"],
            "display": "ssh prod0-main docker inspect legacy-project-prod",
            "returncode": 0,
            "stdout": json.dumps(inspect_payload),
            "stderr": "",
            "ok": True,
        }

        with patch("agentplane.adapters.service.docker_runtime.run_shell_command", return_value=probe):
            payload = docker_runtime.verify_container_service(
                Path("."),
                "prod0-main",
                definition,
                {
                    "container_name": "legacy-project-prod",
                    "project_name": "legacy-project-prod",
                    "compose_file": "/data/1panel/docker/compose/legacy-project-prod/docker-compose.yml",
                    "image": "ghcr.io/example/legacy-project:1.0",
                },
            )

        self.assertTrue(payload["ok"])
        self.assertTrue(payload["checks"]["compose_project"]["ok"])
        self.assertTrue(payload["checks"]["compose_config_files"]["ok"])

    def test_service_verify_checks_live_state_for_container_service(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            bin_dir = root / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            log_file = root / "service-verify.log"
            write_fake_service_ssh(bin_dir)

            result = run_cli(
                "service",
                "verify",
                "--target",
                "prod0-main",
                "--name",
                "onepanel_openresty",
                "--repo-root",
                str(root),
                env_overrides={"PATH": f"{bin_dir}:{os.environ['PATH']}", "FAKE_CMD_LOG": str(log_file)},
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("service", payload["command"])
            self.assertEqual("verify", payload["action"])
            self.assertTrue(payload["payload"]["ok"])
            self.assertEqual("infra", payload["payload"]["checks"]["network_mode"]["actual"])
            self.assertFalse(payload["payload"]["projection_handoff"]["required"])
            self.assertEqual("projection", payload["payload"]["projection_handoff"]["steps"][0]["command"])
            self.assertEqual("ledger.refresh", payload["payload"]["projection_handoff"]["steps"][0]["action"])

    def test_container_service_verify_redacts_inspect_stdout_evidence(self) -> None:
        definition = ServiceDefinition(
            name="minio",
            runtime_kind="docker",
            control_plane="compose",
            supported_operations=("restart",),
            supported_targets=("prod0-main",),
        )
        inspect_payload = {
            "Name": "minio-prod",
            "Config": {
                "Image": "minio/minio:RELEASE.2025-04-22T22-12-26Z",
                "Env": ["MINIO_ROOT_PASSWORD=super-secret", "SERVER_PORT=9000"],
            },
            "State": {"Status": "running", "Running": True},
            "HostConfig": {"NetworkMode": "zqf_network"},
        }
        probe = {
            "argv": ["ssh", "prod0-main", "docker inspect minio-prod"],
            "display": "ssh prod0-main docker inspect minio-prod",
            "returncode": 0,
            "stdout": json.dumps(inspect_payload),
            "stderr": "",
            "ok": True,
        }

        with patch("agentplane.adapters.service.docker_runtime.run_shell_command", return_value=probe):
            payload = docker_runtime.verify_container_service(
                Path("."),
                "prod0-main",
                definition,
                {
                    "container_name": "minio-prod",
                    "image": "minio/minio:RELEASE.2025-04-22T22-12-26Z",
                },
            )

        stdout = payload["evidence"][0]["stdout"]
        self.assertTrue(payload["ok"])
        self.assertNotIn("super-secret", stdout)
        self.assertIn("MINIO_ROOT_PASSWORD=<redacted>", stdout)
        self.assertIn("SERVER_PORT=9000", stdout)

    def test_service_plan_rejects_unsupported_operation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)

            result = run_cli(
                "service",
                "plan",
                "--target",
                "prod0-main",
                "--name",
                "postgres",
                "--operation",
                "reload",
                "--repo-root",
                str(root),
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unsupported", result.stderr.lower())

    def test_service_plan_rejects_reconcile_for_onepanel_app_service(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)

            result = run_cli(
                "service",
                "plan",
                "--target",
                "prod0-main",
                "--name",
                "legacy_runtime",
                "--operation",
                "reconcile",
                "--repo-root",
                str(root),
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unsupported", result.stderr.lower())
