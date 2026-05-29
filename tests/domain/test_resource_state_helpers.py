"""Tests for agentplane.domain.app.resource_state — pure helper functions."""

from __future__ import annotations

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
        result = parse_env_text("KEY=value\nOTHER=123")
        assert result == {"KEY": "value", "OTHER": "123"}

    def test_comments_skipped(self) -> None:
        result = parse_env_text("# comment\nKEY=value")
        assert result == {"KEY": "value"}

    def test_empty_lines_skipped(self) -> None:
        result = parse_env_text("\n\nKEY=value\n")
        assert result == {"KEY": "value"}

    def test_value_with_equals(self) -> None:
        result = parse_env_text("URL=http://host?q=1")
        assert result == {"URL": "http://host?q=1"}

    def test_empty_key_skipped(self) -> None:
        result = parse_env_text("=value")
        assert result == {}

    def test_whitespace_trimmed(self) -> None:
        result = parse_env_text("  KEY  =  value  ")
        assert result == {"KEY": "value"}

    def test_no_equals_skipped(self) -> None:
        result = parse_env_text("NOEQUALS")
        assert result == {}


# ---------------------------------------------------------------------------
# build_app_resource_summary
# ---------------------------------------------------------------------------


class TestBuildAppResourceSummary:
    def test_none_input(self) -> None:
        assert build_app_resource_summary(None) == {}

    def test_non_dict_input(self) -> None:
        assert build_app_resource_summary("not a dict") == {}

    def test_postgres_only(self) -> None:
        resources = {"postgres": {"database": "mydb", "user": "myuser", "secret_file": "pg.env"}}
        result = build_app_resource_summary(resources)
        assert result["postgres"]["database"] == "mydb"
        assert result["postgres"]["user"] == "myuser"
        assert result["postgres"]["secret_file"] == "pg.env"

    def test_redis_strips_user(self) -> None:
        resources = {"redis": {"db": 1, "key_prefix": "app:", "user": "default"}}
        result = build_app_resource_summary(resources)
        assert "user" not in result["redis"]
        assert result["redis"]["db"] == 1

    def test_minio(self) -> None:
        resources = {"minio": {"bucket": "mybucket", "access_key": "ak"}}
        result = build_app_resource_summary(resources)
        assert result["minio"]["bucket"] == "mybucket"

    def test_empty_values_skipped(self) -> None:
        resources = {"postgres": {"database": "", "user": None}}
        result = build_app_resource_summary(resources)
        assert "postgres" not in result

    def test_secret_file_empty_skipped(self) -> None:
        resources = {"postgres": {"database": "db", "secret_file": "  "}}
        result = build_app_resource_summary(resources)
        assert "secret_file" not in result["postgres"]


# ---------------------------------------------------------------------------
# registry_secret_file
# ---------------------------------------------------------------------------


class TestRegistrySecretFile:
    def test_direct_secret_file(self) -> None:
        entry = {"postgres": {"secret_file": "secrets/pg.env"}}
        assert registry_secret_file(entry, "postgres") == "secrets/pg.env"

    def test_secret_files_list_match(self) -> None:
        entry = {"secret_files": ["secrets/postgres.env", "secrets/redis.env"]}
        assert registry_secret_file(entry, "postgres") == "secrets/postgres.env"

    def test_secret_files_list_redis(self) -> None:
        entry = {"secret_files": ["secrets/postgres.env", "secrets/redis.env"]}
        assert registry_secret_file(entry, "redis") == "secrets/redis.env"

    def test_no_match(self) -> None:
        entry = {"secret_files": ["secrets/other.env"]}
        assert registry_secret_file(entry, "postgres") is None

    def test_no_entry(self) -> None:
        assert registry_secret_file({}, "postgres") is None

    def test_non_string_in_list(self) -> None:
        entry = {"secret_files": [123, "secrets/redis.env"]}
        assert registry_secret_file(entry, "redis") == "secrets/redis.env"


# ---------------------------------------------------------------------------
# normalize_key_prefix
# ---------------------------------------------------------------------------


class TestNormalizeKeyPrefix:
    def test_none(self) -> None:
        assert normalize_key_prefix(None) is None

    def test_empty(self) -> None:
        assert normalize_key_prefix("") is None

    def test_already_has_colon(self) -> None:
        assert normalize_key_prefix("app:") == "app:"

    def test_adds_colon(self) -> None:
        assert normalize_key_prefix("app") == "app:"

    def test_whitespace_trimmed(self) -> None:
        assert normalize_key_prefix("  app  ") == "app:"


# ---------------------------------------------------------------------------
# is_canonical_redis_db
# ---------------------------------------------------------------------------


class TestIsCanonicalRedisDb:
    def test_valid_int(self) -> None:
        assert is_canonical_redis_db(1) is True
        assert is_canonical_redis_db(0) is True
        assert is_canonical_redis_db(15) is True

    def test_bool_rejected(self) -> None:
        assert is_canonical_redis_db(True) is False
        assert is_canonical_redis_db(False) is False

    def test_non_int(self) -> None:
        assert is_canonical_redis_db("1") is False
        assert is_canonical_redis_db(None) is False


# ---------------------------------------------------------------------------
# Golden test
# ---------------------------------------------------------------------------


@pytest.mark.golden
class TestResourceStateGolden:
    def test_full_resource_summary_roundtrip(self) -> None:
        """Parse env → build summary → verify fields."""
        env = parse_env_text("REDIS_HOST=127.0.0.1\nREDIS_PORT=6379\nREDIS_DB=1")
        assert env["REDIS_DB"] == "1"

        resources = {
            "postgres": {"database": "mydb", "user": "myuser"},
            "redis": {"db": 1, "key_prefix": "app:"},
            "minio": {"bucket": "b", "access_key": "ak", "policy_name": "rw"},
        }
        summary = build_app_resource_summary(resources)
        assert "postgres" in summary
        assert "redis" in summary
        assert "minio" in summary
        assert normalize_key_prefix(summary["redis"]["key_prefix"]) == "app:"
        assert is_canonical_redis_db(summary["redis"]["db"]) is True
