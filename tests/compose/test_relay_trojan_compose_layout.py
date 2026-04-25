import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


def load_compose(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


class RelayTrojanComposeLayoutTests(unittest.TestCase):
    def test_prod2_template_matches_contract(self) -> None:
        compose = load_compose(
            REPO_ROOT / "infra" / "compose" / "relay-trojan" / "docker-compose.prod2.yml"
        )
        service = compose["services"]["relay-trojan"]

        self.assertEqual("ghcr.io/xtls/xray-core:25.3.6", service["image"])
        self.assertEqual("relay-trojan-prod", service["container_name"])
        self.assertNotIn("env_file", service)
        self.assertEqual("unless-stopped", service["restart"])
        self.assertEqual(
            "run -config /data/relay-trojan/config/config.json", service["command"]
        )
        self.assertIn("0.0.0.0:24443:24443", service["ports"])
        self.assertIn("/data/relay-trojan:/data/relay-trojan", service["volumes"])
        self.assertEqual(["zqf_network"], service["networks"])

    def test_runtime_config_template_matches_contract(self) -> None:
        config = load_compose(
            REPO_ROOT / "infra" / "compose" / "relay-trojan" / "config.template.json"
        )

        inbound = config["inbounds"][0]
        client = inbound["settings"]["clients"][0]
        certificate = inbound["streamSettings"]["tlsSettings"]["certificates"][0]

        self.assertEqual(24443, inbound["port"])
        self.assertEqual("0.0.0.0", inbound["listen"])
        self.assertEqual("trojan", inbound["protocol"])
        self.assertEqual("<RELAY_TROJAN_PASSWORD>", client["password"])
        self.assertEqual("tls", inbound["streamSettings"]["security"])
        self.assertEqual(
            "/data/relay-trojan/certs/fullchain.pem", certificate["certificateFile"]
        )
        self.assertEqual("/data/relay-trojan/certs/privkey.pem", certificate["keyFile"])

    def test_prod2_env_template_matches_contract(self) -> None:
        env_template = (
            REPO_ROOT
            / "templates"
            / "services"
            / "relay-trojan.prod2.env.example"
        ).read_text(encoding="utf-8")

        self.assertIn("RELAY_TROJAN_PUBLIC_DOMAIN=relay.zzzai.fun", env_template)
        self.assertIn("RELAY_TROJAN_PUBLIC_PORT=24443", env_template)
        self.assertIn("RELAY_TROJAN_PASSWORD=replace-with-32-byte-random-string", env_template)
        self.assertNotIn("RELAY_TROJAN_IMAGE_REF=", env_template)
        self.assertNotIn("RELAY_TROJAN_CONTAINER_NAME=", env_template)
        self.assertNotIn("RELAY_TROJAN_CERT_FULLCHAIN=", env_template)
        self.assertNotIn("RELAY_TROJAN_CERT_KEY=", env_template)


if __name__ == "__main__":
    unittest.main()

