"""Tests for agentplane.domain.infra.postgres_audit — DSN parsing, env resolution, live audit."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from agentplane.domain.infra.postgres_audit import (
    _PG_RUNTIME_DATABASE_KEYS,
    _PG_RUNTIME_DSN_KEYS,
    _PG_RUNTIME_USER_KEYS,
    _env_value,
    _live_runtime_binding,
    _pg_binding_from_dsn,
    _prod0_app_resource_live_audit_snapshot,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# _env_value
# ---------------------------------------------------------------------------


class TestEnvValue:
    def test_first_match(self) -> None:
        assert _env_value({"DATABASE_DBNAME": "mydb"}, _PG_RUNTIME_DATABASE_KEYS) == "mydb"

    def test_later_match(self) -> None:
        assert _env_value({"PGDATABASE": "pgdb"}, _PG_RUNTIME_DATABASE_KEYS) == "pgdb"

    def test_no_match(self) -> None:
        assert _env_value({"OTHER_KEY": "val"}, _PG_RUNTIME_DATABASE_KEYS) is None

    def test_empty_dict(self) -> None:
        assert _env_value({}, _PG_RUNTIME_DATABASE_KEYS) is None

    def test_non_dict_input(self) -> None:
        assert _env_value("not a dict", _PG_RUNTIME_DATABASE_KEYS) is None
        assert _env_value(None, _PG_RUNTIME_DATABASE_KEYS) is None
        assert _env_value(42, _PG_RUNTIME_DATABASE_KEYS) is None
        assert _env_value([1, 2], _PG_RUNTIME_DATABASE_KEYS) is None

    def test_empty_string_value_skipped(self) -> None:
        assert _env_value({"DATABASE_DBNAME": ""}, _PG_RUNTIME_DATABASE_KEYS) is None

    def test_none_value_skipped(self) -> None:
        assert _env_value({"DATABASE_DBNAME": None}, _PG_RUNTIME_DATABASE_KEYS) is None

    def test_non_string_value_skipped(self) -> None:
        assert _env_value({"DATABASE_DBNAME": 123}, _PG_RUNTIME_DATABASE_KEYS) is None

    def test_first_non_empty_wins(self) -> None:
        env = {"DATABASE_DBNAME": "", "DATABASE_NAME": "realdb"}
        assert _env_value(env, _PG_RUNTIME_DATABASE_KEYS) == "realdb"

    def test_user_keys(self) -> None:
        assert _env_value({"PGUSER": "admin"}, _PG_RUNTIME_USER_KEYS) == "admin"

    def test_dsn_keys(self) -> None:
        assert _env_value({"DATABASE_URL": "postgres://x/y"}, _PG_RUNTIME_DSN_KEYS) == "postgres://x/y"


# ---------------------------------------------------------------------------
# _pg_binding_from_dsn
# ---------------------------------------------------------------------------


class TestPgBindingFromDsn:
    def test_standard_dsn(self) -> None:
        db, user = _pg_binding_from_dsn("postgres://admin:secret@localhost:5432/mydb")
        assert db == "mydb"
        assert user == "admin"

    def test_dsn_without_port(self) -> None:
        db, user = _pg_binding_from_dsn("postgres://admin@localhost/mydb")
        assert db == "mydb"
        assert user == "admin"

    def test_dsn_with_encoded_password(self) -> None:
        db, user = _pg_binding_from_dsn("postgres://us%40er:p%40ss@host/db")
        assert db == "db"
        assert user == "us@er"

    def test_dsn_with_encoded_username(self) -> None:
        db, user = _pg_binding_from_dsn("postgres://my%2Duser:pw@host/mydb")
        assert user == "my-user"

    def test_dsn_no_database(self) -> None:
        db, user = _pg_binding_from_dsn("postgres://admin@localhost/")
        assert db is None
        assert user == "admin"

    def test_dsn_no_user(self) -> None:
        db, user = _pg_binding_from_dsn("postgres://localhost/mydb")
        assert db == "mydb"
        assert user is None

    def test_dsn_no_user_no_database(self) -> None:
        db, user = _pg_binding_from_dsn("postgres://localhost/")
        assert db is None
        assert user is None

    def test_empty_path(self) -> None:
        db, user = _pg_binding_from_dsn("postgres://u@h")
        assert db is None
        assert user == "u"

    def test_dsn_with_query_params(self) -> None:
        db, user = _pg_binding_from_dsn("postgres://u:p@h/db?sslmode=require")
        assert db == "db"
        assert user == "u"

    def test_postgresql_scheme(self) -> None:
        db, user = _pg_binding_from_dsn("postgresql://u:p@h/dbname")
        assert db == "dbname"
        assert user == "u"

    def test_bare_path_as_dsn(self) -> None:
        db, user = _pg_binding_from_dsn("not-a-url")
        assert db == "not-a-url"
        assert user is None

    def test_empty_string(self) -> None:
        db, user = _pg_binding_from_dsn("")
        assert db is None
        assert user is None

    def test_dsn_with_special_chars_in_db(self) -> None:
        db, user = _pg_binding_from_dsn("postgres://u@h/my-dB_2")
        assert db == "my-dB_2"


# ---------------------------------------------------------------------------
# _live_runtime_binding
# ---------------------------------------------------------------------------


class TestLiveRuntimeBinding:
    def test_direct_env_keys(self) -> None:
        runtime: dict[str, Any] = {
            "env": {"DATABASE_DBNAME": "appdb", "PGUSER": "owner"},
        }
        db, user = _live_runtime_binding(runtime)
        assert db == "appdb"
        assert user == "owner"

    def test_dsn_fallback_for_both(self) -> None:
        runtime: dict[str, Any] = {
            "env": {"DATABASE_URL": "postgres://dsnuser:pw@h/dsdb"},
        }
        db, user = _live_runtime_binding(runtime)
        assert db == "dsdb"
        assert user == "dsnuser"

    def test_dsn_fills_only_missing_database(self) -> None:
        runtime: dict[str, Any] = {
            "env": {
                "PGUSER": "envuser",
                "DATABASE_URL": "postgres://dsnuser:pw@h/dsdb",
            },
        }
        db, user = _live_runtime_binding(runtime)
        assert db == "dsdb"
        assert user == "envuser"

    def test_dsn_fills_only_missing_user(self) -> None:
        runtime: dict[str, Any] = {
            "env": {
                "DATABASE_DBNAME": "envdb",
                "DATABASE_URL": "postgres://dsnuser:pw@h/dsdb",
            },
        }
        db, user = _live_runtime_binding(runtime)
        assert db == "envdb"
        assert user == "dsnuser"

    def test_runtime_dict_fallback(self) -> None:
        runtime: dict[str, Any] = {
            "database": "rtdb",
            "user": "rtuser",
        }
        db, user = _live_runtime_binding(runtime)
        assert db == "rtdb"
        assert user == "rtuser"

    def test_mixed_env_and_runtime_fallback(self) -> None:
        runtime: dict[str, Any] = {
            "env": {"DATABASE_DBNAME": "envdb"},
            "user": "rtuser",
        }
        db, user = _live_runtime_binding(runtime)
        assert db == "envdb"
        assert user == "rtuser"

    def test_empty_runtime(self) -> None:
        db, user = _live_runtime_binding({})
        assert db is None
        assert user is None

    def test_non_dict_runtime(self) -> None:
        assert _live_runtime_binding(None) == (None, None)
        assert _live_runtime_binding("bad") == (None, None)
        assert _live_runtime_binding(42) == (None, None)
        assert _live_runtime_binding([1]) == (None, None)

    def test_empty_env_dict(self) -> None:
        runtime: dict[str, Any] = {"env": {}}
        db, user = _live_runtime_binding(runtime)
        assert db is None
        assert user is None

    def test_empty_string_values_ignored(self) -> None:
        runtime: dict[str, Any] = {
            "env": {"DATABASE_DBNAME": "", "PGUSER": ""},
            "database": "",
            "user": "",
        }
        db, user = _live_runtime_binding(runtime)
        assert db is None
        assert user is None

    def test_env_non_dict_ignored(self) -> None:
        runtime: dict[str, Any] = {"env": "not-a-dict"}
        db, user = _live_runtime_binding(runtime)
        assert db is None
        assert user is None

    def test_priority_env_over_dsn(self) -> None:
        runtime: dict[str, Any] = {
            "env": {
                "DATABASE_DBNAME": "priority_db",
                "PGUSER": "priority_user",
                "DATABASE_URL": "postgres://dsnuser:pw@h/lowpriodb",
            },
        }
        db, user = _live_runtime_binding(runtime)
        assert db == "priority_db"
        assert user == "priority_user"


# ---------------------------------------------------------------------------
# _prod0_app_resource_live_audit_snapshot
# ---------------------------------------------------------------------------


class TestProd0AppResourceLiveAuditSnapshot:
    @patch("agentplane.domain.infra.postgres_audit.execute_remote_bash")
    def test_success(self, mock_exec: MagicMock, tmp_path: Path) -> None:
        payload = {"databases": [{"name": "appdb"}]}
        mock_exec.return_value = {
            "result": {"returncode": 0, "stdout": json.dumps(payload)},
        }
        result = _prod0_app_resource_live_audit_snapshot(tmp_path)
        assert result == payload
        mock_exec.assert_called_once()

    @patch("agentplane.domain.infra.postgres_audit.execute_remote_bash")
    def test_nonzero_returncode(self, mock_exec: MagicMock, tmp_path: Path) -> None:
        mock_exec.return_value = {
            "result": {"returncode": 1, "stdout": "error"},
        }
        with pytest.raises(RuntimeError):
            _prod0_app_resource_live_audit_snapshot(tmp_path)

    @patch("agentplane.domain.infra.postgres_audit.execute_remote_bash")
    def test_non_json_stdout(self, mock_exec: MagicMock, tmp_path: Path) -> None:
        mock_exec.return_value = {
            "result": {"returncode": 0, "stdout": "not json"},
        }
        with pytest.raises(ValueError, match="JSON object"):
            _prod0_app_resource_live_audit_snapshot(tmp_path)

    @patch("agentplane.domain.infra.postgres_audit.execute_remote_bash")
    def test_stdout_json_array_not_dict(self, mock_exec: MagicMock, tmp_path: Path) -> None:
        mock_exec.return_value = {
            "result": {"returncode": 0, "stdout": "[1, 2]"},
        }
        with pytest.raises(ValueError, match="JSON object"):
            _prod0_app_resource_live_audit_snapshot(tmp_path)

    @patch("agentplane.domain.infra.postgres_audit.execute_remote_bash")
    def test_value_error_from_remote(self, mock_exec: MagicMock, tmp_path: Path) -> None:
        mock_exec.side_effect = ValueError("bad config")
        with pytest.raises(RuntimeError, match="bad config"):
            _prod0_app_resource_live_audit_snapshot(tmp_path)

    @patch("agentplane.domain.infra.postgres_audit.execute_remote_bash")
    def test_os_error_from_remote(self, mock_exec: MagicMock, tmp_path: Path) -> None:
        mock_exec.side_effect = OSError("connection refused")
        with pytest.raises(RuntimeError, match="connection refused"):
            _prod0_app_resource_live_audit_snapshot(tmp_path)

    @patch("agentplane.domain.infra.postgres_audit.execute_remote_bash")
    def test_empty_json_object(self, mock_exec: MagicMock, tmp_path: Path) -> None:
        mock_exec.return_value = {
            "result": {"returncode": 0, "stdout": "{}"},
        }
        result = _prod0_app_resource_live_audit_snapshot(tmp_path)
        assert result == {}

    @patch("agentplane.domain.infra.postgres_audit.execute_remote_bash")
    def test_script_path_construction(self, mock_exec: MagicMock, tmp_path: Path) -> None:
        mock_exec.return_value = {
            "result": {"returncode": 0, "stdout": '{"ok": true}'},
        }
        _prod0_app_resource_live_audit_snapshot(tmp_path)
        call_kwargs = mock_exec.call_args
        assert call_kwargs.kwargs["target"] == "prod0-main"
        script = call_kwargs.kwargs["script_file"]
        assert script.name == "prod0-postgres-app-resource-live-audit.sh"
