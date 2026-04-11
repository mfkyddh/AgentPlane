import tomllib
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class PyprojectConfigTests(unittest.TestCase):
    def test_project_declares_build_system_for_local_package(self) -> None:
        payload = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

        self.assertIn("build-system", payload)
        self.assertEqual("hatchling.build", payload["build-system"]["build-backend"])
        self.assertIn("tool", payload)
        self.assertEqual("agentplane-cli", payload["project"]["name"])
        self.assertEqual("agentplane.cli.app:main", payload["project"]["scripts"]["agentplane"])
        self.assertEqual(["agentplane"], payload["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"])


if __name__ == "__main__":
    unittest.main()
