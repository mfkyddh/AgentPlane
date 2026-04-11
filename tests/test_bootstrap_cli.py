import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "agentplane.cli", *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def seed_bootstrap_templates(root: Path) -> None:
    (root / "templates" / "env").mkdir(parents=True, exist_ok=True)
    (root / "templates" / "ssh").mkdir(parents=True, exist_ok=True)
    (root / "templates" / "services").mkdir(parents=True, exist_ok=True)
    (root / "templates" / "secrets" / "local" / "control-plane").mkdir(parents=True, exist_ok=True)
    (root / "templates" / "secrets" / "targets" / "_template").mkdir(parents=True, exist_ok=True)

    (root / "templates" / "env" / "prod-jump.env.example").write_text(
        "CLOUDFLARE_API_TOKEN=replace-with-api-token\n",
        encoding="utf-8",
    )
    (root / "templates" / "ssh" / "config.example").write_text(
        "Host prod0-main\n  HostName REPLACE_WITH_PRIMARY_IP\n",
        encoding="utf-8",
    )
    (root / "templates" / "services" / "onepanel-login.env.example").write_text(
        "ONEPANEL_USERNAME=replace-with-onepanel-username\n"
        "ONEPANEL_PASSWORD=replace-with-onepanel-password\n",
        encoding="utf-8",
    )
    (root / "templates" / "secrets" / "local" / "control-plane" / "README.md").write_text(
        "local control-plane\n",
        encoding="utf-8",
    )
    (root / "templates" / "secrets" / "targets" / "_template" / "README.md").write_text(
        "target <target>\n",
        encoding="utf-8",
    )


class BootstrapCliTests(unittest.TestCase):
    def test_bootstrap_init_secrets_creates_expected_scaffold(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed_bootstrap_templates(root)

            result = run_cli("bootstrap", "init-secrets", "--repo-root", str(root))

            self.assertEqual(0, result.returncode, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("bootstrap", payload["command"])
            self.assertEqual("init-secrets", payload["action"])
            self.assertTrue((root / "secrets" / "local" / "control-plane").is_dir())
            self.assertTrue((root / "secrets" / "targets" / "wsl").is_dir())
            self.assertTrue((root / "secrets" / "targets" / "prod0-main").is_dir())
            self.assertTrue((root / "secrets" / "targets" / "prod2-main").is_dir())
            self.assertTrue((root / "secrets" / "env" / "prod-jump.env").is_file())
            self.assertTrue((root / "secrets" / "ssh" / "config").is_file())
            self.assertTrue((root / "secrets" / "services" / "onepanel-login.prod0-main.env").is_file())

    def test_bootstrap_verify_secrets_does_not_print_secret_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed_bootstrap_templates(root)
            (root / "secrets" / "env").mkdir(parents=True, exist_ok=True)
            (root / "secrets" / "ssh").mkdir(parents=True, exist_ok=True)
            (root / "secrets" / "services").mkdir(parents=True, exist_ok=True)
            (root / "secrets" / "env" / "prod-jump.env").write_text(
                "CLOUDFLARE_API_TOKEN=SECRET_VALUE\n",
                encoding="utf-8",
            )
            (root / "secrets" / "ssh" / "config").write_text(
                "Host prod0-main\n  HostName 1.2.3.4\n",
                encoding="utf-8",
            )
            for target in ("wsl", "prod0-main", "prod2-main"):
                (root / "secrets" / "services" / f"onepanel-login.{target}.env").write_text(
                    "ONEPANEL_USERNAME=demo\nONEPANEL_PASSWORD=SUPER_SECRET\n",
                    encoding="utf-8",
                )

            result = run_cli("bootstrap", "verify-secrets", "--repo-root", str(root))

            self.assertEqual(0, result.returncode, msg=result.stderr)
            self.assertNotIn("SECRET_VALUE", result.stdout)
            self.assertNotIn("SUPER_SECRET", result.stdout)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["payload"]["ok"])

    def test_bootstrap_inspect_local_reports_host_profile_and_path_policy(self) -> None:
        result = run_cli("bootstrap", "inspect-local", "--repo-root", str(REPO_ROOT))

        self.assertEqual(0, result.returncode, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual("bootstrap", payload["command"])
        self.assertEqual("inspect-local", payload["action"])
        self.assertEqual("canonical-ref-only", payload["payload"]["path_policy"]["truth"])
        self.assertIn("host_profile", payload["payload"])

    def test_bootstrap_doctor_flags_placeholder_scaffold_until_human_fills_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed_bootstrap_templates(root)
            init_result = run_cli("bootstrap", "init-secrets", "--repo-root", str(root))
            self.assertEqual(0, init_result.returncode, msg=init_result.stderr)

            doctor = run_cli("bootstrap", "doctor", "--repo-root", str(root))

            self.assertEqual(1, doctor.returncode, msg=doctor.stderr)
            payload = json.loads(doctor.stdout)
            self.assertFalse(payload["payload"]["ok"])
            self.assertFalse(payload["payload"]["secrets"]["ok"])


if __name__ == "__main__":
    unittest.main()
