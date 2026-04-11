import unittest
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
SUB2API_ROOT = Path("/root/work/sub2api")


def load_compose(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


class Sub2ApiComposeLayoutTests(unittest.TestCase):
    def test_sub2api_contracts_use_artifact_first_schema_v2(self) -> None:
        expected_targets = {
            "wsl": SUB2API_ROOT / "deploy" / "agentplane" / "contract.wsl.yaml",
            "prod0-main": SUB2API_ROOT / "deploy" / "agentplane" / "contract.yaml",
            "prod2-main": SUB2API_ROOT / "deploy" / "agentplane" / "contract.prod2.yaml",
        }

        for target, contract_path in expected_targets.items():
            with self.subTest(target=target):
                contract = load_compose(contract_path)
                self.assertEqual(2, contract["schema_version"])
                self.assertEqual("bash deploy/build-runtime-artifacts.sh", contract["artifact"]["build_command"])
                self.assertEqual("dist/oplinux", contract["artifact"]["output_path"])
                self.assertEqual("linux", contract["artifact"]["runtime_os"])
                self.assertEqual("amd64", contract["artifact"]["runtime_arch"])
                self.assertEqual("wsl-linux", contract["packaging"]["backend"])
                self.assertEqual("sub2api-prod", contract["packaging"]["image_name"])
                self.assertEqual("bash deploy/package-runtime-image.sh", contract["packaging"]["package_command"])

    def test_sub2api_build_and_package_scripts_are_split(self) -> None:
        build_script = (SUB2API_ROOT / "deploy" / "build-runtime-artifacts.sh").read_text(encoding="utf-8")
        package_script = (SUB2API_ROOT / "deploy" / "package-runtime-image.sh").read_text(encoding="utf-8")

        self.assertNotIn("docker build", build_script)
        self.assertNotIn("build-runtime-artifacts.sh", package_script)
        self.assertIn("ARTIFACT_OUTPUT_PATH", build_script)
        self.assertIn("ARTIFACT_OUTPUT_PATH", package_script)
        self.assertIn("docker build", package_script)

    def test_wsl_template_matches_contract(self) -> None:
        compose = load_compose(REPO_ROOT / "infra" / "compose" / "sub2api" / "docker-compose.wsl.yml")
        service = compose["services"]["sub2api"]

        self.assertEqual("sub2api-dev", service["container_name"])
        self.assertIn("0.0.0.0:18080:8080", service["ports"])
        self.assertIn("/data/sub2api/data:/app/data", service["volumes"])
        self.assertEqual(["zqf_network"], service["networks"])

    def test_prod_template_matches_contract(self) -> None:
        compose = load_compose(REPO_ROOT / "infra" / "compose" / "sub2api" / "docker-compose.prod0.yml")
        service = compose["services"]["sub2api"]

        self.assertEqual("sub2api-prod", service["container_name"])
        self.assertIn("127.0.0.1:18080:8080", service["ports"])
        self.assertIn("/data/sub2api/data:/app/data", service["volumes"])
        self.assertEqual(["zqf_network"], service["networks"])

    def test_prod2_template_matches_contract(self) -> None:
        compose = load_compose(REPO_ROOT / "infra" / "compose" / "sub2api" / "docker-compose.prod2.yml")
        service = compose["services"]["sub2api"]

        self.assertEqual("sub2api-prod", service["container_name"])
        self.assertIn("127.0.0.1:18080:8080", service["ports"])
        self.assertIn("../../../secrets/services/sub2api.prod2.env", service["env_file"])
        self.assertEqual(["zqf_network"], service["networks"])

    def test_wsl_env_template_uses_isolated_database(self) -> None:
        env_template = (REPO_ROOT / "templates" / "services" / "sub2api.wsl.env.example").read_text(encoding="utf-8")

        self.assertIn("DATABASE_USER=sub2api_wsl", env_template)
        self.assertIn("DATABASE_DBNAME=sub2api_wsl", env_template)
        self.assertIn("REDIS_DB=1", env_template)
        self.assertIn("REDIS_PASSWORD=<redis_password>", env_template)

    def test_prod2_env_template_exists_for_target_scoped_runtime_projection(self) -> None:
        env_template = (REPO_ROOT / "templates" / "services" / "sub2api.prod2.env.example").read_text(encoding="utf-8")

        self.assertIn("DATABASE_USER=sub2api_prod2", env_template)
        self.assertIn("DATABASE_DBNAME=sub2api_prod2", env_template)
        self.assertIn("REDIS_DB=1", env_template)


if __name__ == "__main__":
    unittest.main()
