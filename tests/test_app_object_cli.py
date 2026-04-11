import json
import os
import importlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
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


def write_inventory_with_app(root: Path) -> None:
    server_root = root / "inventory" / "servers" / "prod0-main"
    server_root.mkdir(parents=True, exist_ok=True)
    app_payload = {
        "app": "sub2api",
        "control_plane": "compose",
        "container_name": "sub2api-prod",
        "host_binding": "127.0.0.1:18080",
        "public_url": "https://token.zzzai.cloud:8443",
        "app_resource_summary": {
            "postgres": {
                "database": "sub2api_prod0",
                "user": "sub2api_prod0",
                "secret_file": "secrets/hosts/prod0-main/apps/sub2api/resources/postgres.env",
            },
            "redis": {
                "db": 1,
                "key_prefix": "sub2api:",
                "secret_file": "secrets/hosts/prod0-main/apps/sub2api/resources/redis.env",
            },
        },
    }
    (server_root / "inventory.json").write_text(
        json.dumps(
            {
                "services": {"sub2api": app_payload},
                "object_ledgers": {"counts": {"apps": 1}},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    ledger_root = server_root / "ledgers"
    ledger_root.mkdir(parents=True, exist_ok=True)
    (ledger_root / "apps.json").write_text(
        json.dumps({"items": [app_payload], "count": 1}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    catalog_root = root / "inventory" / "apps"
    catalog_root.mkdir(parents=True, exist_ok=True)
    (catalog_root / "catalog.json").write_text(
        json.dumps(
            {
                "apps": [
                    {
                        "app": "sub2api",
                        "repo_name": "sub2api",
                        "repo_root": str(root / "sub2api"),
                        "service_key": "sub2api",
                        "contracts": {"prod0-main": "deploy/agentplane/contract.yaml"},
                    }
                ]
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


class AppObjectCliTests(unittest.TestCase):
    def test_app_catalog_module_exists_for_object_and_delivery_resolution(self) -> None:
        catalog = importlib.import_module("agentplane.domain.app.catalog")

        self.assertTrue(callable(getattr(catalog, "resolve_app_contract", None)))

    def test_app_catalog_normalizes_wsl_repo_root_for_windows_host(self) -> None:
        catalog = importlib.import_module("agentplane.domain.app.catalog")

        with patch.object(catalog.os, "name", "nt"):
            normalized = catalog._normalize_repo_root_for_current_host("/root/work/sub2api")

        self.assertEqual(r"\\wsl.localhost\Ubuntu\root\work\sub2api", normalized)

    def test_app_object_search_returns_empty_items_when_catalog_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            server_root = root / "inventory" / "servers" / "prod0-main"
            server_root.mkdir(parents=True, exist_ok=True)
            (server_root / "inventory.json").write_text(
                json.dumps({"services": {}}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            payload = run_cli("app", "object", "search", "--target", "prod0-main", "--repo-root", str(root))

            self.assertEqual(0, payload.returncode, msg=payload.stderr)
            payload_json = json.loads(payload.stdout)
            self.assertEqual([], payload_json["payload"]["items"])

    def test_app_object_search_emits_namespaced_action(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory_with_app(root)

            payload = run_cli("app", "object", "search", "--target", "prod0-main", "--repo-root", str(root))

            self.assertEqual(0, payload.returncode, msg=payload.stderr)
            payload_json = json.loads(payload.stdout)
            self.assertEqual("app", payload_json["command"])
            self.assertEqual("object.search", payload_json["action"])
            self.assertEqual("prod0-main", payload_json["target"])
            self.assertIn("items", payload_json["payload"])
            self.assertEqual("sub2api", payload_json["payload"]["items"][0]["app"])

    def test_app_object_get_returns_named_app_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory_with_app(root)

            payload = run_cli(
                "app",
                "object",
                "get",
                "--target",
                "prod0-main",
                "--app",
                "sub2api",
                "--repo-root",
                str(root),
            )

            self.assertEqual(0, payload.returncode, msg=payload.stderr)
            payload_json = json.loads(payload.stdout)
            self.assertEqual("app", payload_json["command"])
            self.assertEqual("object.get", payload_json["action"])
            self.assertIn("app", payload_json["payload"])
            self.assertEqual("sub2api", payload_json["payload"]["app"]["app"])
            self.assertEqual("compose", payload_json["payload"]["app"]["control_plane"])

    def test_app_object_get_returns_summary_files_and_ledger_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory_with_app(root)
            app_root = root / "sub2api"
            (app_root / "deploy" / "agentplane").mkdir(parents=True, exist_ok=True)
            (app_root / "deploy" / "agentplane" / "contract.yaml").write_text(
                json.dumps(
                    {
                        "docs": {"app_summary_files": {"prod0-main": "docs/AGENTPLANE_DEPLOYMENT.prod0-main.md"}}
                    }
                ),
                encoding="utf-8",
            )
            summary_file = app_root / "docs" / "AGENTPLANE_DEPLOYMENT.prod0-main.md"
            summary_file.parent.mkdir(parents=True, exist_ok=True)
            summary_file.write_text("# summary\n", encoding="utf-8")

            payload = run_cli(
                "app",
                "object",
                "get",
                "--target",
                "prod0-main",
                "--app",
                "sub2api",
                "--repo-root",
                str(root),
            )

            self.assertEqual(0, payload.returncode, msg=payload.stderr)
            payload_json = json.loads(payload.stdout)
            self.assertEqual(
                [
                    {
                        "target": "prod0-main",
                        "path": str(summary_file),
                        "source": "docs.app_summary_files",
                        "exists": True,
                    }
                ],
                payload_json["payload"]["summary_files"],
            )
            self.assertEqual(
                {
                    "json_file": str(root / "inventory" / "servers" / "prod0-main" / "ledgers" / "apps.json"),
                    "markdown_file": str(root / "inventory" / "servers" / "prod0-main" / "ledgers" / "apps.md"),
                    "inventory_pointer": "",
                    "expected_pointer": "inventory/servers/prod0-main/ledgers/apps.json",
                    "json_exists": True,
                    "markdown_exists": False,
                    "inventory_pointer_ok": False,
                },
                payload_json["payload"]["ledger_status"],
            )

    def test_app_object_get_accepts_nested_inventory_ledger_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory_with_app(root)
            inventory_file = root / "inventory" / "servers" / "prod0-main" / "inventory.json"
            inventory_payload = json.loads(inventory_file.read_text(encoding="utf-8"))
            inventory_payload["object_ledgers"] = {
                "ledgers": {"apps": "inventory/servers/prod0-main/ledgers/apps.json"}
            }
            inventory_file.write_text(
                json.dumps(inventory_payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            payload = run_cli(
                "app",
                "object",
                "get",
                "--target",
                "prod0-main",
                "--app",
                "sub2api",
                "--repo-root",
                str(root),
            )

            self.assertEqual(0, payload.returncode, msg=payload.stderr)
            payload_json = json.loads(payload.stdout)
            self.assertTrue(payload_json["payload"]["ledger_status"]["inventory_pointer_ok"])
            self.assertEqual(
                "inventory/servers/prod0-main/ledgers/apps.json",
                payload_json["payload"]["ledger_status"]["inventory_pointer"],
            )
            self.assertEqual(
                "inventory/servers/prod0-main/ledgers/apps.json",
                payload_json["payload"]["ledger_status"]["expected_pointer"],
            )

    def test_app_object_get_falls_back_to_single_summary_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory_with_app(root)
            app_root = root / "sub2api"
            (app_root / "deploy" / "agentplane").mkdir(parents=True, exist_ok=True)
            (app_root / "deploy" / "agentplane" / "contract.yaml").write_text(
                json.dumps({"docs": {"app_summary_file": "docs/AGENTPLANE_DEPLOYMENT.md"}}),
                encoding="utf-8",
            )
            summary_file = app_root / "docs" / "AGENTPLANE_DEPLOYMENT.md"
            summary_file.parent.mkdir(parents=True, exist_ok=True)
            summary_file.write_text("# summary fallback\n", encoding="utf-8")

            payload = run_cli(
                "app",
                "object",
                "get",
                "--target",
                "prod0-main",
                "--app",
                "sub2api",
                "--repo-root",
                str(root),
            )

            self.assertEqual(0, payload.returncode, msg=payload.stderr)
            payload_json = json.loads(payload.stdout)
            self.assertEqual(
                [
                    {
                        "target": "prod0-main",
                        "path": str(summary_file),
                        "source": "docs.app_summary_file",
                        "exists": True,
                    }
                ],
                payload_json["payload"]["summary_files"],
            )

    def test_app_object_get_prefers_target_specific_summary_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory_with_app(root)
            app_root = root / "sub2api"
            (app_root / "deploy" / "agentplane").mkdir(parents=True, exist_ok=True)
            (app_root / "deploy" / "agentplane" / "contract.yaml").write_text(
                json.dumps(
                    {
                        "docs": {
                            "app_summary_files": {"prod0-main": "docs/AGENTPLANE_DEPLOYMENT.prod0-main.md"},
                            "app_summary_file": "docs/AGENTPLANE_DEPLOYMENT.md",
                        }
                    }
                ),
                encoding="utf-8",
            )
            summary_file = app_root / "docs" / "AGENTPLANE_DEPLOYMENT.prod0-main.md"
            summary_file.parent.mkdir(parents=True, exist_ok=True)
            summary_file.write_text("# target specific summary\n", encoding="utf-8")
            fallback_file = app_root / "docs" / "AGENTPLANE_DEPLOYMENT.md"
            fallback_file.write_text("# fallback summary\n", encoding="utf-8")

            payload = run_cli(
                "app",
                "object",
                "get",
                "--target",
                "prod0-main",
                "--app",
                "sub2api",
                "--repo-root",
                str(root),
            )

            self.assertEqual(0, payload.returncode, msg=payload.stderr)
            payload_json = json.loads(payload.stdout)
            self.assertEqual(
                [
                    {
                        "target": "prod0-main",
                        "path": str(summary_file),
                        "source": "docs.app_summary_files",
                        "exists": True,
                    }
                ],
                payload_json["payload"]["summary_files"],
            )

    def test_app_object_get_tolerates_malformed_contract_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory_with_app(root)
            app_root = root / "sub2api"
            (app_root / "deploy" / "agentplane").mkdir(parents=True, exist_ok=True)
            (app_root / "deploy" / "agentplane" / "contract.yaml").write_text(
                "docs: [broken",
                encoding="utf-8",
            )

            payload = run_cli(
                "app",
                "object",
                "get",
                "--target",
                "prod0-main",
                "--app",
                "sub2api",
                "--repo-root",
                str(root),
            )

            self.assertEqual(0, payload.returncode, msg=payload.stderr)
            payload_json = json.loads(payload.stdout)
            self.assertEqual("sub2api", payload_json["payload"]["app"]["app"])
            self.assertEqual([], payload_json["payload"]["summary_files"])
            self.assertIn("ledger_status", payload_json["payload"])

    def test_app_object_get_ignores_summary_file_outside_repo_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory_with_app(root)
            app_root = root / "sub2api"
            outside_file = root / "outside-summary.md"
            outside_file.write_text("# outside\n", encoding="utf-8")
            (app_root / "deploy" / "agentplane").mkdir(parents=True, exist_ok=True)
            (app_root / "deploy" / "agentplane" / "contract.yaml").write_text(
                json.dumps(
                    {
                        "docs": {
                            "app_summary_files": {"prod0-main": "../outside-summary.md"},
                        }
                    }
                ),
                encoding="utf-8",
            )

            payload = run_cli(
                "app",
                "object",
                "get",
                "--target",
                "prod0-main",
                "--app",
                "sub2api",
                "--repo-root",
                str(root),
            )

            self.assertEqual(0, payload.returncode, msg=payload.stderr)
            payload_json = json.loads(payload.stdout)
            self.assertEqual([], payload_json["payload"]["summary_files"])

    def test_app_object_get_falls_back_when_target_specific_summary_path_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory_with_app(root)
            app_root = root / "sub2api"
            (app_root / "deploy" / "agentplane").mkdir(parents=True, exist_ok=True)
            (app_root / "deploy" / "agentplane" / "contract.yaml").write_text(
                json.dumps(
                    {
                        "docs": {
                            "app_summary_files": {"prod0-main": "../outside-summary.md"},
                            "app_summary_file": "docs/AGENTPLANE_DEPLOYMENT.md",
                        }
                    }
                ),
                encoding="utf-8",
            )
            fallback_file = app_root / "docs" / "AGENTPLANE_DEPLOYMENT.md"
            fallback_file.parent.mkdir(parents=True, exist_ok=True)
            fallback_file.write_text("# fallback summary\n", encoding="utf-8")

            payload = run_cli(
                "app",
                "object",
                "get",
                "--target",
                "prod0-main",
                "--app",
                "sub2api",
                "--repo-root",
                str(root),
            )

            self.assertEqual(0, payload.returncode, msg=payload.stderr)
            payload_json = json.loads(payload.stdout)
            self.assertEqual(
                [
                    {
                        "target": "prod0-main",
                        "path": str(fallback_file),
                        "source": "docs.app_summary_file",
                        "exists": True,
                    }
                ],
                payload_json["payload"]["summary_files"],
            )

    def test_app_object_get_tolerates_invalid_utf8_contract_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory_with_app(root)
            app_root = root / "sub2api"
            (app_root / "deploy" / "agentplane").mkdir(parents=True, exist_ok=True)
            (app_root / "deploy" / "agentplane" / "contract.yaml").write_bytes(b"\xff\xfe\xfa")

            payload = run_cli(
                "app",
                "object",
                "get",
                "--target",
                "prod0-main",
                "--app",
                "sub2api",
                "--repo-root",
                str(root),
            )

            self.assertEqual(0, payload.returncode, msg=payload.stderr)
            payload_json = json.loads(payload.stdout)
            self.assertEqual([], payload_json["payload"]["summary_files"])

    def test_app_object_verify_fails_when_summary_file_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory_with_app(root)
            app_root = root / "sub2api"
            (app_root / "deploy" / "agentplane").mkdir(parents=True, exist_ok=True)
            (app_root / "deploy" / "agentplane" / "contract.yaml").write_text(
                json.dumps(
                    {
                        "docs": {"app_summary_files": {"prod0-main": "docs/AGENTPLANE_DEPLOYMENT.prod0-main.md"}}
                    }
                ),
                encoding="utf-8",
            )
            inventory_file = root / "inventory" / "servers" / "prod0-main" / "inventory.json"
            inventory_payload = json.loads(inventory_file.read_text(encoding="utf-8"))
            inventory_payload["object_ledgers"] = {
                "ledgers": {"apps": "inventory/servers/prod0-main/ledgers/apps.json"}
            }
            inventory_file.write_text(
                json.dumps(inventory_payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            ledger_root = root / "inventory" / "servers" / "prod0-main" / "ledgers"
            (ledger_root / "apps.md").write_text("# apps\n", encoding="utf-8")

            payload = run_cli(
                "app",
                "object",
                "verify",
                "--target",
                "prod0-main",
                "--app",
                "sub2api",
                "--repo-root",
                str(root),
            )

            self.assertEqual(1, payload.returncode, msg=payload.stderr)
            payload_json = json.loads(payload.stdout)
            self.assertIn("summary_files", payload_json["payload"]["failures"])
            self.assertFalse(payload_json["payload"]["checks"]["summary_files"]["ok"])
            self.assertTrue(payload_json["payload"]["checks"]["ledger_status"]["ok"])

    def test_app_object_verify_fails_when_inventory_pointer_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory_with_app(root)
            app_root = root / "sub2api"
            (app_root / "deploy" / "agentplane").mkdir(parents=True, exist_ok=True)
            (app_root / "deploy" / "agentplane" / "contract.yaml").write_text(
                json.dumps(
                    {
                        "docs": {"app_summary_files": {"prod0-main": "docs/AGENTPLANE_DEPLOYMENT.prod0-main.md"}}
                    }
                ),
                encoding="utf-8",
            )
            summary_file = app_root / "docs" / "AGENTPLANE_DEPLOYMENT.prod0-main.md"
            summary_file.parent.mkdir(parents=True, exist_ok=True)
            summary_file.write_text("# summary\n", encoding="utf-8")
            ledger_root = root / "inventory" / "servers" / "prod0-main" / "ledgers"
            (ledger_root / "apps.md").write_text("# apps\n", encoding="utf-8")

            payload = run_cli(
                "app",
                "object",
                "verify",
                "--target",
                "prod0-main",
                "--app",
                "sub2api",
                "--repo-root",
                str(root),
            )

            self.assertEqual(1, payload.returncode, msg=payload.stderr)
            payload_json = json.loads(payload.stdout)
            self.assertIn("ledger_status", payload_json["payload"]["failures"])
            self.assertFalse(payload_json["payload"]["checks"]["ledger_status"]["ok"])
            self.assertTrue(payload_json["payload"]["checks"]["summary_files"]["ok"])

    def test_app_object_verify_reports_false_when_projection_cannot_be_trusted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory_with_app(root)

            payload = run_cli(
                "app",
                "object",
                "verify",
                "--target",
                "prod0-main",
                "--app",
                "sub2api",
                "--repo-root",
                str(root),
            )

            self.assertEqual(1, payload.returncode, msg=payload.stderr)
            payload_json = json.loads(payload.stdout)
            self.assertEqual("app", payload_json["command"])
            self.assertEqual("object.verify", payload_json["action"])
            self.assertIn("ok", payload_json["payload"])
            self.assertIn("checks", payload_json["payload"])
            self.assertIn("failures", payload_json["payload"])
            self.assertFalse(payload_json["payload"]["ok"])

    def test_app_object_search_prefers_explicit_app_repo_root_over_catalog_repo_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            repo_root = tmp_root / "oplinux"
            canonical_root = tmp_root / "sub2api"
            worktree_root = tmp_root / "sub2api.worktree"
            repo_root.mkdir(parents=True, exist_ok=True)
            canonical_root.mkdir(parents=True, exist_ok=True)
            worktree_root.mkdir(parents=True, exist_ok=True)

            server_root = repo_root / "inventory" / "servers" / "prod0-main"
            server_root.mkdir(parents=True, exist_ok=True)
            (server_root / "inventory.json").write_text(
                json.dumps(
                    {
                        "services": {
                            "sub2api": {
                                "app": "sub2api",
                                "control_plane": "compose",
                                "public_url": "https://token.zzzai.cloud:8443",
                            }
                        }
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            catalog_root = repo_root / "inventory" / "apps"
            catalog_root.mkdir(parents=True, exist_ok=True)
            (catalog_root / "catalog.json").write_text(
                json.dumps(
                    {
                        "apps": [
                            {
                                "app": "sub2api",
                                "repo_name": "sub2api",
                                "repo_root": str(canonical_root),
                                "service_key": "sub2api",
                                "contracts": {"prod0-main": "deploy/agentplane/contract.yaml"},
                            }
                        ]
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            for app_root in (canonical_root, worktree_root):
                (app_root / "deploy" / "agentplane").mkdir(parents=True, exist_ok=True)
                (app_root / "deploy" / "agentplane" / "contract.yaml").write_text("{}", encoding="utf-8")

            payload = run_cli(
                "app",
                "object",
                "search",
                "--target",
                "prod0-main",
                "--app",
                "sub2api",
                "--repo-root",
                str(repo_root),
                "--app-repo-root",
                str(worktree_root),
            )

            self.assertEqual(0, payload.returncode, msg=payload.stderr)
            payload_json = json.loads(payload.stdout)
            self.assertEqual(
                [
                    {
                        "app": "sub2api",
                        "service_key": "sub2api",
                        "contract_file": str((worktree_root / "deploy" / "agentplane" / "contract.yaml").resolve()),
                        "control_plane": "compose",
                        "public_url": "https://token.zzzai.cloud:8443",
                    }
                ],
                payload_json["payload"]["items"],
            )

    def test_app_object_get_prefers_explicit_app_repo_root_over_catalog_repo_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            repo_root = tmp_root / "oplinux"
            canonical_root = tmp_root / "sub2api"
            worktree_root = tmp_root / "sub2api.worktree"
            repo_root.mkdir(parents=True, exist_ok=True)
            canonical_root.mkdir(parents=True, exist_ok=True)
            worktree_root.mkdir(parents=True, exist_ok=True)

            server_root = repo_root / "inventory" / "servers" / "prod0-main"
            server_root.mkdir(parents=True, exist_ok=True)
            (server_root / "inventory.json").write_text(
                json.dumps(
                    {
                        "services": {
                            "sub2api": {
                                "app": "sub2api",
                                "control_plane": "compose",
                                "public_url": "https://token.zzzai.cloud:8443",
                            }
                        }
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            catalog_root = repo_root / "inventory" / "apps"
            catalog_root.mkdir(parents=True, exist_ok=True)
            (catalog_root / "catalog.json").write_text(
                json.dumps(
                    {
                        "apps": [
                            {
                                "app": "sub2api",
                                "repo_name": "sub2api",
                                "repo_root": str(canonical_root),
                                "service_key": "sub2api",
                                "contracts": {"prod0-main": "deploy/agentplane/contract.yaml"},
                            }
                        ]
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            for app_root, marker in ((canonical_root, "canonical"), (worktree_root, "worktree")):
                (app_root / "deploy" / "agentplane").mkdir(parents=True, exist_ok=True)
                (app_root / "deploy" / "agentplane" / "contract.yaml").write_text(
                    json.dumps({"docs": {"app_summary_file": f"docs/{marker.upper()}.md"}}),
                    encoding="utf-8",
                )
                summary_file = app_root / "docs" / f"{marker.upper()}.md"
                summary_file.parent.mkdir(parents=True, exist_ok=True)
                summary_file.write_text(f"# {marker}\n", encoding="utf-8")

            payload = run_cli(
                "app",
                "object",
                "get",
                "--target",
                "prod0-main",
                "--app",
                "sub2api",
                "--repo-root",
                str(repo_root),
                "--app-repo-root",
                str(worktree_root),
            )

            self.assertEqual(0, payload.returncode, msg=payload.stderr)
            payload_json = json.loads(payload.stdout)
            self.assertEqual(
                str((worktree_root / "deploy" / "agentplane" / "contract.yaml").resolve()),
                payload_json["payload"]["app"]["contract_file"],
            )
            self.assertEqual(
                [
                    {
                        "target": "prod0-main",
                        "path": str((worktree_root / "docs" / "WORKTREE.md").resolve()),
                        "source": "docs.app_summary_file",
                        "exists": True,
                    }
                ],
                payload_json["payload"]["summary_files"],
            )

    def test_app_object_verify_prefers_explicit_app_repo_root_over_catalog_repo_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            repo_root = tmp_root / "oplinux"
            canonical_root = tmp_root / "sub2api"
            worktree_root = tmp_root / "sub2api.worktree"
            repo_root.mkdir(parents=True, exist_ok=True)
            canonical_root.mkdir(parents=True, exist_ok=True)
            worktree_root.mkdir(parents=True, exist_ok=True)

            server_root = repo_root / "inventory" / "servers" / "prod0-main"
            server_root.mkdir(parents=True, exist_ok=True)
            (server_root / "inventory.json").write_text(
                json.dumps(
                    {
                        "services": {
                            "sub2api": {
                                "app": "sub2api",
                                "control_plane": "compose",
                                "public_url": "https://token.zzzai.cloud:8443",
                            }
                        },
                        "object_ledgers": {
                            "ledgers": {"apps": "inventory/servers/prod0-main/ledgers/apps.json"}
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            ledger_root = server_root / "ledgers"
            ledger_root.mkdir(parents=True, exist_ok=True)
            (ledger_root / "apps.json").write_text(json.dumps({"count": 1}, ensure_ascii=False, indent=2), encoding="utf-8")
            (ledger_root / "apps.md").write_text("# apps\n", encoding="utf-8")
            catalog_root = repo_root / "inventory" / "apps"
            catalog_root.mkdir(parents=True, exist_ok=True)
            (catalog_root / "catalog.json").write_text(
                json.dumps(
                    {
                        "apps": [
                            {
                                "app": "sub2api",
                                "repo_name": "sub2api",
                                "repo_root": str(canonical_root),
                                "service_key": "sub2api",
                                "contracts": {"prod0-main": "deploy/agentplane/contract.yaml"},
                            }
                        ]
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            (canonical_root / "deploy" / "agentplane").mkdir(parents=True, exist_ok=True)
            (canonical_root / "deploy" / "agentplane" / "contract.yaml").write_text(
                json.dumps({"docs": {"app_summary_file": "docs/CANONICAL.md"}}),
                encoding="utf-8",
            )

            (worktree_root / "deploy" / "agentplane").mkdir(parents=True, exist_ok=True)
            (worktree_root / "deploy" / "agentplane" / "contract.yaml").write_text(
                json.dumps({"docs": {"app_summary_file": "docs/WORKTREE.md"}}),
                encoding="utf-8",
            )
            summary_file = worktree_root / "docs" / "WORKTREE.md"
            summary_file.parent.mkdir(parents=True, exist_ok=True)
            summary_file.write_text("# worktree\n", encoding="utf-8")

            payload = run_cli(
                "app",
                "object",
                "verify",
                "--target",
                "prod0-main",
                "--app",
                "sub2api",
                "--repo-root",
                str(repo_root),
                "--app-repo-root",
                str(worktree_root),
            )

            self.assertEqual(0, payload.returncode, msg=payload.stderr)
            payload_json = json.loads(payload.stdout)
            self.assertTrue(payload_json["payload"]["ok"])
            self.assertEqual(
                [
                    {
                        "target": "prod0-main",
                        "path": str(summary_file.resolve()),
                        "source": "docs.app_summary_file",
                        "exists": True,
                    }
                ],
                payload_json["payload"]["checks"]["summary_files"]["items"],
            )

    def test_app_object_refresh_ledger_writes_inventory_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory_with_app(root)
            app_root = root / "sub2api"
            (app_root / "deploy" / "agentplane").mkdir(parents=True, exist_ok=True)
            (app_root / "deploy" / "agentplane" / "contract.yaml").write_text("{}", encoding="utf-8")

            payload = run_cli(
                "app",
                "object",
                "refresh-ledger",
                "--target",
                "prod0-main",
                "--repo-root",
                str(root),
                "--write",
            )

            self.assertEqual(0, payload.returncode, msg=payload.stderr)
            payload_json = json.loads(payload.stdout)
            self.assertEqual(
                "inventory/servers/prod0-main/ledgers/apps.json",
                payload_json["payload"]["inventory_pointer"],
            )
            inventory = json.loads((root / "inventory" / "servers" / "prod0-main" / "inventory.json").read_text(encoding="utf-8"))
            self.assertEqual(
                "inventory/servers/prod0-main/ledgers/apps.json",
                inventory["object_ledgers"]["ledgers"]["apps"],
            )

    def test_real_tracked_catalog_freezes_sub2api_only(self) -> None:
        catalog_file = REPO_ROOT / "inventory" / "apps" / "catalog.json"

        payload = json.loads(catalog_file.read_text(encoding="utf-8"))

        self.assertEqual(
            {
                "apps": [
                    {
                        "app": "sub2api",
                        "repo_name": "sub2api",
                        "repo_root": "/root/work/sub2api",
                        "service_key": "sub2api",
                        "contracts": {
                            "wsl": "deploy/agentplane/contract.wsl.yaml",
                            "prod0-main": "deploy/agentplane/contract.yaml",
                            "prod2-main": "deploy/agentplane/contract.prod2.yaml",
                        },
                    },
                ]
            },
            payload,
        )

    def test_real_catalog_resolves_sub2api_for_prod0_main(self) -> None:
        payload = run_cli(
            "app",
            "object",
            "search",
            "--target",
            "prod0-main",
            "--repo-root",
            str(REPO_ROOT),
        )

        self.assertEqual(0, payload.returncode, msg=payload.stderr)
        payload_json = json.loads(payload.stdout)
        self.assertEqual(["sub2api"], [item["app"] for item in payload_json["payload"]["items"]])
        self.assertEqual(
            "/root/work/sub2api/deploy/agentplane/contract.yaml",
            payload_json["payload"]["items"][0]["contract_file"],
        )

    def test_real_catalog_resolves_sub2api_for_prod2_main_and_wsl(self) -> None:
        prod2_payload = run_cli(
            "app",
            "object",
            "get",
            "--target",
            "prod2-main",
            "--app",
            "sub2api",
            "--repo-root",
            str(REPO_ROOT),
        )

        self.assertEqual(0, prod2_payload.returncode, msg=prod2_payload.stderr)
        prod2_json = json.loads(prod2_payload.stdout)
        self.assertEqual(
            "/root/work/sub2api/deploy/agentplane/contract.prod2.yaml",
            prod2_json["payload"]["app"]["contract_file"],
        )

        wsl_payload = run_cli(
            "app",
            "object",
            "search",
            "--target",
            "wsl",
            "--repo-root",
            str(REPO_ROOT),
        )

        self.assertEqual(0, wsl_payload.returncode, msg=wsl_payload.stderr)
        wsl_json = json.loads(wsl_payload.stdout)
        self.assertEqual(["sub2api"], [item["app"] for item in wsl_json["payload"]["items"]])
        self.assertEqual(
            "/root/work/sub2api/deploy/agentplane/contract.wsl.yaml",
            wsl_json["payload"]["items"][0]["contract_file"],
        )

    def test_real_formal_catalog_sub2api_keeps_none_previous_control_plane(self) -> None:
        for target in ("wsl", "prod0-main", "prod2-main"):
            with self.subTest(target=target):
                payload = run_cli(
                    "app",
                    "delivery",
                    "validate-contract",
                    "--target",
                    target,
                    "--app",
                    "sub2api",
                    "--repo-root",
                    str(REPO_ROOT),
                )

                self.assertEqual(0, payload.returncode, msg=payload.stderr)
                payload_json = json.loads(payload.stdout)
                self.assertEqual(2, payload_json["payload"]["schema_version"])
                self.assertTrue(payload_json["payload"]["_meta"]["artifact_first"])
                self.assertEqual("dist/oplinux", payload_json["payload"]["artifact"]["output_path"])
                self.assertEqual("linux", payload_json["payload"]["artifact"]["runtime_os"])
                self.assertEqual("amd64", payload_json["payload"]["artifact"]["runtime_arch"])
                self.assertEqual("wsl-linux", payload_json["payload"]["packaging"]["backend"])
                self.assertEqual(
                    "bash deploy/package-runtime-image.sh",
                    payload_json["payload"]["packaging"]["package_command"],
                )
                self.assertEqual("none", payload_json["payload"]["rollback"]["previous_control_plane"]["kind"])

    def test_real_catalog_has_no_newapi_or_sub2apipay_entries(self) -> None:
        payload = run_cli(
            "app",
            "object",
            "search",
            "--target",
            "prod0-main",
            "--repo-root",
            str(REPO_ROOT),
        )

        self.assertEqual(0, payload.returncode, msg=payload.stderr)
        payload_json = json.loads(payload.stdout)
        self.assertEqual(["sub2api"], [item["app"] for item in payload_json["payload"]["items"]])
        self.assertNotIn("newapi", [item["app"] for item in payload_json["payload"]["items"]])
        self.assertNotIn("sub2apipay", [item["app"] for item in payload_json["payload"]["items"]])

    def test_real_tracked_apps_ledgers_only_include_sub2api(self) -> None:
        for target, contract_file in (
            ("prod0-main", "/root/work/sub2api/deploy/agentplane/contract.yaml"),
            ("prod2-main", "/root/work/sub2api/deploy/agentplane/contract.prod2.yaml"),
        ):
            with self.subTest(target=target):
                ledger_json = json.loads(
                    (REPO_ROOT / "inventory" / "servers" / target / "ledgers" / "apps.json").read_text(encoding="utf-8")
                )
                items = ledger_json["items"]
                self.assertEqual(["sub2api"], [item["app"] for item in items])
                self.assertEqual(contract_file, items[0]["contract_file"])
                ledger_markdown = (
                    REPO_ROOT / "inventory" / "servers" / target / "ledgers" / "apps.md"
                ).read_text(encoding="utf-8")
                self.assertIn("`sub2api` / `compose`", ledger_markdown)
                self.assertNotIn("`newapi` / `compose`", ledger_markdown)
                self.assertNotIn("`sub2apipay` / `compose`", ledger_markdown)

    def test_real_sub2api_inventory_keeps_none_previous_control_plane_rollback(self) -> None:
        inventory_payload = json.loads(
            (REPO_ROOT / "inventory" / "servers" / "prod0-main" / "inventory.json").read_text(encoding="utf-8")
        )
        self.assertIn("sub2api", inventory_payload["services"])
        self.assertEqual({"kind": "none"}, inventory_payload["services"]["sub2api"]["rollback_entry"])


if __name__ == "__main__":
    unittest.main()
