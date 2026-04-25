from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import yaml
from tests.support.app_delivery_cli import run_app_delivery_cli
from tests.support.app_delivery_contracts import write_contract
from tests.support.app_delivery_targets import (
    baseline_tenant_resources,
    write_inventory,
    write_tenant_secret_files,
)


class AppArtifactContractTests(unittest.TestCase):
    def test_validate_contract_accepts_schema2_artifact_first_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_tenant_secret_files(root, target="wsl")
            write_contract(
                root,
                schema_version=2,
                tenant_resources=baseline_tenant_resources(target="wsl"),
                build_command="bash deploy/build-runtime-artifacts.sh",
                package_command="bash deploy/package-runtime-image.sh",
                packaging_backend="wsl-linux",
            )

            result = run_app_delivery_cli("validate-contract", repo_root=root, app="sub2api", target="wsl")

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)["payload"]
            self.assertEqual("v2", payload["_meta"]["contract_mode"])
            self.assertTrue(payload["_meta"]["artifact_first"])

    def test_validate_contract_rejects_schema2_contract_missing_packaging_backend(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_tenant_secret_files(root)
            contract_file = write_contract(
                root,
                schema_version=2,
                tenant_resources=baseline_tenant_resources(),
                build_command="bash deploy/build-runtime-artifacts.sh",
                package_command="bash deploy/package-runtime-image.sh",
            )
            payload = yaml.safe_load(contract_file.read_text(encoding="utf-8"))
            del payload["packaging"]["backend"]
            contract_file.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8")

            result = run_app_delivery_cli("validate-contract", repo_root=root, app="sub2api")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("packaging.backend", result.stderr)


if __name__ == "__main__":
    unittest.main()
