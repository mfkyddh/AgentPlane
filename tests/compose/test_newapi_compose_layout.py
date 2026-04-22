import unittest
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]


def load_compose(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


class NewApiComposeLayoutTests(unittest.TestCase):
    def test_wsl_template_matches_expected_layout(self) -> None:
        compose = load_compose(REPO_ROOT / "infra" / "compose" / "newapi" / "docker-compose.wsl.yml")
        service = compose["services"]["newapi"]

        self.assertEqual("newapi-dev", service["container_name"])
        self.assertIn("0.0.0.0:3000:3000", service["ports"])
        self.assertIn("/data/newapi/data:/data", service["volumes"])
        self.assertIn("/data/newapi/logs:/app/logs", service["volumes"])
        self.assertEqual(["zqf_network"], service["networks"])

    def test_prod_template_matches_expected_layout(self) -> None:
        compose = load_compose(REPO_ROOT / "infra" / "compose" / "newapi" / "docker-compose.prod0.yml")
        service = compose["services"]["newapi"]

        self.assertEqual("newapi-prod", service["container_name"])
        self.assertIn("127.0.0.1:3000:3000", service["ports"])
        self.assertIn("/data/newapi/data:/data", service["volumes"])
        self.assertIn("/data/newapi/logs:/app/logs", service["volumes"])
        self.assertEqual(["zqf_network"], service["networks"])

    def test_prod2_template_matches_expected_layout(self) -> None:
        compose = load_compose(REPO_ROOT / "infra" / "compose" / "newapi" / "docker-compose.prod2.yml")
        service = compose["services"]["newapi"]

        self.assertEqual("newapi-prod", service["container_name"])
        self.assertEqual(["../../../secrets/services/newapi.prod2.env"], service["env_file"])
        self.assertIn("127.0.0.1:3000:3000", service["ports"])
        self.assertIn("/data/newapi/data:/data", service["volumes"])
        self.assertIn("/data/newapi/logs:/app/logs", service["volumes"])
        self.assertEqual(["zqf_network"], service["networks"])

    def test_wsl_env_template_uses_isolated_postgres_database(self) -> None:
        env_template = (REPO_ROOT / "templates" / "services" / "newapi.wsl.env.example").read_text(encoding="utf-8")

        self.assertIn("SQL_DSN=postgresql://newapi_wsl:<postgres_password>@postgres18-dev:5432/newapi_wsl?sslmode=disable", env_template)
        self.assertIn("REDIS_CONN_STRING=redis://:<redis_password>@redis7-dev:6379/2", env_template)

    def test_prod2_env_template_uses_prod2_isolated_resources(self) -> None:
        env_template = (REPO_ROOT / "templates" / "services" / "newapi.prod2.env.example").read_text(encoding="utf-8")

        self.assertIn(
            "SQL_DSN=postgresql://newapi_prod2:<urlencoded-postgres-password>@postgres18-prod:5432/newapi_prod2?sslmode=disable",
            env_template,
        )
        self.assertIn("REDIS_CONN_STRING=redis://:<urlencoded-redis-password>@redis7-prod:6379/2", env_template)


if __name__ == "__main__":
    unittest.main()

