import json
import tempfile
import unittest
from pathlib import Path

from agentplane.domain.app.catalog import load_app_catalog, write_app_catalog
from agentplane.domain.app.models import AppCatalogEntry
from agentplane.runtime.path_policy import assert_canonical_ref, is_host_specific_path


class TruthPathPolicyTests(unittest.TestCase):
    def test_truth_contract_rejects_windows_drive_paths(self) -> None:
        self.assertTrue(is_host_specific_path("D:/Projects/AgentPlane"))

    def test_truth_contract_rejects_unc_paths(self) -> None:
        self.assertTrue(is_host_specific_path(r"\\wsl.localhost\Ubuntu\root\work\sub2api"))

    def test_truth_contract_allows_canonical_refs(self) -> None:
        self.assertFalse(is_host_specific_path("apps/sub2api/contracts/prod0-main"))
        self.assertEqual("apps/sub2api/contracts/prod0-main", assert_canonical_ref("apps/sub2api/contracts/prod0-main"))

    def test_write_app_catalog_persists_canonical_refs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            entry = AppCatalogEntry(
                app="sub2api",
                repo_name="sub2api",
                repo_root=Path("<app-repo-root>"),
                service_key="sub2api",
                contracts={
                    "wsl": "deploy/agentplane/contract.wsl.yaml",
                    "prod0-main": "deploy/agentplane/contract.yaml",
                },
            )

            catalog_file = write_app_catalog(repo_root, [entry])
            payload = json.loads(catalog_file.read_text(encoding="utf-8"))

            self.assertEqual(
                {
                    "apps": [
                        {
                            "app": "sub2api",
                            "repo_name": "sub2api",
                            "repo_ref": "apps/sub2api",
                            "service_key": "sub2api",
                            "contracts": {
                                "prod0-main": "apps/sub2api/contracts/prod0-main",
                                "wsl": "apps/sub2api/contracts/wsl",
                            },
                        }
                    ]
                },
                payload,
            )

    def test_load_app_catalog_resolves_runtime_path_from_canonical_refs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_root = root / "AgentPlane"
            app_root = root / "sub2api"
            (repo_root / "inventory" / "apps").mkdir(parents=True, exist_ok=True)
            app_root.mkdir(parents=True, exist_ok=True)
            (repo_root / "inventory" / "apps" / "catalog.json").write_text(
                json.dumps(
                    {
                        "apps": [
                            {
                                "app": "sub2api",
                                "repo_name": "sub2api",
                                "repo_ref": "apps/sub2api",
                                "service_key": "sub2api",
                                "contracts": {"prod0-main": "apps/sub2api/contracts/prod0-main"},
                            }
                        ]
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            entries = load_app_catalog(repo_root)

            self.assertEqual(1, len(entries))
            self.assertEqual(app_root.resolve(), entries[0].repo_root.resolve())
            self.assertEqual("deploy/agentplane/contract.yaml", entries[0].contracts["prod0-main"])


if __name__ == "__main__":
    unittest.main()

