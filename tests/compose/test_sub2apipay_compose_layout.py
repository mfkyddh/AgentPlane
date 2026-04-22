import unittest
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]


def load_compose(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


class Sub2ApiPayComposeLayoutTests(unittest.TestCase):
    def test_wsl_template_matches_contract(self) -> None:
        compose = load_compose(REPO_ROOT / "infra" / "compose" / "sub2apipay" / "docker-compose.wsl.yml")
        service = compose["services"]["sub2apipay"]

        self.assertEqual("sub2apipay-dev", service["container_name"])
        self.assertIn("0.0.0.0:18091:3000", service["ports"])
        self.assertIn("/data/sub2apipay/data:/data", service["volumes"])
        self.assertEqual(["zqf_network"], service["networks"])
        self.assertEqual(["CMD-SHELL", "wget -q -O /dev/null http://127.0.0.1:3000/pay"], service["healthcheck"]["test"])

    def test_prod_template_matches_contract(self) -> None:
        compose = load_compose(REPO_ROOT / "infra" / "compose" / "sub2apipay" / "docker-compose.prod0.yml")
        service = compose["services"]["sub2apipay"]

        self.assertEqual("sub2apipay-prod", service["container_name"])
        self.assertIn("127.0.0.1:18091:3000", service["ports"])
        self.assertIn("../../../secrets/services/sub2apipay.prod0.env", service["env_file"])
        self.assertIn("/data/sub2apipay/data:/data", service["volumes"])
        self.assertEqual(["zqf_network"], service["networks"])
        self.assertEqual(["CMD-SHELL", "wget -q -O /dev/null http://127.0.0.1:3000/pay"], service["healthcheck"]["test"])

    def test_wsl_env_template_uses_isolated_database(self) -> None:
        env_template = (REPO_ROOT / "templates" / "services" / "sub2apipay.wsl.env.example").read_text(encoding="utf-8")

        self.assertIn("DATABASE_URL=postgresql://sub2apipay_wsl:<postgres_password>@postgres18-dev:5432/sub2apipay_dev", env_template)
        self.assertIn("NEXT_PUBLIC_APP_URL=http://127.0.0.1:18091", env_template)

    def test_prod0_env_template_uses_prod0_postgres_tenant(self) -> None:
        env_template = (REPO_ROOT / "templates" / "services" / "sub2apipay.prod0.env.example").read_text(encoding="utf-8")

        self.assertIn("DATABASE_URL=postgresql://sub2apipay_prod0:<urlencoded-postgres-password>@postgres18-prod:5432/sub2apipay", env_template)
        self.assertIn("NEXT_PUBLIC_APP_URL=https://pay.zzzai.cloud:8443", env_template)


if __name__ == "__main__":
    unittest.main()

