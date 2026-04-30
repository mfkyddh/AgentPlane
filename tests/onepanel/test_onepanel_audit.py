from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pytest
from agentplane.cli.audit import audit_filesystem
from tests.support.app_resources import resource_relative

pytestmark = pytest.mark.e2e

REPO_ROOT = Path(__file__).resolve().parents[2]

def run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    repo_path = str(REPO_ROOT)
    env["PYTHONPATH"] = repo_path if not existing else f"{repo_path}:{existing}"
    return subprocess.run(
        [sys.executable, "-m", "agentplane.cli", *args],
        cwd=cwd or REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

def write_inventory(root: Path, env: str, payload: dict) -> None:
    inventory_file = root / "inventory" / "servers" / env / "inventory.json"
    inventory_file.parent.mkdir(parents=True, exist_ok=True)
    inventory_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

def write_prod0_inventory(root: Path, payload: dict) -> None:
    write_inventory(root, "prod0-main", payload)

def write_app_resource_registry(root: Path, payload: dict) -> None:
    registry_file = root / "inventory" / "servers" / "prod0-main" / "app-resources.json"
    registry_file.parent.mkdir(parents=True, exist_ok=True)
    registry_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

def baseline_app_resource_registry() -> dict:
    return {
        "sub2api": {
            "owner_app": "sub2api",
            "ledger_status": {
                "intent": "live-db-partition-ledger",
                "runtime_credential_model": "shared-runtime-credentials",
                "tenant_isolation": "logical-db-partition-not-strong-isolation",
                "local_secret_presence": "not-materialized-by-repo",
            },
            "postgres": {"database": "sub2api_prod0", "user": "sub2api_prod0"},
            "redis": {"db": 1, "key_prefix": "sub2api:"},
            "minio": {
                "bucket": "prod0-sub2api",
                "access_key": "sub2api_prod0",
                "policy_name": "prod0-sub2api-rw",
                "policy_scope": "bucket-only",
                "isolation_level": "bucket-scoped-rw",
            },
            "secret_files": [
                resource_relative("prod0-main", "sub2api", "postgres"),
                resource_relative("prod0-main", "sub2api", "redis"),
                resource_relative("prod0-main", "sub2api", "minio"),
            ],
        },
        "samplepay": {
            "owner_app": "samplepay",
            "ledger_status": {
                "intent": "live-db-partition-ledger",
                "runtime_credential_model": "dedicated-runtime-credentials",
                "tenant_isolation": "dedicated-db-user-per-app",
                "local_secret_presence": "not-materialized-by-repo",
            },
            "postgres": {"database": "samplepay", "user": "samplepay_prod0"},
            "secret_files": [
                resource_relative("prod0-main", "samplepay", "postgres"),
            ],
        },
        "sampleapi": {
            "owner_app": "sampleapi",
            "ledger_status": {
                "intent": "live-db-partition-ledger",
                "runtime_credential_model": "shared-runtime-credentials",
                "tenant_isolation": "logical-db-partition-not-strong-isolation",
                "local_secret_presence": "not-materialized-by-repo",
            },
            "postgres": {"database": "sampleapi_prod0", "user": "sampleapi_prod0"},
            "redis": {"db": 2, "key_prefix": "sampleapi:"},
            "minio": {
                "bucket": "prod0-sampleapi",
                "access_key": "sampleapi_prod0",
                "policy_name": "prod0-sampleapi-rw",
                "policy_scope": "bucket-only",
                "isolation_level": "bucket-scoped-rw",
            },
            "secret_files": [
                resource_relative("prod0-main", "sampleapi", "postgres"),
                resource_relative("prod0-main", "sampleapi", "redis"),
                resource_relative("prod0-main", "sampleapi", "minio"),
            ],
        },
    }

def baseline_payload(*, include_app_resource_summary: bool = False) -> dict:
    payload = {
        "managed_bridge_networks": [
            {
                "name": "zqf_network",
                "driver": "bridge",
                "subnet": "172.19.0.0/16",
                "gateway_ip": "172.19.0.1/16",
                "required_for": ["postgres18-prod", "redis7-prod", "minio-prod", "sub2api-prod", "sampleapi-prod"],
            }
        ],
        "security": {"openresty_public_listen": {"ports": [8443]}},
        "services": {
            "onepanel_openresty": {"network_mode": "infra", "listen_ports": [8443]},
            "sampleapi": {
                "docker_networks": ["zqf_network"],
                "control_plane": "compose",
                "depends_on_containers": ["postgres18-prod", "redis7-prod"],
            },
            "samplepay": {
                "runtime_root": "/data/samplepay/app/current",
                "config_files": [
                    "/data/samplepay/config/samplepay-prod.env",
                    "/data/samplepay/config/.env.runtime",
                ],
            },
            "sub2api": {
                "control_plane": "compose",
                "container_name": "sub2api-prod",
                "data_dir": "/data/sub2api/data",
                "config_files": ["/data/sub2api/config/sub2api-prod.env"],
                "depends_on_containers": ["postgres18-prod", "redis7-prod"],
            },
        },
    }
    if include_app_resource_summary:
        registry = baseline_app_resource_registry()
        services = payload["services"]
        for app_id in ("sub2api", "sampleapi"):
            services[app_id]["app_resource_summary"] = {
                "postgres": {
                    **dict(registry[app_id]["postgres"]),
                    "secret_file": resource_relative("prod0-main", app_id, "postgres"),
                },
                "redis": {
                    **dict(registry[app_id]["redis"]),
                    "secret_file": resource_relative("prod0-main", app_id, "redis"),
                },
                "minio": {
                    **dict(registry[app_id]["minio"]),
                    "secret_file": resource_relative("prod0-main", app_id, "minio"),
                },
            }
        services["samplepay"]["app_resource_summary"] = {
            "postgres": {
                **dict(registry["samplepay"]["postgres"]),
                "secret_file": resource_relative("prod0-main", "samplepay", "postgres"),
            }
        }
    return payload

class Prod0AuditTests(unittest.TestCase):
    def test_detects_invalid_managed_bridge_network_declaration(self) -> None:
        payload = baseline_payload()
        payload["managed_bridge_networks"] = [
            {
                "name": "zqf_network",
                "driver": "bridge",
                "subnet": "172.19.0.0/16",
            }
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root, "prod0-main", payload)

            result = audit_filesystem(root, "prod0-main")
            codes = {item["id"] for item in result["violations"]}

            self.assertIn("prod.bridge_network.declaration", codes)

    def test_detects_key_prod0_policy_violations(self) -> None:
        # token_backend is the legacy inventory alias that the audit maps to sub2api.
        legacy_sub2api_alias = {"data_dir": "/var/lib/sub2api", "config_file": "/etc/sub2api/sub2api-prod.env"}
        payload = {
            "security": {"openresty_public_listen": {"ports": [2053]}},
            "services": {
                "onepanel_openresty": {"network_mode": "bridge", "listen_ports": [2053]},
                "token_backend": legacy_sub2api_alias,
            },
            "notes": ["legacy nginx-ui marker"],
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_prod0_inventory(root, payload)

            result = audit_filesystem(root, "prod0-main")
            codes = {item["id"] for item in result["violations"]}

            self.assertIn("prod0.openresty.listen_ports", codes)
            self.assertIn("prod0.openresty.network_mode", codes)
            self.assertIn("prod0.sub2api.data_dir", codes)
            self.assertIn("prod0.sub2api.config_file", codes)
            self.assertIn("prod0.inventory.legacy_marker", codes)

    def test_cli_audit_filesystem_reports_tenant_registry_summary_and_drift_including_minio(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            payload_missing_registry = baseline_payload(include_app_resource_summary=True)
            write_prod0_inventory(root, payload_missing_registry)
            missing_registry = run_cli("infra", "audit", "prod0-main", "--repo-root", str(root))
            self.assertEqual(missing_registry.returncode, 0, msg=missing_registry.stderr)
            payload = json.loads(missing_registry.stdout)
            self.assertEqual({"command", "action", "target", "payload"}, set(payload))
            self.assertEqual("infra", payload["command"])
            self.assertEqual("audit", payload["action"])
            self.assertEqual("prod0-main", payload["target"])
            self.assertIn("violations", payload["payload"])
            codes = {item["id"] for item in payload["payload"]["violations"]}
            self.assertIn("prod0.app_resource.registry_missing", codes)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            payload_missing_summary = baseline_payload()
            write_prod0_inventory(root, payload_missing_summary)
            write_app_resource_registry(root, baseline_app_resource_registry())
            missing_summary = run_cli("infra", "audit", "prod0-main", "--repo-root", str(root))
            self.assertEqual(missing_summary.returncode, 0, msg=missing_summary.stderr)
            payload = json.loads(missing_summary.stdout)
            self.assertEqual({"command", "action", "target", "payload"}, set(payload))
            self.assertEqual("infra", payload["command"])
            self.assertEqual("audit", payload["action"])
            self.assertEqual("prod0-main", payload["target"])
            self.assertIn("violations", payload["payload"])
            codes = {item["id"] for item in payload["payload"]["violations"]}
            self.assertIn("prod0.app_resource.summary_missing", codes)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            payload_drift = baseline_payload(include_app_resource_summary=True)
            tenant_registry = baseline_app_resource_registry()
            # Lock in MinIO drift detection through the CLI: postgres/redis remain consistent, only minio differs.
            payload_drift["services"]["sampleapi"]["app_resource_summary"] = {
                "postgres": dict(tenant_registry["sampleapi"]["postgres"]),
                "redis": dict(tenant_registry["sampleapi"]["redis"]),
                "minio": {"bucket": "prod0-sampleapi-legacy", "access_key": "sampleapi_legacy"},
            }
            payload_drift["services"]["sub2api"]["app_resource_summary"] = {
                "postgres": dict(tenant_registry["sub2api"]["postgres"]),
                "redis": dict(tenant_registry["sub2api"]["redis"]),
                "minio": {"bucket": "prod0-sub2api-legacy", "access_key": "sub2api_legacy"},
            }
            write_prod0_inventory(root, payload_drift)
            write_app_resource_registry(root, tenant_registry)
            drift = run_cli("infra", "audit", "prod0-main", "--repo-root", str(root))
            self.assertEqual(drift.returncode, 0, msg=drift.stderr)
            payload = json.loads(drift.stdout)
            self.assertEqual({"command", "action", "target", "payload"}, set(payload))
            self.assertEqual("infra", payload["command"])
            self.assertEqual("audit", payload["action"])
            self.assertEqual("prod0-main", payload["target"])
            self.assertIn("violations", payload["payload"])
            codes = {item["id"] for item in payload["payload"]["violations"]}
            self.assertIn("prod0.app_resource.drift", codes)

    def test_accepts_compliant_prod0_snapshot(self) -> None:
        payload = baseline_payload(include_app_resource_summary=True)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_prod0_inventory(root, payload)
            write_app_resource_registry(root, baseline_app_resource_registry())

            result = audit_filesystem(root, "prod0-main")
            self.assertEqual([], result["violations"], msg=json.dumps(result, ensure_ascii=False))

    def test_tenant_audit_requires_resource_tenant_registry(self) -> None:
        payload = baseline_payload(include_app_resource_summary=True)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_prod0_inventory(root, payload)

            result = audit_filesystem(root, "prod0-main")
            codes = {item["id"] for item in result["violations"]}
            self.assertIn("prod0.app_resource.registry_missing", codes)

    def test_tenant_audit_requires_resource_tenant_registry_even_when_formal_apps_lack_summary(self) -> None:
        payload = baseline_payload()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_prod0_inventory(root, payload)

            result = audit_filesystem(root, "prod0-main")
            codes = {item["id"] for item in result["violations"]}
            self.assertIn("prod0.app_resource.registry_missing", codes)

    def test_tenant_audit_does_not_treat_non_tenant_formal_app_as_registry_missing(self) -> None:
        payload = {
            "security": {"openresty_public_listen": {"ports": [8443]}},
            "services": {
                "onepanel_openresty": {"network_mode": "infra", "listen_ports": [8443]},
                "marketing_site": {
                    "control_plane": "compose",
                    "container_name": "marketing-site-prod",
                    "public_url": "https://example.com",
                    "rollback_entry": {"kind": "compose", "service_name": "marketing_site"},
                },
                "samplepay": {
                    "runtime_root": "/data/samplepay/app/current",
                    "config_files": [
                        "/data/samplepay/config/samplepay-prod.env",
                        "/data/samplepay/config/.env.runtime",
                    ],
                },
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_prod0_inventory(root, payload)

            result = audit_filesystem(root, "prod0-main")
            codes = {item["id"] for item in result["violations"]}
            self.assertNotIn("prod0.app_resource.registry_missing", codes)

    def test_tenant_audit_detects_missing_formal_app_tenant_summaries(self) -> None:
        payload = baseline_payload()
        tenant_registry = baseline_app_resource_registry()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_prod0_inventory(root, payload)
            write_app_resource_registry(root, tenant_registry)

            result = audit_filesystem(root, "prod0-main")
            codes = {item["id"] for item in result["violations"]}
            self.assertIn("prod0.app_resource.summary_missing", codes)

    def test_tenant_audit_detects_tenant_drift_between_inventory_and_registry(self) -> None:
        payload = baseline_payload(include_app_resource_summary=True)
        tenant_registry = baseline_app_resource_registry()
        # Lock in MinIO drift detection: postgres/redis remain consistent, only minio differs.
        payload["services"]["sampleapi"]["app_resource_summary"] = {
            "postgres": dict(tenant_registry["sampleapi"]["postgres"]),
            "redis": dict(tenant_registry["sampleapi"]["redis"]),
            "minio": {"bucket": "prod0-sampleapi-legacy", "access_key": "sampleapi_legacy"},
        }
        payload["services"]["sub2api"]["app_resource_summary"] = {
            "postgres": dict(tenant_registry["sub2api"]["postgres"]),
            "redis": dict(tenant_registry["sub2api"]["redis"]),
            "minio": {"bucket": "prod0-sub2api-legacy", "access_key": "sub2api_legacy"},
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_prod0_inventory(root, payload)
            write_app_resource_registry(root, tenant_registry)

            result = audit_filesystem(root, "prod0-main")
            codes = {item["id"] for item in result["violations"]}
            self.assertIn("prod0.app_resource.drift", codes)

    def test_tenant_audit_accepts_postgres_only_app_resource_summary_when_registry_matches(self) -> None:
        payload = baseline_payload(include_app_resource_summary=True)
        payload["services"]["samplepay"]["control_plane"] = "compose"
        payload["services"]["samplepay"]["depends_on_containers"] = ["postgres18-prod"]
        tenant_registry = baseline_app_resource_registry()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_prod0_inventory(root, payload)
            write_app_resource_registry(root, tenant_registry)

            result = audit_filesystem(root, "prod0-main")
            issues = [
                item
                for item in result["violations"]
                if item["id"] == "prod0.app_resource.drift" and item.get("details", {}).get("app") == "samplepay"
            ]
            self.assertEqual([], issues, msg=json.dumps(issues, ensure_ascii=False))

    def test_tenant_audit_detects_duplicate_app_resource_summary_blocks_in_inventory_source(self) -> None:
        tenant_registry = baseline_app_resource_registry()
        raw_inventory = """
{
  "security": {"openresty_public_listen": {"ports": [8443]}},
  "services": {
    "onepanel_openresty": {"network_mode": "infra", "listen_ports": [8443]},
    "sampleapi": {
      "docker_networks": ["zqf_network"],
      "control_plane": "compose",
      "depends_on_containers": ["postgres18-prod", "redis7-prod"],
      "app_resource_summary": {
        "postgres": {"database": "sampleapi_prod0", "user": "sampleapi_prod0", "secret_file": "%s"},
        "redis": {"user": "sampleapi_prod0", "db": 2, "key_prefix": "sampleapi:", "secret_file": "%s"},
        "minio": {"bucket": "prod0-sampleapi", "access_key": "sampleapi_prod0", "secret_file": "%s"}
      },
      "app_resource_summary": {
        "postgres": {"database": "sampleapi_legacy", "user": "sampleapi_legacy"},
        "redis": {"user": "sampleapi_legacy", "db": 0, "key_prefix": "legacy:"},
        "minio": {"bucket": "prod0-sampleapi-legacy", "access_key": "sampleapi_legacy"}
      }
    },
    "sub2api": {
      "control_plane": "compose",
      "depends_on_containers": ["postgres18-prod", "redis7-prod"],
      "app_resource_summary": {
        "postgres": {"database": "sub2api_prod0", "user": "sub2api_prod0", "secret_file": "%s"},
        "redis": {"user": "sub2api_prod0", "db": 1, "key_prefix": "sub2api:", "secret_file": "%s"},
        "minio": {"bucket": "prod0-sub2api", "access_key": "sub2api_prod0", "secret_file": "%s"}
      }
    },
        "samplepay": {
          "runtime_root": "/data/samplepay/app/current",
          "config_files": ["/data/samplepay/config/samplepay-prod.env", "/data/samplepay/config/.env.runtime"]
        },
        "marketing_site": {
          "control_plane": "compose",
          "container_name": "marketing-site-prod",
          "public_url": "https://example.com",
          "app_resource_summary": {"redis": {"db": 9}},
          "app_resource_summary": {"redis": {"db": 8}}
        }
      }
}
""" % (
            resource_relative("prod0-main", "sampleapi", "postgres"),
            resource_relative("prod0-main", "sampleapi", "redis"),
            resource_relative("prod0-main", "sampleapi", "minio"),
            resource_relative("prod0-main", "sub2api", "postgres"),
            resource_relative("prod0-main", "sub2api", "redis"),
            resource_relative("prod0-main", "sub2api", "minio"),
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory_file = root / "inventory" / "servers" / "prod0-main" / "inventory.json"
            inventory_file.parent.mkdir(parents=True, exist_ok=True)
            inventory_file.write_text(raw_inventory.strip() + "\n", encoding="utf-8")
            write_app_resource_registry(root, tenant_registry)

            result = audit_filesystem(root, "prod0-main")
            duplicates = [item for item in result["violations"] if item["id"] == "prod0.app_resource.summary_duplicate"]
            self.assertEqual(1, len(duplicates), msg=json.dumps(result, ensure_ascii=False))
            details = duplicates[0].get("details", {})
            self.assertEqual("sampleapi", details.get("app"))
            self.assertEqual("services.sampleapi.app_resource_summary", details.get("json_path"))

    def test_prod0_openresty_runtime_ports_must_match_declared_public_ports(self) -> None:
        payload = baseline_payload(include_app_resource_summary=True)
        payload["services"]["onepanel_openresty"]["listen_ports"] = [443]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_prod0_inventory(root, payload)
            write_app_resource_registry(root, baseline_app_resource_registry())

            result = audit_filesystem(root, "prod0-main")
            codes = {item["id"] for item in result["violations"]}
            self.assertIn("prod0.openresty.listen_ports", codes)

    def test_prod_openresty_443_contract_comes_from_inventory_declaration(self) -> None:
        payload = {
            "managed_bridge_networks": [
                {
                    "name": "zqf_network",
                    "driver": "bridge",
                    "subnet": "172.19.0.0/16",
                    "gateway_ip": "172.19.0.1/16",
                    "required_for": ["sub2api-prod"],
                }
            ],
            "security": {"openresty_public_listen": {"ports": [443]}},
            "services": {
                "onepanel_openresty": {"network_mode": "infra", "listen_ports": [443]},
                "sub2api": {
                    "container_name": "sub2api-prod",
                    "data_dir": "/data/sub2api/data",
                    "config_files": ["/data/sub2api/config/sub2api-prod.env"],
                },
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root, "prod0-main", payload)
            (root / "data" / "sub2api" / "data").mkdir(parents=True, exist_ok=True)
            (root / "data" / "sub2api" / "config").mkdir(parents=True, exist_ok=True)

            result = audit_filesystem(root, "prod0-main")
            self.assertEqual([], result["violations"], msg=json.dumps(result, ensure_ascii=False))
            cli_result = run_cli("infra", "audit", "prod0-main", "--repo-root", str(root))
            self.assertEqual(0, cli_result.returncode, msg=cli_result.stderr)
            cli_payload = json.loads(cli_result.stdout)
            self.assertEqual({"command", "action", "target", "payload"}, set(cli_payload))
            self.assertEqual("infra", cli_payload["command"])
            self.assertEqual("audit", cli_payload["action"])
            self.assertEqual("prod0-main", cli_payload["target"])
            self.assertEqual([], cli_payload["payload"]["violations"], msg=json.dumps(cli_payload, ensure_ascii=False))

    def test_tenant_audit_detects_legacy_flat_secret_references_for_formal_apps(self) -> None:
        payload = baseline_payload(include_app_resource_summary=True)
        payload["services"]["sampleapi"]["config_files"] = [
            "/opt/agentplane/secrets/services/postgres.env",
            "/opt/agentplane/secrets/services/redis.conf",
            "/opt/agentplane/secrets/services/minio.env",
        ]
        payload["services"]["sub2api"]["config_files"] = [
            "secrets/services/postgres.env",
            "secrets/services/redis.conf",
            "secrets/services/minio.env",
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_prod0_inventory(root, payload)
            write_app_resource_registry(root, baseline_app_resource_registry())

            result = audit_filesystem(root, "prod0-main")
            codes = {item["id"] for item in result["violations"]}
            self.assertIn("prod0.app_resource.legacy_flat_secret_reference", codes)
