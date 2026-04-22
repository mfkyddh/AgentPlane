import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
import re

from tests.support.app_resources import resource_relative, resource_root

from agentplane.cli.audit import audit_filesystem
from agentplane.domain.app.runtime import _render_server_readme

REPO_ROOT = Path(__file__).resolve().parents[1]


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
        "sub2apipay": {
            "owner_app": "sub2apipay",
            "ledger_status": {
                "intent": "live-db-partition-ledger",
                "runtime_credential_model": "dedicated-runtime-credentials",
                "tenant_isolation": "dedicated-db-user-per-app",
                "local_secret_presence": "not-materialized-by-repo",
            },
            "postgres": {"database": "sub2apipay", "user": "sub2apipay_prod0"},
            "secret_files": [
                resource_relative("prod0-main", "sub2apipay", "postgres"),
            ],
        },
        "newapi": {
            "owner_app": "newapi",
            "ledger_status": {
                "intent": "live-db-partition-ledger",
                "runtime_credential_model": "shared-runtime-credentials",
                "tenant_isolation": "logical-db-partition-not-strong-isolation",
                "local_secret_presence": "not-materialized-by-repo",
            },
            "postgres": {"database": "newapi_prod0", "user": "newapi_prod0"},
            "redis": {"db": 2, "key_prefix": "newapi:"},
            "minio": {
                "bucket": "prod0-newapi",
                "access_key": "newapi_prod0",
                "policy_name": "prod0-newapi-rw",
                "policy_scope": "bucket-only",
                "isolation_level": "bucket-scoped-rw",
            },
            "secret_files": [
                resource_relative("prod0-main", "newapi", "postgres"),
                resource_relative("prod0-main", "newapi", "redis"),
                resource_relative("prod0-main", "newapi", "minio"),
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
                "required_for": ["postgres18-prod", "redis7-prod", "minio-prod", "sub2api-prod", "newapi-prod"],
            }
        ],
        "security": {"openresty_public_listen": {"ports": [8443]}},
        "services": {
            "onepanel_openresty": {"network_mode": "host", "listen_ports": [8443]},
            "newapi": {
                "docker_networks": ["zqf_network"],
                "control_plane": "compose",
                "depends_on_containers": ["postgres18-prod", "redis7-prod"],
            },
            "sub2apipay": {
                "runtime_root": "/data/sub2apipay/app/current",
                "config_files": [
                    "/data/sub2apipay/config/sub2apipay-prod.env",
                    "/data/sub2apipay/config/.env.runtime",
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
        for app_id in ("sub2api", "newapi"):
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
        services["sub2apipay"]["app_resource_summary"] = {
            "postgres": {
                **dict(registry["sub2apipay"]["postgres"]),
                "secret_file": resource_relative("prod0-main", "sub2apipay", "postgres"),
            }
        }
    return payload


def assert_live_db_partition_markers(test_case: unittest.TestCase, text: str) -> None:
    test_case.assertRegex(text, re.compile(r"(DB.?级|数据库级).*(逻辑分区|分区)|逻辑分区.*(DB.?级|数据库级)"))
    test_case.assertRegex(
        text,
        re.compile(r"共享.*(?:runtime|运行时).*(凭据|密码|口令)|共享.*(凭据|密码|口令).*(?:runtime|运行时)"),
    )
    test_case.assertRegex(text, re.compile(r"(不|非).*(强|安全).*隔离"))
    test_case.assertNotIn("remediation-target", text)
    test_case.assertNotIn("pending-realization", text)


def assert_prod0_mixed_app_resource_credential_semantics(test_case: unittest.TestCase, text: str) -> None:
    test_case.assertIn(
        "`app_resource_summary` 供 prod0 台账与对账使用；只有 Redis 采用共享 runtime 凭据，PostgreSQL/MinIO 继续记录各自租户凭据标识，其中 MinIO 额外登记 bucket-scoped policy 元数据。",
        text,
    )
    test_case.assertIn(
            "Redis 采用共享 runtime 凭据（shared runtime credential），并通过 DB 级逻辑分区 + key prefix 区分租户，不再把 per-app Redis user 视为活跃运行时依赖。",
        text,
    )
    test_case.assertIn("bucket-scoped", text)
    test_case.assertNotIn(
        "`app_resource_summary` 反映当前 prod0 台账语义：共享 runtime 凭据，供台账与对账使用。",
        text,
    )


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
            write_inventory(root, "prod2-main", payload)

            result = audit_filesystem(root, "prod2-main")
            codes = {item["id"] for item in result["violations"]}

            self.assertIn("prod.bridge_network.declaration", codes)

    def test_detects_key_prod0_policy_violations(self) -> None:
        # token_backend is the legacy inventory alias that the audit maps to sub2api.
        legacy_sub2api_alias = {"data_dir": "/var/lib/sub2api", "config_file": "/etc/sub2api/sub2api-prod.env"}
        payload = {
            "security": {"openresty_public_listen": {"ports": [2053]}},
            "services": {
                "onepanel_openresty": {"network_mode": "bridge", "listen_ports": [2053]},
                "newapi": {"docker_networks": ["bridge"]},
                "sub2apipay": {"runtime_root": "/opt/sub2apipay/current", "config_files": ["/etc/sub2apipay/sub2apipay-prod.env"]},
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
            self.assertIn("prod0.newapi.network", codes)
            self.assertIn("prod0.sub2api.data_dir", codes)
            self.assertIn("prod0.sub2api.config_file", codes)
            self.assertIn("prod0.sub2apipay.runtime_root", codes)
            self.assertIn("prod0.sub2apipay.config_files", codes)
            self.assertIn("prod0.inventory.legacy_marker", codes)

    def test_cli_audit_filesystem_reports_tenant_registry_summary_and_drift_including_minio(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            payload_missing_registry = baseline_payload(include_app_resource_summary=True)
            write_prod0_inventory(root, payload_missing_registry)
            missing_registry = run_cli("host", "audit", "prod0-main", "--repo-root", str(root))
            self.assertEqual(missing_registry.returncode, 0, msg=missing_registry.stderr)
            payload = json.loads(missing_registry.stdout)
            self.assertEqual({"command", "action", "target", "payload"}, set(payload))
            self.assertEqual("host", payload["command"])
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
            missing_summary = run_cli("host", "audit", "prod0-main", "--repo-root", str(root))
            self.assertEqual(missing_summary.returncode, 0, msg=missing_summary.stderr)
            payload = json.loads(missing_summary.stdout)
            self.assertEqual({"command", "action", "target", "payload"}, set(payload))
            self.assertEqual("host", payload["command"])
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
            payload_drift["services"]["newapi"]["app_resource_summary"] = {
                "postgres": dict(tenant_registry["newapi"]["postgres"]),
                "redis": dict(tenant_registry["newapi"]["redis"]),
                "minio": {"bucket": "prod0-newapi-legacy", "access_key": "newapi_legacy"},
            }
            payload_drift["services"]["sub2api"]["app_resource_summary"] = {
                "postgres": dict(tenant_registry["sub2api"]["postgres"]),
                "redis": dict(tenant_registry["sub2api"]["redis"]),
                "minio": {"bucket": "prod0-sub2api-legacy", "access_key": "sub2api_legacy"},
            }
            write_prod0_inventory(root, payload_drift)
            write_app_resource_registry(root, tenant_registry)
            drift = run_cli("host", "audit", "prod0-main", "--repo-root", str(root))
            self.assertEqual(drift.returncode, 0, msg=drift.stderr)
            payload = json.loads(drift.stdout)
            self.assertEqual({"command", "action", "target", "payload"}, set(payload))
            self.assertEqual("host", payload["command"])
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
                "onepanel_openresty": {"network_mode": "host", "listen_ports": [8443]},
                "marketing_site": {
                    "control_plane": "compose",
                    "container_name": "marketing-site-prod",
                    "public_url": "https://example.com",
                    "rollback_entry": {"kind": "compose", "service_name": "marketing_site"},
                },
                "sub2apipay": {
                    "runtime_root": "/data/sub2apipay/app/current",
                    "config_files": [
                        "/data/sub2apipay/config/sub2apipay-prod.env",
                        "/data/sub2apipay/config/.env.runtime",
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
        payload["services"]["newapi"]["app_resource_summary"] = {
            "postgres": dict(tenant_registry["newapi"]["postgres"]),
            "redis": dict(tenant_registry["newapi"]["redis"]),
            "minio": {"bucket": "prod0-newapi-legacy", "access_key": "newapi_legacy"},
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
        payload["services"]["sub2apipay"]["control_plane"] = "compose"
        payload["services"]["sub2apipay"]["depends_on_containers"] = ["postgres18-prod"]
        tenant_registry = baseline_app_resource_registry()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_prod0_inventory(root, payload)
            write_app_resource_registry(root, tenant_registry)

            result = audit_filesystem(root, "prod0-main")
            issues = [
                item
                for item in result["violations"]
                if item["id"] == "prod0.app_resource.drift" and item.get("details", {}).get("app") == "sub2apipay"
            ]
            self.assertEqual([], issues, msg=json.dumps(issues, ensure_ascii=False))

    def test_tenant_audit_detects_duplicate_app_resource_summary_blocks_in_inventory_source(self) -> None:
        tenant_registry = baseline_app_resource_registry()
        raw_inventory = """
{
  "security": {"openresty_public_listen": {"ports": [8443]}},
  "services": {
    "onepanel_openresty": {"network_mode": "host", "listen_ports": [8443]},
    "newapi": {
      "docker_networks": ["zqf_network"],
      "control_plane": "compose",
      "depends_on_containers": ["postgres18-prod", "redis7-prod"],
      "app_resource_summary": {
        "postgres": {"database": "newapi_prod0", "user": "newapi_prod0", "secret_file": "%s"},
        "redis": {"user": "newapi_prod0", "db": 2, "key_prefix": "newapi:", "secret_file": "%s"},
        "minio": {"bucket": "prod0-newapi", "access_key": "newapi_prod0", "secret_file": "%s"}
      },
      "app_resource_summary": {
        "postgres": {"database": "newapi_legacy", "user": "newapi_legacy"},
        "redis": {"user": "newapi_legacy", "db": 0, "key_prefix": "legacy:"},
        "minio": {"bucket": "prod0-newapi-legacy", "access_key": "newapi_legacy"}
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
        "sub2apipay": {
          "runtime_root": "/data/sub2apipay/app/current",
          "config_files": ["/data/sub2apipay/config/sub2apipay-prod.env", "/data/sub2apipay/config/.env.runtime"]
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
            resource_relative("prod0-main", "newapi", "postgres"),
            resource_relative("prod0-main", "newapi", "redis"),
            resource_relative("prod0-main", "newapi", "minio"),
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
            self.assertEqual("newapi", details.get("app"))
            self.assertEqual("services.newapi.app_resource_summary", details.get("json_path"))

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

    def test_prod2_openresty_443_contract_comes_from_inventory_declaration(self) -> None:
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
                "onepanel_openresty": {"network_mode": "host", "listen_ports": [443]},
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root, "prod2-main", payload)

            result = audit_filesystem(root, "prod2-main")
            self.assertEqual([], result["violations"], msg=json.dumps(result, ensure_ascii=False))
            cli_result = run_cli("host", "audit", "prod2-main", "--repo-root", str(root))
            self.assertEqual(0, cli_result.returncode, msg=cli_result.stderr)
            cli_payload = json.loads(cli_result.stdout)
            self.assertEqual({"command", "action", "target", "payload"}, set(cli_payload))
            self.assertEqual("host", cli_payload["command"])
            self.assertEqual("audit", cli_payload["action"])
            self.assertEqual("prod2-main", cli_payload["target"])
            self.assertEqual([], cli_payload["payload"]["violations"], msg=json.dumps(cli_payload, ensure_ascii=False))

    def test_tenant_audit_detects_legacy_flat_secret_references_for_formal_apps(self) -> None:
        payload = baseline_payload(include_app_resource_summary=True)
        payload["services"]["newapi"]["config_files"] = [
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

    def test_tracked_prod0_registry_uses_normalized_app_resource_summary_values(self) -> None:
        registry_file = REPO_ROOT / "inventory" / "servers" / "prod0-main" / "app-resources.json"
        payload = json.loads(registry_file.read_text(encoding="utf-8"))
        self.assertEqual("sub2apipay", payload["sub2apipay"]["owner_app"])
        self.assertEqual("sub2apipay", payload["sub2apipay"]["postgres"]["database"])
        self.assertEqual("sub2apipay_prod0", payload["sub2apipay"]["postgres"]["user"])
        self.assertEqual(1, payload["sub2api"]["redis"]["db"])
        self.assertEqual("sub2api:", payload["sub2api"]["redis"]["key_prefix"])
        self.assertEqual(2, payload["newapi"]["redis"]["db"])
        self.assertEqual("newapi:", payload["newapi"]["redis"]["key_prefix"])
        self.assertEqual("prod0-sub2api-rw", payload["sub2api"]["minio"]["policy_name"])
        self.assertEqual("bucket-only", payload["sub2api"]["minio"]["policy_scope"])
        self.assertEqual("bucket-scoped-rw", payload["sub2api"]["minio"]["isolation_level"])
        self.assertEqual("prod0-newapi-rw", payload["newapi"]["minio"]["policy_name"])
        self.assertEqual("bucket-only", payload["newapi"]["minio"]["policy_scope"])
        self.assertEqual("bucket-scoped-rw", payload["newapi"]["minio"]["isolation_level"])

    def test_tracked_resource_tenant_ledgers_mark_live_db_partition_semantics(self) -> None:
        registry_file = REPO_ROOT / "inventory" / "servers" / "prod0-main" / "app-resources.json"
        payload = json.loads(registry_file.read_text(encoding="utf-8"))
        expected_status = {
            "sub2api": {
                "runtime_credential_model": "shared-runtime-credentials",
                "tenant_isolation": "logical-db-partition-not-strong-isolation",
            },
            "sub2apipay": {
                "runtime_credential_model": "dedicated-runtime-credentials",
                "tenant_isolation": "dedicated-db-user-per-app",
            },
            "newapi": {
                "runtime_credential_model": "shared-runtime-credentials",
                "tenant_isolation": "logical-db-partition-not-strong-isolation",
            },
        }
        for app in ("sub2api", "sub2apipay", "newapi"):
            with self.subTest(app=app):
                status = payload[app].get("ledger_status")
                if isinstance(status, dict):
                    self.assertEqual("live-db-partition-ledger", status.get("intent"))
                    self.assertEqual(expected_status[app]["runtime_credential_model"], status.get("runtime_credential_model"))
                    self.assertEqual(expected_status[app]["tenant_isolation"], status.get("tenant_isolation"))
                    self.assertEqual("not-materialized-by-repo", status.get("local_secret_presence"))
                postgres = payload[app].get("postgres")
                self.assertIsInstance(postgres, dict)
                assert isinstance(postgres, dict)
                self.assertIn("database", postgres)
                self.assertIn("user", postgres)
                if app != "sub2apipay":
                    redis = payload[app].get("redis")
                    self.assertIsInstance(redis, dict)
                    assert isinstance(redis, dict)
                    self.assertIn("db", redis)
                    self.assertIn("key_prefix", redis)
                else:
                    self.assertNotIn("redis", payload[app])
                    self.assertNotIn("minio", payload[app])

        ledger_md = (
            REPO_ROOT / "inventory" / "servers" / "prod0-main" / "ledgers" / "app_resources.md"
        ).read_text(encoding="utf-8")
        assert_live_db_partition_markers(self, ledger_md)

        server_readme = (REPO_ROOT / "inventory" / "servers" / "prod0-main" / "README.md").read_text(
            encoding="utf-8"
        )
        assert_live_db_partition_markers(self, server_readme)

        inventory_text = (REPO_ROOT / "inventory" / "servers" / "prod0-main" / "inventory.json").read_text(
            encoding="utf-8"
        )
        assert_live_db_partition_markers(self, inventory_text)
        inventory_payload = json.loads(inventory_text)
        for app in ("sub2api", "sub2apipay", "newapi"):
            with self.subTest(app=f"{app}-inventory-postgres"):
                postgres = inventory_payload["services"][app]["app_resource_summary"]["postgres"]
                self.assertIsInstance(postgres, dict)
                assert isinstance(postgres, dict)
                self.assertEqual(
                    payload[app]["postgres"]["database"],
                    postgres.get("database"),
                )
                self.assertEqual(
                    payload[app]["postgres"]["user"],
                    postgres.get("user"),
                )
                self.assertEqual(
                    resource_relative("prod0-main", app, "postgres"),
                    postgres.get("secret_file"),
                )

        for app in ("sub2api", "newapi"):
            with self.subTest(app=f"{app}-inventory-redis-user"):
                redis = inventory_payload["services"][app]["app_resource_summary"]["redis"]
                self.assertIsInstance(redis, dict)
                assert isinstance(redis, dict)
                self.assertNotIn("user", redis)

        self.assertEqual(
            {"postgres"},
            set(inventory_payload["services"]["sub2apipay"]["app_resource_summary"].keys()),
        )

    def test_tracked_prod0_readme_and_renderer_lock_mixed_tenant_credential_semantics(self) -> None:
        inventory_payload = json.loads(
            (REPO_ROOT / "inventory" / "servers" / "prod0-main" / "inventory.json").read_text(encoding="utf-8")
        )
        tracked_readme = (REPO_ROOT / "inventory" / "servers" / "prod0-main" / "README.md").read_text(
            encoding="utf-8"
        )

        assert_prod0_mixed_app_resource_credential_semantics(self, tracked_readme)
        rendered_readme = _render_server_readme("prod0-main", inventory_payload)
        assert_prod0_mixed_app_resource_credential_semantics(self, rendered_readme)

    def test_tracked_prod0_inventory_has_single_app_resource_summary_per_formal_app(self) -> None:
        inventory_file = REPO_ROOT / "inventory" / "servers" / "prod0-main" / "inventory.json"
        raw = inventory_file.read_text(encoding="utf-8")

        for app in ("newapi", "sub2apipay", "sub2api"):
            anchor = f"\"{app}\": {{"
            start = raw.find(anchor)
            self.assertNotEqual(-1, start, msg=f"missing app block in inventory source: {app}")
            next_start = raw.find("\n    \"", start + len(anchor))
            app_block = raw[start:] if next_start == -1 else raw[start:next_start]
            self.assertEqual(
                1,
                app_block.count("\"app_resource_summary\""),
                msg=f"app {app} must have exactly one app_resource_summary block in inventory source",
            )

    def test_tracked_prod0_inventory_and_registry_have_no_tenant_drift(self) -> None:
        result = audit_filesystem(REPO_ROOT, "prod0-main")
        tenant_issue_ids = {
            "prod0.app_resource.registry_missing",
            "prod0.app_resource.summary_missing",
            "prod0.app_resource.summary_duplicate",
            "prod0.app_resource.drift",
        }
        issues = [item for item in result["violations"] if item["id"] in tenant_issue_ids]
        self.assertEqual([], issues, msg=json.dumps(issues, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
