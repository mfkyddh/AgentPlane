import unittest
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
OFFICIAL_WSL_IMAGE = "${SUB2API_IMAGE_REF:-ghcr.io/wei-shaw/sub2api:latest}"


def load_compose(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


class Sub2ApiComposeLayoutTests(unittest.TestCase):
    def test_wsl_template_matches_contract(self) -> None:
        compose = load_compose(REPO_ROOT / "infra" / "compose" / "sub2api" / "docker-compose.wsl.yml")
        service = compose["services"]["sub2api"]

        self.assertEqual(OFFICIAL_WSL_IMAGE, service["image"])
        self.assertEqual("always", service["pull_policy"])
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

