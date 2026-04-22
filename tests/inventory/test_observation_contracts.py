import json
import tempfile
import unittest
from pathlib import Path


def write_app_object_fixture(root: Path) -> Path:
    target = "prod0-main"
    server_root = root / "inventory" / "servers" / target
    server_root.mkdir(parents=True, exist_ok=True)
    (server_root / "inventory.json").write_text(
        json.dumps(
            {
                "services": {
                    "sub2api": {
                        "control_plane": "compose",
                        "public_url": "https://token.zzzai.cloud:8443",
                    }
                },
                "object_ledgers": {
                    "ledgers": {"apps": f"inventory/servers/{target}/ledgers/apps.json"}
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

    catalog_root = root / "inventory" / "apps"
    catalog_root.mkdir(parents=True, exist_ok=True)
    app_root = root / "sub2api"
    (catalog_root / "catalog.json").write_text(
        json.dumps(
            {
                "apps": [
                    {
                        "app": "sub2api",
                        "repo_name": "sub2api",
                        "repo_root": str(app_root),
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

    contract_file = app_root / "deploy" / "agentplane" / "contract.yaml"
    contract_file.parent.mkdir(parents=True, exist_ok=True)
    contract_file.write_text(
        json.dumps({"docs": {"app_summary_file": "docs/AGENTPLANE_DEPLOYMENT.md"}}),
        encoding="utf-8",
    )
    summary_file = app_root / "docs" / "AGENTPLANE_DEPLOYMENT.md"
    summary_file.parent.mkdir(parents=True, exist_ok=True)
    summary_file.write_text("# summary\n", encoding="utf-8")
    return contract_file.resolve()


class ObservationContractTests(unittest.TestCase):
    def test_verification_payload_keeps_resolved_path_out_of_ledger_fields(self) -> None:
        from agentplane.runtime.observation import build_verification_payload

        payload = build_verification_payload(
            canonical_ref="apps/sub2api/contracts/prod0-main",
            ledger_fields={"app": "sub2api"},
            verification_fields={"check": "ok"},
            resolved_path="D:/Projects/AgentPlane/.cache/runtime/contract.yaml",
        )

        self.assertEqual("apps/sub2api/contracts/prod0-main", payload["ledger_fields"]["canonical_ref"])
        self.assertEqual("sub2api", payload["ledger_fields"]["app"])
        self.assertNotIn("resolved_path", payload["ledger_fields"])
        self.assertEqual(
            "D:/Projects/AgentPlane/.cache/runtime/contract.yaml",
            payload["verification_fields"]["resolved_path"],
        )

    def test_extract_ledger_fields_drops_observation_only_keys(self) -> None:
        from agentplane.runtime.observation import extract_ledger_fields

        payload = extract_ledger_fields(
            {
                "canonical_ref": "targets/prod0-main/services/postgres",
                "name": "postgres",
                "verification_fields": {"live": {"ok": True}},
                "observation": {"resolved_path": "D:/tmp/runtime.json"},
                "resolved_path": "D:/tmp/runtime.json",
            }
        )

        self.assertEqual("targets/prod0-main/services/postgres", payload["canonical_ref"])
        self.assertEqual("postgres", payload["name"])
        self.assertNotIn("verification_fields", payload)
        self.assertNotIn("observation", payload)
        self.assertNotIn("resolved_path", payload)

    def test_app_object_verify_separates_ledger_fields_and_observation(self) -> None:
        from agentplane.domain.app.object_handlers import verify_app_object

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            contract_file = write_app_object_fixture(root)

            payload = verify_app_object(root, "prod0-main", "sub2api")

        self.assertTrue(payload["ok"])
        self.assertEqual("apps/sub2api/contracts/prod0-main", payload["canonical_ref"])
        self.assertEqual("apps/sub2api/contracts/prod0-main", payload["ledger_fields"]["canonical_ref"])
        self.assertEqual("sub2api", payload["ledger_fields"]["app"])
        self.assertNotIn("resolved_path", payload["ledger_fields"])
        self.assertEqual(str(contract_file), payload["verification_fields"]["resolved_path"])
        self.assertEqual(str(contract_file), payload["observation"]["resolved_path"])
        self.assertIn("summary_files", payload["verification_fields"])


if __name__ == "__main__":
    unittest.main()

