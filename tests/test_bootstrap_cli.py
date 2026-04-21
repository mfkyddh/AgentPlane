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
    (root / "inventory" / "servers" / "wsl").mkdir(parents=True, exist_ok=True)
    (root / "inventory" / "servers" / "prod0-main").mkdir(parents=True, exist_ok=True)
    (root / "inventory" / "servers" / "prod2-main").mkdir(parents=True, exist_ok=True)

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
    for target in ("wsl", "prod0-main", "prod2-main"):
        (root / "inventory" / "servers" / target / "inventory.json").write_text(
            json.dumps({"target": target}, ensure_ascii=False),
            encoding="utf-8",
        )


def write_takeover_ready_ssh_contract(root: Path) -> None:
    (root / "secrets" / "ssh" / "keys").mkdir(parents=True, exist_ok=True)
    (root / "secrets" / "ssh" / "config").write_text(
        "Host prod0-main 1.2.3.4\n"
        "  HostName 1.2.3.4\n"
        "  User root\n"
        "  IdentityFile <repo-root>/secrets/ssh/keys/prod0-main.pem\n"
        "\n"
        "Host prod2-main 5.6.7.8\n"
        "  HostName 5.6.7.8\n"
        "  User root\n"
        "  IdentityFile <repo-root>/secrets/ssh/keys/prod2-main.pem\n",
        encoding="utf-8",
    )
    (root / "secrets" / "ssh" / "keys" / "prod0-main.pem").write_text("demo-prod0", encoding="utf-8")
    (root / "secrets" / "ssh" / "keys" / "prod2-main.pem").write_text("demo-prod2", encoding="utf-8")


class BootstrapCliTests(unittest.TestCase):
    def test_bootstrap_init_secrets_creates_only_takeover_truth_scaffold(self) -> None:
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
            self.assertTrue((root / "secrets" / "ssh" / "config").is_file())
            self.assertTrue((root / "secrets" / "ssh" / "keys").is_dir())
            self.assertFalse((root / "secrets" / "env" / "prod-jump.env").exists())
            self.assertFalse((root / "secrets" / "services" / "onepanel-login.prod0-main.env").exists())

    def test_bootstrap_verify_secrets_does_not_print_secret_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed_bootstrap_templates(root)
            write_takeover_ready_ssh_contract(root)

            result = run_cli("bootstrap", "verify-secrets", "--repo-root", str(root))

            self.assertEqual(0, result.returncode, msg=result.stderr)
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
        self.assertIn("required_truths", payload["payload"]["contract"])
        self.assertIn("projection_only", payload["payload"]["contract"])

    def test_bootstrap_verify_secrets_requires_structured_ssh_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed_bootstrap_templates(root)
            (root / "secrets" / "ssh").mkdir(parents=True, exist_ok=True)
            (root / "secrets" / "ssh" / "config").write_text(
                "Host prod0-main\n"
                "  HostName 1.2.3.4\n"
                "  User root\n"
                "  IdentityFile <repo-root>/secrets/ssh/keys/prod0-main.pem\n",
                encoding="utf-8",
            )

            result = run_cli("bootstrap", "verify-secrets", "--repo-root", str(root))

            self.assertEqual(1, result.returncode, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["payload"]["ok"])
            issues = payload["payload"]["checks"][0]["issues"]
            self.assertIn("missing-ssh-host:prod2-main", issues)
            self.assertIn("missing-ssh-key:prod0-main.pem", issues)

    def test_bootstrap_doctor_reports_projection_warnings_without_blocking_takeover(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed_bootstrap_templates(root)
            write_takeover_ready_ssh_contract(root)
            (root / "secrets" / "env").mkdir(parents=True, exist_ok=True)
            (root / "secrets" / "env" / "prod-jump.env").write_text(
                "export PROJECT_SSH_CONFIG=/root/work/env_ubuntu/secrets/ssh/config\n",
                encoding="utf-8",
            )

            doctor = run_cli("bootstrap", "doctor", "--repo-root", str(root))

            self.assertEqual(0, doctor.returncode, msg=doctor.stderr)
            payload = json.loads(doctor.stdout)
            self.assertTrue(payload["payload"]["ok"])
            self.assertTrue(payload["payload"]["secrets"]["ok"])
            self.assertFalse(payload["payload"]["projections"]["ok"])
            self.assertEqual("warning", payload["payload"]["readiness_checks"][-1]["severity"])


if __name__ == "__main__":
    unittest.main()
