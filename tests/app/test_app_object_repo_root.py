from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pytest
from tests.support.app_object import run_cli

pytestmark = pytest.mark.integration


class AppObjectRepoRootCliTests(unittest.TestCase):
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
                                "public_url": "https://token.example.net:8443",
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
                        "target": "prod0-main",
                        "repo_name": "sub2api.worktree",
                        "service_key": "sub2api",
                        "canonical_ref": "apps/sub2api/contracts/prod0-main",
                        "resolved_path": str((worktree_root / "deploy" / "agentplane" / "contract.yaml").resolve()),
                        "contract_file": str((worktree_root / "deploy" / "agentplane" / "contract.yaml").resolve()),
                        "control_plane": "compose",
                        "public_url": "https://token.example.net:8443",
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
                                "public_url": "https://token.example.net:8443",
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
                                "public_url": "https://token.example.net:8443",
                            }
                        },
                        "object_ledgers": {"ledgers": {"apps": "inventory/servers/prod0-main/ledgers/apps.json"}},
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            ledger_root = server_root / "ledgers"
            ledger_root.mkdir(parents=True, exist_ok=True)
            (ledger_root / "apps.json").write_text(
                json.dumps({"count": 1}, ensure_ascii=False, indent=2), encoding="utf-8"
            )
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


# ======================================================================
# From: test_app_object_lifecycle.py
# ======================================================================


def _write_catalog(repo_root: Path, payload: dict) -> None:
    path = repo_root / "inventory" / "apps" / "catalog.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_catalog(repo_root: Path) -> dict:
    path = repo_root / "inventory" / "apps" / "catalog.json"
    return json.loads(path.read_text(encoding="utf-8"))


