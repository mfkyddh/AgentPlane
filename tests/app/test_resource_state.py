"""Tests for agentplane.domain.app.resource_state — pure helper functions."""

from __future__ import annotations

from typing import Any

import pytest
from agentplane.domain.app.resource_state import (
    build_app_resource_summary,
    is_canonical_redis_db,
    normalize_key_prefix,
    parse_env_text,
    registry_secret_file,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# parse_env_text
# ---------------------------------------------------------------------------


class TestParseEnvText:
    def test_basic(self) -> None:
        text = "KEY=value\nOTHER=stuff\n"
        result = parse_env_text(text)
        assert result == {"KEY": "value", "OTHER": "stuff"}

    def test_comments_skipped(self) -> None:
        text = "# comment\nKEY=value\n"
        result = parse_env_text(text)
        assert result == {"KEY": "value"}

    def test_empty_lines_skipped(self) -> None:
        text = "\n\nKEY=value\n\n"
        result = parse_env_text(text)
        assert result == {"KEY": "value"}

    def test_no_equals_skipped(self) -> None:
        text = "INVALID_LINE\nKEY=value\n"
        result = parse_env_text(text)
        assert result == {"KEY": "value"}

    def test_empty_key_skipped(self) -> None:
        text = "=value\nKEY=val\n"
        result = parse_env_text(text)
        assert result == {"KEY": "val"}

    def test_value_with_equals(self) -> None:
        text = "URL=http://host?key=val\n"
        result = parse_env_text(text)
        assert result["URL"] == "http://host?key=val"

    def test_whitespace_trimmed(self) -> None:
        text = "  KEY  =  value  \n"
        result = parse_env_text(text)
        assert result["KEY"] == "value"

    def test_empty(self) -> None:
        assert parse_env_text("") == {}


# ---------------------------------------------------------------------------
# build_app_resource_summary
# ---------------------------------------------------------------------------


class TestBuildAppResourceSummary:
    def test_postgres(self) -> None:
        resources: dict[str, Any] = {"postgres": {"database": "mydb", "user": "myuser"}}
        result = build_app_resource_summary(resources)
        assert result["postgres"]["database"] == "mydb"
        assert result["postgres"]["user"] == "myuser"

    def test_redis(self) -> None:
        resources: dict[str, Any] = {"redis": {"db": 1, "key_prefix": "app:"}}
        result = build_app_resource_summary(resources)
        assert result["redis"]["db"] == 1
        assert result["redis"]["key_prefix"] == "app:"

    def test_minio(self) -> None:
        resources: dict[str, Any] = {"minio": {"bucket": "b", "access_key": "k", "policy_name": "p", "policy_scope": "s", "isolation_level": "l"}}
        result = build_app_resource_summary(resources)
        assert result["minio"]["bucket"] == "b"

    def test_secret_file_included(self) -> None:
        resources: dict[str, Any] = {"postgres": {"database": "db", "secret_file": "path/to/secret"}}
        result = build_app_resource_summary(resources)
        assert result["postgres"]["secret_file"] == "path/to/secret"

    def test_empty_values_skipped(self) -> None:
        resources: dict[str, Any] = {"postgres": {"database": "", "user": None}}
        result = build_app_resource_summary(resources)
        assert "postgres" not in result

    def test_non_dict_resource(self) -> None:
        resources: dict[str, Any] = {"postgres": "invalid"}
        result = build_app_resource_summary(resources)
        assert "postgres" not in result

    def test_non_dict_input(self) -> None:
        assert build_app_resource_summary("invalid") == {}


# ---------------------------------------------------------------------------
# registry_secret_file
# ---------------------------------------------------------------------------


class TestRegistrySecretFile:
    def test_direct_secret_file(self) -> None:
        entry: dict[str, Any] = {"postgres": {"secret_file": "path/to/pg.env"}}
        assert registry_secret_file(entry, "postgres") == "path/to/pg.env"

    def test_secret_files_list(self) -> None:
        entry: dict[str, Any] = {"secret_files": ["path/to/postgres.env", "path/to/redis.env"]}
        assert registry_secret_file(entry, "postgres") == "path/to/postgres.env"

    def test_no_secret(self) -> None:
        entry: dict[str, Any] = {}
        assert registry_secret_file(entry, "postgres") is None

    def test_empty_direct(self) -> None:
        entry: dict[str, Any] = {"postgres": {"secret_file": ""}}
        assert registry_secret_file(entry, "postgres") is None

    def test_non_dict_resource(self) -> None:
        entry: dict[str, Any] = {"postgres": "invalid"}
        assert registry_secret_file(entry, "postgres") is None


# ---------------------------------------------------------------------------
# normalize_key_prefix
# ---------------------------------------------------------------------------


class TestNormalizeKeyPrefix:
    def test_adds_colon(self) -> None:
        assert normalize_key_prefix("myapp") == "myapp:"

    def test_already_has_colon(self) -> None:
        assert normalize_key_prefix("myapp:") == "myapp:"

    def test_none(self) -> None:
        assert normalize_key_prefix(None) is None

    def test_empty(self) -> None:
        assert normalize_key_prefix("") is None

    def test_whitespace(self) -> None:
        assert normalize_key_prefix("  ") is None

    def test_int_value(self) -> None:
        assert normalize_key_prefix(42) == "42:"


# ---------------------------------------------------------------------------
# is_canonical_redis_db
# ---------------------------------------------------------------------------


class TestIsCanonicalRedisDb:
    def test_int(self) -> None:
        assert is_canonical_redis_db(1) is True

    def test_zero(self) -> None:
        assert is_canonical_redis_db(0) is True

    def test_bool_rejected(self) -> None:
        assert is_canonical_redis_db(True) is False
        assert is_canonical_redis_db(False) is False

    def test_string(self) -> None:
        assert is_canonical_redis_db("1") is False

    def test_none(self) -> None:
        assert is_canonical_redis_db(None) is False


# ---------------------------------------------------------------------------
# Golden test
# ---------------------------------------------------------------------------


@pytest.mark.golden
class TestResourceStateGolden:
    def test_full_env_parse_roundtrip(self) -> None:
        """Full env text with all field types parses correctly."""
        text = """# Database config
DATABASE_HOST=db.local
DATABASE_PORT=5432
DATABASE_NAME=mydb

# Redis config
REDIS_HOST=redis.local
REDIS_PORT=6379
REDIS_PASSWORD=secret
REDIS_DB=1
REDIS_KEY_PREFIX=myapp:
REDIS_ENABLE_TLS=false
"""
        result = parse_env_text(text)
        assert result["DATABASE_HOST"] == "db.local"
        assert result["REDIS_DB"] == "1"
        assert normalize_key_prefix(result["REDIS_KEY_PREFIX"]) == "myapp:"
        assert is_canonical_redis_db(1) is True

    def test_resource_summary_roundtrip(self) -> None:
        """Full resource spec produces correct summary."""
        resources: dict[str, Any] = {
            "postgres": {"database": "sub2api", "user": "sub2api_user", "secret_file": "secrets/pg.env"},
            "redis": {"db": 1, "key_prefix": "sub2api:", "secret_file": "secrets/redis.env"},
            "minio": {"bucket": "sub2api", "access_key": "key", "policy_name": "rw", "policy_scope": "bucket", "isolation_level": "strict"},
        }
        summary = build_app_resource_summary(resources)
        assert len(summary) == 3
        assert summary["postgres"]["database"] == "sub2api"
        assert summary["redis"]["db"] == 1
        assert summary["minio"]["bucket"] == "sub2api"
