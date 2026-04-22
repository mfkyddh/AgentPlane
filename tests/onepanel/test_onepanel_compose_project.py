import json
import tempfile
import unittest
from pathlib import Path

from agentplane.scripts.onepanel.env_targets import get_target
from agentplane.scripts.onepanel.compose_project import render_sub2apipay_compose


class OnePanelComposeProjectTests(unittest.TestCase):
    def test_prod0_target_uses_root_direct_ssh(self) -> None:
        target = get_target("prod0-main")

        self.assertEqual("root", target.ssh_user)
        self.assertFalse(target.ssh_requires_sudo)

    def test_prod2_target_uses_root_direct_ssh(self) -> None:
        target = get_target("prod2-main")

        self.assertEqual("root", target.ssh_user)
        self.assertFalse(target.ssh_requires_sudo)

    def test_render_sub2apipay_compose_rewrites_runtime_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory_file = root / "inventory" / "servers" / "prod0-main" / "inventory.json"
            inventory_file.parent.mkdir(parents=True, exist_ok=True)
            inventory_file.write_text(
                json.dumps(
                    {
                        "services": {
                            "sub2apipay": {
                                "container_name": "sub2apipay-prod",
                                "compose_file": "/data/sub2apipay/app/current/docker-compose.prod.yml",
                                "config_files": [
                                    "/data/sub2apipay/config/sub2apipay-prod.env",
                                    "/data/sub2apipay/config/.env.runtime",
                                ],
                                "host_binding": "127.0.0.1:18091",
                                "container_port": 3000,
                            }
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            raw = """
services:
  app:
    container_name: old-name
    image: demo:latest
    env_file:
      - /etc/sub2apipay/sub2apipay-prod.env
    ports:
      - "127.0.0.1:9999:3000"
    networks:
      - bridge
""".strip()

            rendered = render_sub2apipay_compose(root, raw)

            self.assertIn("container_name: sub2apipay-prod", rendered)
            self.assertIn("/data/sub2apipay/config/sub2apipay-prod.env", rendered)
            self.assertIn("/data/sub2apipay/config/.env.runtime", rendered)
            self.assertIn("127.0.0.1:18091:3000", rendered)
            self.assertIn("zqf_network", rendered)


if __name__ == "__main__":
    unittest.main()

