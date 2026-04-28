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

class ServiceCliTests(unittest.TestCase):
    def test_service_search_lists_formal_managed_services(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)

            result = run_cli("service", "search", "--target", "prod0-main", "--repo-root", str(root))

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("service", payload["command"])
            self.assertEqual("search", payload["action"])
            self.assertEqual("prod0-main", payload["target"])
            names = {item["name"] for item in payload["payload"]["items"]}
            self.assertEqual(
                {
                    "postgres",
                    "redis",
                    "minio",
                    "mihomo",
                    "onepanel_openresty",
                    "sampleapi",
                    "relay-trojan",
                    "relay-trojan-host",
                    "legacy_runtime",
                    "legacy_project",
                },
                names,
            )

    def test_service_get_returns_declared_shape_and_supported_operations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            bin_dir = root / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            log_file = root / "service-get.log"
            write_fake_service_ssh(bin_dir)

            result = run_cli(
                "service",
                "get",
                "--target",
                "prod0-main",
                "--name",
                "postgres",
                "--repo-root",
                str(root),
                env_overrides={"PATH": f"{bin_dir}:{os.environ['PATH']}", "FAKE_CMD_LOG": str(log_file)},
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("service", payload["command"])
            self.assertEqual("get", payload["action"])
            self.assertEqual("postgres", payload["payload"]["service"]["name"])
            self.assertIn("restart", payload["payload"]["service"]["supported_operations"])
            self.assertIn("reconcile", payload["payload"]["service"]["supported_operations"])

    def test_service_get_supports_dynamic_compose_service_with_reconcile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            bin_dir = root / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            log_file = root / "service-get-sampleapi.log"
            write_fake_service_ssh(bin_dir)

            result = run_cli(
                "service",
                "get",
                "--target",
                "prod0-main",
                "--name",
                "sampleapi",
                "--repo-root",
                str(root),
                env_overrides={"PATH": f"{bin_dir}:{os.environ['PATH']}", "FAKE_CMD_LOG": str(log_file)},
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("sampleapi", payload["payload"]["service"]["name"])
            self.assertEqual("compose", payload["payload"]["service"]["control_plane"])
            self.assertEqual(["restart", "reconcile"], payload["payload"]["service"]["supported_operations"])

    def test_service_plan_reconcile_syncs_tracked_compose_asset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            compose_file = root / "infra" / "compose" / "sampleapi" / "docker-compose.prod0.yml"
            compose_file.parent.mkdir(parents=True, exist_ok=True)
            compose_file.write_text("services:\n  sampleapi:\n    image: ghcr.io/example/sampleapi:2026.04\n", encoding="utf-8")

            result = run_cli(
                "service",
                "plan",
                "--target",
                "prod0-main",
                "--name",
                "sampleapi",
                "--operation",
                "reconcile",
                "--repo-root",
                str(root),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            steps = payload["payload"]["steps"]
            self.assertEqual(4, len(steps))
            self.assertIn("mkdir -p /opt/agentplane/infra/compose/sampleapi", steps[0]["display"])
            self.assertIn("ln -s /opt/env_ubuntu/secrets /opt/agentplane/secrets", steps[1]["display"])
            self.assertIn("scp", steps[2]["argv"])
            self.assertIn("docker-compose.prod0.yml", steps[2]["display"])
            self.assertIn("docker compose -f docker-compose.prod0.yml up -d", steps[3]["display"])

    def test_service_get_and_verify_relay_trojan_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            bin_dir = root / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            get_log = root / "service-get-relay-trojan.log"
            verify_log = root / "service-verify-relay-trojan.log"
            write_fake_service_ssh(bin_dir)

            get_result = run_cli(
                "service",
                "get",
                "--target",
                "prod0-main",
                "--name",
                "relay-trojan",
                "--repo-root",
                str(root),
                env_overrides={"PATH": f"{bin_dir}:{os.environ['PATH']}", "FAKE_CMD_LOG": str(get_log)},
            )

            self.assertEqual(get_result.returncode, 0, msg=get_result.stderr)
            payload = json.loads(get_result.stdout)
            self.assertEqual("relay-trojan", payload["payload"]["service"]["name"])
            declared = payload["payload"]["service"]["declared"]
            self.assertEqual("0.0.0.0:24443", declared["host_binding"])
            endpoint = declared["public_endpoint"]
            self.assertEqual("relay.example.org", endpoint["domain"])

            verify_result = run_cli(
                "service",
                "verify",
                "--target",
                "prod0-main",
                "--name",
                "relay-trojan",
                "--repo-root",
                str(root),
                env_overrides={"PATH": f"{bin_dir}:{os.environ['PATH']}", "FAKE_CMD_LOG": str(verify_log)},
            )

            self.assertEqual(verify_result.returncode, 0, msg=verify_result.stderr)
            verify_payload = json.loads(verify_result.stdout)
            host_binding_check = verify_payload["payload"]["checks"]["host_binding"]
            self.assertTrue(host_binding_check["ok"])

    def test_service_verify_allows_host_network_without_ports_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            bin_dir = root / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            log_file = root / "service-verify-relay-trojan-host.log"
            write_fake_service_ssh(bin_dir)

            result = run_cli(
                "service",
                "verify",
                "--target",
                "prod0-main",
                "--name",
                "relay-trojan-host",
                "--repo-root",
                str(root),
                env_overrides={"PATH": f"{bin_dir}:{os.environ['PATH']}", "FAKE_CMD_LOG": str(log_file)},
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            host_binding_check = payload["payload"]["checks"]["host_binding"]
            self.assertTrue(host_binding_check["ok"])
            self.assertEqual("infra", payload["payload"]["checks"]["network_mode"]["actual"])

    def test_service_materialize_renders_relay_clash_profile_from_service_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            source_file = root / "source.yaml"
            merge_file = root / "merge.yaml"
            output_file = root / "relay-local.yaml"
            source_file.write_text(
                yaml.safe_dump(
                    {
                        "proxies": [
                            {"name": "旧节点A", "type": "ss", "server": "a.example.com", "port": 443, "cipher": "aes-128-gcm", "password": "x"},
                            {"name": "旧节点B", "type": "ss", "server": "b.example.com", "port": 443, "cipher": "aes-128-gcm", "password": "y"},
                        ],
                        "proxy-groups": [
                            {"name": "国外流量", "type": "select", "proxies": ["旧节点A", "旧节点B", "直接连接"]},
                            {"name": "GPT", "type": "select", "proxies": ["国外流量", "旧节点A", "DIRECT"]},
                        ],
                        "rules": ["DOMAIN-SUFFIX,openai.com,GPT", "MATCH,国外流量"],
                    },
                    allow_unicode=True,
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
            merge_file.write_text(
                yaml.safe_dump(
                    {"prepend__rules": ["DOMAIN-SUFFIX,example.org,DIRECT"]},
                    allow_unicode=True,
                    sort_keys=False,
                ),
                encoding="utf-8",
            )

            result = run_cli(
                "service",
                "materialize",
                "--target",
                "prod0-main",
                "--name",
                "relay-trojan",
                "--artifact",
                "clash-local-profile",
                "--source",
                str(source_file),
                "--merge-template",
                str(merge_file),
                "--output",
                str(output_file),
                "--password",
                "test-password",
                "--repo-root",
                str(root),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("service", payload["command"])
            self.assertEqual("materialize", payload["action"])
            self.assertEqual("clash-local-profile", payload["payload"]["artifact"])
            self.assertEqual("relay.example.org", payload["payload"]["resolved"]["server"])
            self.assertEqual(24443, payload["payload"]["resolved"]["port"])
            self.assertEqual("Prod2|Relay", payload["payload"]["resolved"]["node_name"])

            rendered = yaml.safe_load(output_file.read_text(encoding="utf-8"))
            self.assertEqual("Prod2|Relay", rendered["proxies"][0]["name"])
            self.assertEqual("relay.example.org", rendered["proxies"][0]["server"])
            self.assertEqual(["Prod2|Relay", "直接连接"], rendered["proxy-groups"][0]["proxies"])
            self.assertEqual(
                ["DOMAIN-SUFFIX,example.org,DIRECT", "DOMAIN-SUFFIX,openai.com,GPT", "MATCH,国外流量"],
                rendered["rules"],
            )

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

# ======================================================================
# From: test_service_apply_cli.py
# ======================================================================

class ServiceApplyCliTests(unittest.TestCase):
    def test_service_apply_restarts_systemd_service_and_verifies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            bin_dir = root / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            log_file = root / "service-apply-mihomo.log"
            write_fake_service_ssh(bin_dir)

            result = run_cli(
                "service",
                "apply",
                "--target",
                "prod0-main",
                "--name",
                "mihomo",
                "--operation",
                "restart",
                "--execute",
                "--repo-root",
                str(root),
                env_overrides={"PATH": f"{bin_dir}:{os.environ['PATH']}", "FAKE_CMD_LOG": str(log_file)},
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            plan = json.loads(
                run_cli(
                    "service",
                    "plan",
                    "--target",
                    "prod0-main",
                    "--name",
                    "mihomo",
                    "--operation",
                    "restart",
                    "--repo-root",
                    str(root),
                ).stdout
            )
            self.assertEqual("service", payload["command"])
            self.assertEqual("apply", payload["action"])
            self.assertTrue(payload["payload"]["ok"])
            self.assertTrue(payload["payload"]["verified"]["ok"])
            self.assertEqual(
                plan["payload"]["steps"][0]["argv"],
                payload["payload"]["results"][0]["argv"],
            )
            log_text = log_file.read_text(encoding="utf-8")
            self.assertIn("systemctl restart mihomo", log_text)
            self.assertIn("systemctl is-active mihomo", log_text)

    def test_service_apply_reconcile_uses_remote_compose_path_and_verifies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            bin_dir = root / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            log_file = root / "service-apply-postgres.log"
            write_fake_service_ssh(bin_dir)

            result = run_cli(
                "service",
                "apply",
                "--target",
                "prod0-main",
                "--name",
                "postgres",
                "--operation",
                "reconcile",
                "--execute",
                "--repo-root",
                str(root),
                env_overrides={"PATH": f"{bin_dir}:{os.environ['PATH']}", "FAKE_CMD_LOG": str(log_file)},
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            plan = json.loads(
                run_cli(
                    "service",
                    "plan",
                    "--target",
                    "prod0-main",
                    "--name",
                    "postgres",
                    "--operation",
                    "reconcile",
                    "--repo-root",
                    str(root),
                ).stdout
            )
            self.assertTrue(payload["payload"]["ok"])
            self.assertTrue(payload["payload"]["verified"]["ok"])
            self.assertEqual(
                plan["payload"]["steps"][0]["argv"],
                payload["payload"]["results"][0]["argv"],
            )
            self.assertTrue(plan["payload"]["projection_handoff"]["required"])
            self.assertTrue(payload["payload"]["projection_handoff"]["required"])
            self.assertEqual("projection", payload["payload"]["projection_handoff"]["steps"][0]["command"])
            self.assertEqual("ledger.refresh", payload["payload"]["projection_handoff"]["steps"][0]["action"])
            log_text = log_file.read_text(encoding="utf-8")
            self.assertIn("cd /opt/agentplane/infra/compose/postgres && docker compose -f docker-compose.prod0.yml up -d", log_text)
            self.assertIn("docker inspect postgres18-prod", log_text)

# ======================================================================
# From: test_service_lifecycle.py
# ======================================================================

class ServiceLifecycleTests(unittest.TestCase):
    def test_plan_onboard_and_offboard_cycles(self):
        base_services = {
            "postgres": {"container_name": "postgres18"},
        }
        next_services, evidence = service_lifecycle.plan_service_registry_onboard(
            base_services,
            service_key="sampleapi",
            entry={"container_name": "sampleapi-prod", "control_plane": "compose"},
        )
        self.assertIn("sampleapi", next_services)
        self.assertEqual(next_services["sampleapi"]["container_name"], "sampleapi-prod")
        self.assertFalse(evidence["replaced"])
        self.assertEqual(evidence["action"], "upsert")

        replaced_services, replaced_evidence = service_lifecycle.plan_service_registry_onboard(
            next_services,
            service_key="sampleapi",
            entry={"container_name": "sampleapi-prod", "control_plane": "compose"},
            allow_replace=True,
        )
        self.assertTrue(replaced_evidence["replaced"])
        self.assertEqual(replaced_services["sampleapi"]["container_name"], "sampleapi-prod")

        offboarded_services, remove_evidence = service_lifecycle.plan_service_registry_offboard(
            replaced_services,
            service_key="sampleapi",
        )
        self.assertNotIn("sampleapi", offboarded_services)
        self.assertEqual(remove_evidence["action"], "remove")
        self.assertEqual(remove_evidence["service_key"], "sampleapi")

        with self.assertRaises(ValueError):
            service_lifecycle.plan_service_registry_offboard(
                offboarded_services,
                service_key="sampleapi",
            )

    def test_plan_rejects_invalid_entries(self):
        base_services = {}
        with self.assertRaises(ValueError):
            service_lifecycle.plan_service_registry_onboard(
                base_services,
                service_key="docker",
                entry={"container_name": "ignored"},
            )
        with self.assertRaises(ValueError):
            service_lifecycle.plan_service_registry_onboard(
                base_services,
                service_key="sampleapi",
                entry={"container_name": " ", "control_plane": "compose"},
            )
        with self.assertRaises(ValueError):
            service_lifecycle.plan_service_registry_onboard(
                base_services,
                service_key="sampleapi",
                entry={"container_name": "foo", "control_plane": "invalid"},
            )

    def test_apply_round_trip_updates_inventory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            target = "wsl"
            inventory_file = self._write_inventory(repo_root, target, {"postgres": {"container_name": "postgres18"}})

            onboard_result = service_lifecycle.apply_service_onboard(
                repo_root=repo_root,
                target=target,
                service_key="sampleapi",
                entry={"container_name": " sampleapi-prod ", "control_plane": "compose"},
            )
            self.assertTrue(onboard_result.changed)
            payload = json.loads(inventory_file.read_text(encoding="utf-8").strip())
            self.assertIn("sampleapi", payload["services"])
            self.assertEqual(payload["services"]["sampleapi"]["container_name"], "sampleapi-prod")

            offboard_result = service_lifecycle.apply_service_offboard(
                repo_root=repo_root,
                target=target,
                service_key="sampleapi",
            )
            self.assertTrue(offboard_result.changed)
            payload_after = json.loads(inventory_file.read_text(encoding="utf-8").strip())
            self.assertNotIn("sampleapi", payload_after["services"])

    def test_service_verify_separates_ledger_fields_and_observation(self) -> None:
        from agentplane.domain.service.handlers import verify_service

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            self._write_inventory(
                repo_root,
                "prod0-main",
                {
                    "postgres": {
                        "container_name": "postgres18-prod",
                        "control_plane": "compose",
                        "image": "postgres:18.3",
                    }
                },
            )

            with patch(
                "agentplane.domain.service.handlers.verify_container_service",
                return_value={
                    "ok": True,
                    "checks": {"running": {"ok": True, "actual": "running"}},
                    "evidence": [{"kind": "probe", "value": "docker inspect postgres18-prod"}],
                    "failures": [],
                },
            ):
                payload = verify_service(repo_root, "prod0-main", "postgres")

        self.assertTrue(payload["ok"])
        self.assertEqual("targets/prod0-main/services/postgres", payload["canonical_ref"])
        self.assertEqual("targets/prod0-main/services/postgres", payload["ledger_fields"]["canonical_ref"])
        self.assertEqual("postgres", payload["ledger_fields"]["name"])
        self.assertNotIn("evidence", payload["ledger_fields"])
        self.assertIn("live", payload["verification_fields"])
        self.assertEqual(
            [{"kind": "probe", "value": "docker inspect postgres18-prod"}],
            payload["verification_fields"]["live"]["evidence"],
        )

    def _write_inventory(self, repo_root: Path, target: str, services: dict[str, dict[str, str]]) -> Path:
        server_dir = repo_root / "inventory" / "servers" / target
        server_dir.mkdir(parents=True, exist_ok=True)
        inventory_file = server_dir / "inventory.json"
        payload = {"services": services}
        inventory_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return inventory_file

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

            with patch("agentplane.domain.service.public_endpoint.CloudflareClient", _FakeCloudflareClient), patch.dict(
                os.environ,
                {"PATH": f"{bin_dir}:{os.environ['PATH']}", "FAKE_CMD_LOG": str(log_file)},
                clear=False,
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
            with patch("agentplane.domain.service.public_endpoint.CloudflareClient", _FakeCloudflareClient), patch(
                "agentplane.scripts.internal.ensure_cloudflare_dns_record.CloudflareClient",
                _FakeCloudflareClient,
            ), patch.dict(
                os.environ,
                {"PATH": f"{bin_dir}:{os.environ['PATH']}", "FAKE_CMD_LOG": str(log_file)},
                clear=False,
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
