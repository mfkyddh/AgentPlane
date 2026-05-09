from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from agentplane.domain.infra import networks as network_domain
from tests.support.cli import run_agentplane_cli as run_cli
from tests.support.constants import CONTAINER_SUB2API
from tests.support.fake_scripts import write_fake_bridge_network_ssh

pytestmark = pytest.mark.e2e


class HostCliTests(unittest.TestCase):
    def test_infra_secrets_init_data_services_wraps_formal_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_cli(
                "infra",
                "secrets",
                "init-data-services",
                "prod0-main",
                "--repo-root",
                str(root),
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual({"command", "action", "target", "payload"}, set(payload))
            self.assertEqual("infra", payload["command"])
            self.assertEqual("secrets.init-data-services", payload["action"])
            self.assertEqual("prod0-main", payload["target"])
            self.assertIn("files", payload["payload"])

    def test_infra_secrets_sync_layout_wraps_sync_host_layout_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            host_root = root / "secrets" / "hosts" / "prod0-main" / "onepanel"
            host_root.mkdir(parents=True, exist_ok=True)
            (host_root / "api.env").write_text("ONEPANEL_API_KEY=demo\n", encoding="utf-8")

            result = run_cli(
                "infra",
                "secrets",
                "sync-layout",
                "prod0-main",
                "--repo-root",
                str(root),
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual({"command", "action", "target", "payload"}, set(payload))
            self.assertEqual("infra", payload["command"])
            self.assertEqual("secrets.sync-layout", payload["action"])
            self.assertEqual("prod0-main", payload["target"])
            self.assertEqual("planned", payload["payload"]["projections"][0]["status"])

    def test_infra_network_audit_uses_formal_host_shape_without_compat_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory_dir = root / "inventory" / "servers" / "prod0-main"
            inventory_dir.mkdir(parents=True, exist_ok=True)
            inventory_dir.joinpath("inventory.json").write_text(
                json.dumps(
                    {
                        "ssh": {"aliases": ["prod0-main"], "user": "root"},
                        "managed_bridge_networks": [
                            {
                                "name": "zqf_network",
                                "driver": "bridge",
                                "subnet": "172.19.0.0/16",
                                "gateway_ip": "172.19.0.1/16",
                                "required_for": [CONTAINER_SUB2API],
                            }
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            (root / "secrets" / "ssh").mkdir(parents=True, exist_ok=True)
            (root / "secrets" / "ssh" / "config").write_text("Host prod0-main\n", encoding="utf-8")
            bin_dir = root / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            log_file = root / "network-audit.log"
            state_dir = root / "fake-network-state"
            state_dir.mkdir(parents=True, exist_ok=True)
            write_fake_bridge_network_ssh(bin_dir)

            result = run_cli(
                "infra",
                "network",
                "audit",
                "prod0-main",
                "--repo-root",
                str(root),
                env_overrides={
                    "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
                    "FAKE_CMD_LOG": str(log_file),
                    "FAKE_NETWORK_STATE_DIR": str(state_dir),
                },
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual({"command", "action", "target", "payload"}, set(payload))
            self.assertEqual("infra", payload["command"])
            self.assertEqual("network.audit", payload["action"])
            self.assertEqual("prod0-main", payload["target"])
            self.assertFalse(payload["payload"]["ok"])

    def test_network_audit_fails_when_required_container_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory_dir = root / "inventory" / "servers" / "prod0-main"
            inventory_dir.mkdir(parents=True, exist_ok=True)
            inventory_dir.joinpath("inventory.json").write_text(
                json.dumps(
                    {
                        "ssh": {"aliases": ["prod0-main"], "user": "root"},
                        "managed_bridge_networks": [
                            {
                                "name": "zqf_network",
                                "driver": "bridge",
                                "subnet": "172.19.0.0/16",
                                "gateway_ip": "172.19.0.1/16",
                                "required_for": ["missing-prod"],
                            }
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            def fake_remote_step(repo_root: Path, target: str, command: str) -> dict[str, object]:
                if "docker network inspect zqf_network --format" in command:
                    return {
                        "ok": True,
                        "stdout": json.dumps(
                            {
                                "Name": "zqf_network",
                                "Id": "66f7da1be943bc160d7df638561fe15ccc1ceea6912e9c753dd40d087e23d8b3",
                                "Driver": "bridge",
                                "IPAM": {"Config": [{"Subnet": "172.19.0.0/16", "Gateway": "172.19.0.1"}]},
                                "Containers": {"sub2api": {"Name": CONTAINER_SUB2API}},
                            }
                        ),
                    }
                if "ip -json -4 addr show dev br-66f7da1be943" in command:
                    return {
                        "ok": True,
                        "stdout": '[{"ifname":"br-66f7da1be943","addr_info":[{"local":"172.19.0.1","prefixlen":16}]}]',
                    }
                if "ip -json route show 172.19.0.0/16" in command:
                    return {
                        "ok": True,
                        "stdout": '[{"dst":"172.19.0.0/16","dev":"br-66f7da1be943","prefsrc":"172.19.0.1"}]',
                    }
                return {"ok": False, "stdout": ""}

            with patch("agentplane.domain.infra.networks._remote_step", side_effect=fake_remote_step):
                payload = network_domain.audit_managed_bridge_networks(root, "prod0-main")

            network = payload["networks"][0]
            self.assertFalse(payload["ok"])
            self.assertEqual(["missing-prod"], network["missing_required_containers"])
            self.assertIn("required_containers_missing", network["problems"])

    def test_infra_network_ensure_uses_formal_host_shape_without_compat_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory_dir = root / "inventory" / "servers" / "prod0-main"
            inventory_dir.mkdir(parents=True, exist_ok=True)
            inventory_dir.joinpath("inventory.json").write_text(
                json.dumps(
                    {
                        "ssh": {"aliases": ["prod0-main"], "user": "root"},
                        "managed_bridge_networks": [
                            {
                                "name": "zqf_network",
                                "driver": "bridge",
                                "subnet": "172.19.0.0/16",
                                "gateway_ip": "172.19.0.1/16",
                                "required_for": [CONTAINER_SUB2API],
                            }
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            (root / "secrets" / "ssh").mkdir(parents=True, exist_ok=True)
            (root / "secrets" / "ssh" / "config").write_text("Host prod0-main\n", encoding="utf-8")
            state = {"gateway_present": False, "route_present": False}

            def fake_remote_step(repo_root: Path, target: str, command: str) -> dict[str, object]:
                if "docker network inspect zqf_network --format" in command:
                    return {
                        "ok": True,
                        "stdout": json.dumps(
                            {
                                "Name": "zqf_network",
                                "Id": "66f7da1be943bc160d7df638561fe15ccc1ceea6912e9c753dd40d087e23d8b3",
                                "Driver": "bridge",
                                "IPAM": {"Config": [{"Subnet": "172.19.0.0/16", "Gateway": "172.19.0.1"}]},
                                "Containers": {"sub2api": {"Name": CONTAINER_SUB2API}},
                            }
                        ),
                    }
                if "ip -json -4 addr show dev br-66f7da1be943" in command:
                    stdout = (
                        '[{"ifname":"br-66f7da1be943","addr_info":[{"local":"172.19.0.1","prefixlen":16}]}]'
                        if state["gateway_present"]
                        else '[{"ifname":"br-66f7da1be943","addr_info":[]}]'
                    )
                    return {"ok": True, "stdout": stdout}
                if "ip -json route show 172.19.0.0/16" in command:
                    stdout = (
                        '[{"dst":"172.19.0.0/16","dev":"br-66f7da1be943","prefsrc":"172.19.0.1"}]'
                        if state["route_present"]
                        else "[]"
                    )
                    return {"ok": True, "stdout": stdout}
                if "ip addr add 172.19.0.1/16 dev br-66f7da1be943" in command:
                    state["gateway_present"] = True
                    return {"ok": True, "stdout": ""}
                if "ip route replace 172.19.0.0/16 dev br-66f7da1be943 src 172.19.0.1" in command:
                    state["route_present"] = True
                    return {"ok": True, "stdout": ""}
                return {"ok": False, "stdout": ""}

            from agentplane.cli.infra import handle_infra_command

            args = SimpleNamespace(
                infra_action="network",
                infra_network_action="ensure",
                target="prod0-main",
                repo_root=str(root),
            )
            with patch("agentplane.domain.infra.networks._remote_step", side_effect=fake_remote_step):
                payload = handle_infra_command(args)

            self.assertEqual({"command", "action", "target", "payload"}, set(payload))
            self.assertEqual("infra", payload["command"])
            self.assertEqual("network.ensure", payload["action"])
            self.assertEqual("prod0-main", payload["target"])
            self.assertTrue(payload["payload"]["ok"])

    def test_infra_health_wraps_structured_health_summary(self) -> None:
        from agentplane.cli.infra import handle_infra_command

        fake_dashboard_current = {
            "uptime": 864000,
            "cpuUsedPercent": 23.45,
            "memoryUsedPercent": 50.0,
            "load1": 1.25,
            "load5": 0.98,
            "load15": 0.87,
            "loadUsagePercent": 12.5,
            "memoryTotal": 17179869184,
            "memoryUsed": 8589934592,
            "memoryAvailable": 8589934592,
            "diskData": [
                {"path": "/", "device": "/dev/sda1", "total": 107374182400, "free": 53687091200, "usedPercent": 50.0}
            ],
            "netBytesSent": 1073741824,
            "netBytesRecv": 2147483648,
            "procs": 128,
        }
        fake_dashboard_base = {
            "hostname": "prod0-main",
            "os": "ubuntu",
            "prettyDistro": "Ubuntu 22.04.3 LTS",
            "kernelVersion": "5.15.0-91-generic",
            "cpuLogicalCores": 8,
            "cpuCores": 4,
            "cpuModelName": "Intel Xeon",
            "websiteNumber": 3,
            "databaseNumber": 2,
            "cronjobNumber": 5,
            "appInstalledNumber": 4,
        }
        fake_executor = object()
        fake_gateway = SimpleNamespace(
            onepanel_target_executor=lambda target: fake_executor,
            get_onepanel_dashboard_current=lambda executor: fake_dashboard_current,
            get_onepanel_dashboard_base=lambda executor: fake_dashboard_base,
            get_onepanel_dashboard_top_cpu=lambda executor: [],
            get_onepanel_dashboard_top_mem=lambda executor: [],
            search_onepanel_alerts=lambda executor, alert_type="", status="": {"items": [], "total": 0},
            search_onepanel_alert_logs=lambda executor, status="": {"items": [], "total": 0},
            get_onepanel_monitor_setting=lambda executor: {"monitorStatus": "enable"},
        )

        args = SimpleNamespace(
            infra_action="health",
            target="prod0-main",
            repo_root=".",
        )
        with patch("agentplane.domain.infra.health.default_provider_gateway", return_value=fake_gateway):
            payload = handle_infra_command(args)

        self.assertEqual({"command", "action", "target", "payload"}, set(payload))
        self.assertEqual("infra", payload["command"])
        self.assertEqual("health", payload["action"])
        self.assertEqual("prod0-main", payload["target"])
        self.assertEqual("healthy", payload["payload"]["status"])
        self.assertEqual("prod0-main", payload["payload"]["hostname"])
        self.assertEqual(23.45, payload["payload"]["cpu"]["used_percent"])
        self.assertEqual(50.0, payload["payload"]["memory"]["used_percent"])
        self.assertEqual(8, payload["payload"]["cpu"]["cores"])

    def test_infra_health_reports_warning_on_high_cpu(self) -> None:
        from agentplane.cli.infra import handle_infra_command

        fake_dashboard_current = {
            "uptime": 864000,
            "cpuUsedPercent": 85.0,
            "memoryUsedPercent": 50.0,
            "load1": 1.25,
            "load5": 0.98,
            "load15": 0.87,
            "loadUsagePercent": 12.5,
            "memoryTotal": 17179869184,
            "memoryUsed": 8589934592,
            "memoryAvailable": 8589934592,
            "diskData": [],
            "netBytesSent": 0,
            "netBytesRecv": 0,
            "procs": 128,
        }
        fake_dashboard_base = {
            "hostname": "prod0-main",
            "os": "ubuntu",
            "prettyDistro": "Ubuntu 22.04.3 LTS",
            "kernelVersion": "5.15.0-91-generic",
            "cpuLogicalCores": 8,
            "cpuCores": 4,
            "cpuModelName": "Intel Xeon",
            "websiteNumber": 3,
            "databaseNumber": 2,
            "cronjobNumber": 5,
            "appInstalledNumber": 4,
        }
        fake_executor = object()
        fake_gateway = SimpleNamespace(
            onepanel_target_executor=lambda target: fake_executor,
            get_onepanel_dashboard_current=lambda executor: fake_dashboard_current,
            get_onepanel_dashboard_base=lambda executor: fake_dashboard_base,
            get_onepanel_dashboard_top_cpu=lambda executor: [],
            get_onepanel_dashboard_top_mem=lambda executor: [],
            search_onepanel_alerts=lambda executor, alert_type="", status="": {"items": [], "total": 0},
            search_onepanel_alert_logs=lambda executor, status="": {"items": [], "total": 0},
            get_onepanel_monitor_setting=lambda executor: {"monitorStatus": "enable"},
        )

        args = SimpleNamespace(
            infra_action="health",
            target="prod0-main",
            repo_root=".",
        )
        with patch("agentplane.domain.infra.health.default_provider_gateway", return_value=fake_gateway):
            payload = handle_infra_command(args)

        self.assertEqual("warning", payload["payload"]["status"])
        self.assertEqual("warning", payload["payload"]["cpu"]["severity"])


# ======================================================================
# From: test_local_host_cli.py
# ======================================================================


