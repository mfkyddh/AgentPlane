import json
import tempfile
import unittest
from pathlib import Path

from agentplane.cli.audit import audit_filesystem


class WslAuditTests(unittest.TestCase):
    def test_detects_legacy_compose_entrypoints_and_env_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service_dir = root / "infra" / "compose" / "redis"
            service_dir.mkdir(parents=True, exist_ok=True)
            (service_dir / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
            (service_dir / ".env").write_text("REDIS_PASSWORD=demo\n", encoding="utf-8")

            result = audit_filesystem(root, "wsl")
            codes = {item["id"] for item in result["violations"]}

            self.assertIn("wsl.legacy.compose_entrypoint", codes)
            self.assertIn("wsl.legacy.env_file", codes)

    def test_detects_compose_scoped_private_env_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service_dir = root / "infra" / "compose" / "cliproxyapi"
            service_dir.mkdir(parents=True, exist_ok=True)
            (service_dir / "docker-compose.wsl.yml").write_text("services: {}\n", encoding="utf-8")
            (service_dir / "docker-compose.prod0.yml").write_text("services: {}\n", encoding="utf-8")
            (service_dir / ".env.wsl").write_text("FOO=bar\n", encoding="utf-8")
            (service_dir / ".env.prod0").write_text("FOO=bar\n", encoding="utf-8")

            result = audit_filesystem(root, "wsl")
            codes = {item["id"] for item in result["violations"]}

            self.assertIn("wsl.compose.private_env_file", codes)

    def test_allows_minimal_compliant_compose_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service_dir = root / "infra" / "compose" / "minio"
            service_dir.mkdir(parents=True, exist_ok=True)
            (service_dir / "docker-compose.wsl.yml").write_text("services: {}\n", encoding="utf-8")
            (service_dir / "docker-compose.prod0.yml").write_text("services: {}\n", encoding="utf-8")

            result = audit_filesystem(root, "wsl")
            wsl_violations = [item for item in result["violations"] if item["scope"] == "wsl"]
            self.assertEqual([], wsl_violations, msg=json.dumps(result, ensure_ascii=False))

    def test_exempts_prod2_only_compose_directories_from_wsl_template_requirement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service_dir = root / "infra" / "compose" / "vmail"
            service_dir.mkdir(parents=True, exist_ok=True)
            (service_dir / "docker-compose.prod2.yml").write_text("services: {}\n", encoding="utf-8")

            prod2_inventory = root / "inventory" / "servers" / "prod2-main" / "inventory.json"
            prod2_inventory.parent.mkdir(parents=True, exist_ok=True)
            prod2_inventory.write_text(
                json.dumps(
                    {
                        "services": {
                            "vmail": {
                                "control_plane": "compose",
                            }
                        }
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            result = audit_filesystem(root, "wsl")
            codes = {item["id"] for item in result["violations"]}

            self.assertNotIn("wsl.missing.compose_wsl", codes)
            self.assertNotIn("wsl.missing.compose_prod0", codes)


if __name__ == "__main__":
    unittest.main()
