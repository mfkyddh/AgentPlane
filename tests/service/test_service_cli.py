import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from tests.support.service_cli import (
    _FakeCloudflareClient,
    run_cli,
    run_cli_inline,
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
                    "newapi",
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
            log_file = root / "service-get-newapi.log"
            write_fake_service_ssh(bin_dir)

            result = run_cli(
                "service",
                "get",
                "--target",
                "prod0-main",
                "--name",
                "newapi",
                "--repo-root",
                str(root),
                env_overrides={"PATH": f"{bin_dir}:{os.environ['PATH']}", "FAKE_CMD_LOG": str(log_file)},
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("newapi", payload["payload"]["service"]["name"])
            self.assertEqual("compose", payload["payload"]["service"]["control_plane"])
            self.assertEqual(["restart", "reconcile"], payload["payload"]["service"]["supported_operations"])

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
            self.assertEqual("host", payload["payload"]["checks"]["network_mode"]["actual"])

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
            self.assertEqual("host", payload["payload"]["checks"]["network_mode"]["actual"])
            self.assertFalse(payload["payload"]["projection_handoff"]["required"])
            self.assertEqual("projection", payload["payload"]["projection_handoff"]["steps"][0]["command"])
            self.assertEqual("ledger.refresh", payload["payload"]["projection_handoff"]["steps"][0]["action"])

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

