import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml
from agentplane.adapters.service import docker_runtime
from agentplane.domain.service.models import ServiceDefinition
from tests.support.service_cli import (
    run_cli,
    write_fake_service_ssh,
    write_inventory,
)


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
            self.assertEqual("relay.zzzai.fun", endpoint["domain"])

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
                    {"prepend__rules": ["DOMAIN-SUFFIX,zzzai.fun,DIRECT"]},
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
            self.assertEqual("relay.zzzai.fun", payload["payload"]["resolved"]["server"])
            self.assertEqual(24443, payload["payload"]["resolved"]["port"])
            self.assertEqual("Prod2|Relay", payload["payload"]["resolved"]["node_name"])

            rendered = yaml.safe_load(output_file.read_text(encoding="utf-8"))
            self.assertEqual("Prod2|Relay", rendered["proxies"][0]["name"])
            self.assertEqual("relay.zzzai.fun", rendered["proxies"][0]["server"])
            self.assertEqual(["Prod2|Relay", "直接连接"], rendered["proxy-groups"][0]["proxies"])
            self.assertEqual(
                ["DOMAIN-SUFFIX,zzzai.fun,DIRECT", "DOMAIN-SUFFIX,openai.com,GPT", "MATCH,国外流量"],
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



if __name__ == "__main__":
    unittest.main()

