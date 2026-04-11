import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agentplane.scripts.onepanel.compose_policy import (  # type: ignore  # noqa: E402
    enforce_zqf_network,
    normalize_compose_for_app,
    requires_host_network,
)


class ComposePolicyTests(unittest.TestCase):
    def test_openresty_requires_host_network(self) -> None:
        self.assertTrue(requires_host_network("openresty"))
        self.assertFalse(requires_host_network("new-api"))
        self.assertFalse(requires_host_network("demo-app"))

    def test_replaces_legacy_1panel_network_with_zqf_network(self) -> None:
        raw = """
services:
  demo:
    image: demo:latest
    networks:
      - 1panel-network
networks:
  1panel-network:
    external: true
""".strip()

        rendered = enforce_zqf_network(raw)

        self.assertIn("zqf_network", rendered)
        self.assertNotIn("1panel-network", rendered)

    def test_preserves_extra_networks_while_forcing_zqf_network(self) -> None:
        raw = """
services:
  demo:
    image: demo:latest
    networks:
      - app-private
networks:
  app-private:
    external: true
""".strip()

        rendered = enforce_zqf_network(raw)

        self.assertIn("zqf_network", rendered)
        self.assertIn("app-private", rendered)

    def test_openresty_is_normalized_to_host_network(self) -> None:
        raw = """
services:
  openresty:
    image: openresty:latest
    networks:
      - 1panel-network
networks:
  1panel-network:
    external: true
""".strip()

        rendered = normalize_compose_for_app("openresty", raw)

        self.assertIn("network_mode: host", rendered)
        self.assertNotIn("zqf_network", rendered)
        self.assertNotIn("1panel-network", rendered)

    def test_non_openresty_app_never_gets_host_network_exception(self) -> None:
        raw = """
services:
  demo:
    image: demo:latest
""".strip()

        rendered = normalize_compose_for_app("demo", raw)

        self.assertIn("zqf_network", rendered)
        self.assertNotIn("network_mode: host", rendered)


if __name__ == "__main__":
    unittest.main()
