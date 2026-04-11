import tempfile
import unittest
from pathlib import Path

from agentplane.cli.secrets import materialize_legacy_host_layout
from agentplane.runtime.bootstrap import bootstrap_directory_specs, bootstrap_required_truth_specs


class SecretsHostLayoutTests(unittest.TestCase):
    def test_bootstrap_required_truth_specs_keep_takeover_truth_separate_from_projections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            specs = bootstrap_required_truth_specs(root)
            refs = {item["secret_ref"]: item["destination"] for item in specs}

            self.assertEqual(
                str(root / "secrets" / "ssh" / "config").replace("\\", "/"),
                str(refs["local/control-plane/ssh-config"]).replace("\\", "/"),
            )
            self.assertNotIn("local/control-plane/prod-jump", refs)

    def test_bootstrap_directory_specs_follow_inventory_targets_instead_of_hardcoded_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "inventory" / "servers" / "wsl").mkdir(parents=True, exist_ok=True)
            (root / "inventory" / "servers" / "prod9-main").mkdir(parents=True, exist_ok=True)
            (root / "inventory" / "servers" / "wsl" / "inventory.json").write_text("{}", encoding="utf-8")
            (root / "inventory" / "servers" / "prod9-main" / "inventory.json").write_text("{}", encoding="utf-8")

            specs = bootstrap_directory_specs(root)
            targets = {item["scope"] for item in specs if item["scope"].startswith("targets/")}

            self.assertEqual({"targets/wsl", "targets/prod9-main"}, targets)

    def test_materialize_legacy_host_layout_projects_host_truth_into_legacy_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            host_root = root / "secrets" / "hosts" / "prod0-main"
            (host_root / "onepanel").mkdir(parents=True, exist_ok=True)
            (host_root / "infra" / "postgres").mkdir(parents=True, exist_ok=True)
            (host_root / "apps" / "newapi" / "tenants").mkdir(parents=True, exist_ok=True)
            (host_root / "apps" / "newapi").mkdir(parents=True, exist_ok=True)

            (host_root / "onepanel" / "api.env").write_text("ONEPANEL_API_KEY=demo\n", encoding="utf-8")
            (host_root / "infra" / "postgres" / "admin.env").write_text("POSTGRES_USER=postgres\n", encoding="utf-8")
            (host_root / "apps" / "newapi" / "runtime.env").write_text("DATABASE_URL=postgres://demo\n", encoding="utf-8")
            (host_root / "apps" / "newapi" / "tenants" / "postgres.env").write_text("PGDATABASE=newapi_prod0\n", encoding="utf-8")

            payload = materialize_legacy_host_layout(root, "prod0-main", write=True)

            self.assertEqual("prod0-main", payload["target"])
            self.assertTrue((root / "secrets" / "services" / "onepanel-api.env").is_file())
            self.assertTrue((root / "secrets" / "services" / "postgres" / "admin.prod0.env").is_file())
            self.assertTrue((root / "secrets" / "services" / "newapi.prod0.env").is_file())
            self.assertTrue((root / "secrets" / "tenants" / "prod0-main" / "newapi" / "postgres.env").is_file())
            self.assertEqual(
                "ONEPANEL_API_KEY=demo\n",
                (root / "secrets" / "services" / "onepanel-api.env").read_text(encoding="utf-8"),
            )

    def test_materialize_legacy_host_layout_projects_backup_env_with_host_first_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            host_root = root / "secrets" / "hosts" / "wsl"
            automation_root = host_root / "automations"
            automation_root.mkdir(parents=True, exist_ok=True)

            (automation_root / "secrets-backup.r2.env").write_text(
                "SECRETS_BACKUP_SOURCE_DIR=/root/work/AgentPlane/secrets/hosts/wsl\n"
                "SECRETS_BACKUP_STATE_FILE=/data/agentplane/secrets-backup/state.json\n",
                encoding="utf-8",
            )

            payload = materialize_legacy_host_layout(root, "wsl", write=True)
            self.assertEqual("wsl", payload["target"])

            projected = root / "secrets" / "services" / "secrets-backup.r2.wsl.env"
            self.assertTrue(projected.is_file())
            projected_text = projected.read_text(encoding="utf-8")
            self.assertIn(
                f"SECRETS_BACKUP_SOURCE_DIR={root}/secrets/hosts/wsl".replace("\\", "/"),
                projected_text.replace("\\", "/"),
            )
