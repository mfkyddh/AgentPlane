import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from agentplane.cli.prod0_postgres_app_resource_audit import (
    _live_runtime_binding,
    _pg_binding_from_dsn,
    _prod0_app_resource_live_audit_snapshot,
)


class Prod0PostgresAppResourceAuditInternalTests(unittest.TestCase):
    def test_pg_binding_from_dsn_decodes_username_and_database(self) -> None:
        database, user = _pg_binding_from_dsn("postgresql://sub2api_prod0%40tenant:pw@db/sub2api_prod0")

        self.assertEqual("sub2api_prod0", database)
        self.assertEqual("sub2api_prod0@tenant", user)

    def test_live_runtime_binding_prefers_discrete_keys_over_dsn(self) -> None:
        database, user = _live_runtime_binding(
            {
                "env": {
                    "PGDATABASE": "sub2api_prod0",
                    "PGUSER": "sub2api_prod0",
                    "DATABASE_URL": "postgresql://wrong:pw@db/wrong",
                }
            }
        )

        self.assertEqual("sub2api_prod0", database)
        self.assertEqual("sub2api_prod0", user)

    @mock.patch("agentplane.cli.prod0_postgres_app_resource_audit.execute_remote_bash")
    def test_prod0_app_resource_live_audit_snapshot_uses_remote_substrate_script_file(
        self, execute_remote_bash_mock: mock.Mock
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script_file = root / "agentplane" / "scripts" / "remote" / "prod0-postgres-app-resource-live-audit.sh"
            script_file.parent.mkdir(parents=True, exist_ok=True)
            script_file.write_text("#!/bin/sh\n", encoding="utf-8")
            execute_remote_bash_mock.return_value = {
                "result": {"returncode": 0, "stdout": json.dumps({"apps": {}, "catalog": {}}), "stderr": ""},
            }

            payload = _prod0_app_resource_live_audit_snapshot(root)

            self.assertEqual({"apps": {}, "catalog": {}}, payload)
            execute_remote_bash_mock.assert_called_once_with(repo_root=root, target="prod0-main", script_file=script_file)


if __name__ == "__main__":
    unittest.main()
