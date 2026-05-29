"""Tests for agentplane.domain.app.projection.runtime_env — pure helper functions."""

from __future__ import annotations

from pathlib import Path

import pytest
from agentplane.domain.app.projection.runtime_env import (
    _format_env_text,
    _merge_sub2api_env,
    _public_projection_payload,
    _redact_drift_payload,
    _render_env_formal_required_kinds,
    formal_prod0_required_kinds,
    formal_registry_entry_errors,
    service_env_file,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# service_env_file
# ---------------------------------------------------------------------------


class TestServiceEnvFile:
    def test_wsl_target(self, tmp_path: Path) -> None:
        result = service_env_file(tmp_path, "wsl", "myapp")
        assert result.name == "myapp.wsl.env"
        assert "services" in result.parts

    def test_prod0_target(self, tmp_path: Path) -> None:
        result = service_env_file(tmp_path, "prod0-main", "myapp")
        assert result.name == "myapp.prod0.env"
        assert "services" in result.parts

    def test_unsupported_target(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="Unsupported target"):
            service_env_file(tmp_path, "staging", "myapp")


# ---------------------------------------------------------------------------
# _merge_sub2api_env
# ---------------------------------------------------------------------------


class TestMergeSub2apiEnv:
    def test_basic_merge(self) -> None:
        current = {"APP_PORT": "8080", "OTHER": "val"}
        pg = {"PGHOST": "localhost", "PGPORT": "5432", "PGUSER": "u", "PGPASSWORD": "p", "PGDATABASE": "db", "PGSSLMODE": "disable"}
        redis = {"REDIS_HOST": "rhost", "REDIS_PORT": "6379", "REDIS_PASSWORD": "rpw", "REDIS_DB": "0", "REDIS_ENABLE_TLS": "false"}
        merged, managed = _merge_sub2api_env(current, pg, redis)
        assert merged["DATABASE_HOST"] == "localhost"
        assert merged["DATABASE_PORT"] == "5432"
        assert merged["APP_PORT"] == "8080"
        assert "DATABASE_HOST" in managed
        assert "REDIS_HOST" in managed

    def test_strips_red_user_and_key_prefix(self) -> None:
        current = {"REDIS_USER": "should_go", "REDIS_KEY_PREFIX": "also_go", "KEEP": "yes"}
        pg: dict[str, str] = {}
        redis: dict[str, str] = {}
        merged, _ = _merge_sub2api_env(current, pg, redis)
        assert "REDIS_USER" not in merged
        assert "REDIS_KEY_PREFIX" not in merged
        assert "KEEP" in merged

    def test_empty_values_not_overridden(self) -> None:
        current = {"DATABASE_HOST": "existing"}
        pg = {"PGHOST": ""}  # empty string should NOT override
        redis: dict[str, str] = {}
        merged, _ = _merge_sub2api_env(current, pg, redis)
        assert merged["DATABASE_HOST"] == "existing"

    def test_nonempty_pg_overrides(self) -> None:
        current = {"DATABASE_HOST": "old"}
        pg = {"PGHOST": "new-host", "PGPORT": "5432", "PGUSER": "u", "PGPASSWORD": "p", "PGDATABASE": "db", "PGSSLMODE": "disable"}
        redis: dict[str, str] = {}
        merged, _ = _merge_sub2api_env(current, pg, redis)
        assert merged["DATABASE_HOST"] == "new-host"


# ---------------------------------------------------------------------------
# _format_env_text
# ---------------------------------------------------------------------------


class TestFormatEnvText:
    def test_preferred_order(self) -> None:
        values = {"Z": "1", "A": "2", "M": "3"}
        result = _format_env_text(values, ["M", "A", "Z"])
        lines = result.strip().split("\n")
        assert lines[0] == "M=3"
        assert lines[1] == "A=2"
        assert lines[2] == "Z=1"

    def test_unpreferred_sorted(self) -> None:
        values = {"B": "1", "A": "2"}
        result = _format_env_text(values, [])
        lines = result.strip().split("\n")
        assert lines[0] == "A=2"
        assert lines[1] == "B=1"

    def test_trailing_newline(self) -> None:
        result = _format_env_text({"K": "V"}, [])
        assert result.endswith("\n")

    def test_empty(self) -> None:
        result = _format_env_text({}, [])
        assert result == "\n"

    def test_preferred_skips_missing_keys(self) -> None:
        values = {"A": "1"}
        result = _format_env_text(values, ["MISSING", "A"])
        assert result == "A=1\n"


# ---------------------------------------------------------------------------
# formal_prod0_required_kinds
# ---------------------------------------------------------------------------


class TestFormalProd0RequiredKinds:
    def test_sub2api(self) -> None:
        result = formal_prod0_required_kinds("sub2api")
        assert "postgres" in result
        assert "redis" in result
        assert "minio" in result

    def test_unknown_app(self) -> None:
        assert formal_prod0_required_kinds("unknown-app") == ()


# ---------------------------------------------------------------------------
# _render_env_formal_required_kinds
# ---------------------------------------------------------------------------


class TestRenderEnvFormalRequiredKinds:
    def test_filters_to_postgres_redis(self) -> None:
        result = _render_env_formal_required_kinds("sub2api")
        assert "postgres" in result
        assert "redis" in result
        assert "minio" not in result

    def test_unknown_app_empty(self) -> None:
        assert _render_env_formal_required_kinds("unknown") == ()


# ---------------------------------------------------------------------------
# formal_registry_entry_errors
# ---------------------------------------------------------------------------


class TestFormalRegistryEntryErrors:
    def test_non_prod0_returns_empty(self) -> None:
        assert formal_registry_entry_errors("wsl", "sub2api", {}) == []

    def test_unknown_app_returns_empty(self) -> None:
        assert formal_registry_entry_errors("prod0-main", "unknown", {}) == []

    def test_non_dict_entry(self) -> None:
        errors = formal_registry_entry_errors("prod0-main", "sub2api", "bad")
        assert len(errors) == 1
        assert "missing registry entry" in errors[0]["issues"][0]

    def test_wrong_owner_app(self) -> None:
        entry = {
            "owner_app": "wrong",
            "postgres": {"database": "db", "user": "u", "secret_file": "secrets/hosts/prod0-main/apps/sub2api/resources/postgres.env"},
            "redis": {"db": 1, "key_prefix": "sub2api:", "secret_file": "secrets/hosts/prod0-main/apps/sub2api/resources/redis.env"},
            "minio": {"bucket": "b", "access_key": "k", "policy_name": "p", "policy_scope": "s", "isolation_level": "l", "secret_file": "secrets/hosts/prod0-main/apps/sub2api/resources/minio.env"},
        }
        errors = formal_registry_entry_errors("prod0-main", "sub2api", entry)
        assert any("owner_app" in i for i in errors[0]["issues"])

    def test_missing_kind_spec(self) -> None:
        entry = {"owner_app": "sub2api"}
        errors = formal_registry_entry_errors("prod0-main", "sub2api", entry, required_kinds=("postgres",))
        assert any("missing postgres specification" in i for i in errors[0]["issues"])

    def test_valid_entry(self) -> None:
        entry = {
            "owner_app": "sub2api",
            "postgres": {"database": "db", "user": "u", "secret_file": "secrets/hosts/prod0-main/apps/sub2api/resources/postgres.env"},
            "redis": {"db": 1, "key_prefix": "sub2api:", "secret_file": "secrets/hosts/prod0-main/apps/sub2api/resources/redis.env"},
        }
        errors = formal_registry_entry_errors("prod0-main", "sub2api", entry, required_kinds=("postgres", "redis"))
        assert errors == []


# ---------------------------------------------------------------------------
# _redact_drift_payload
# ---------------------------------------------------------------------------


class TestRedactDriftPayload:
    def test_redacts_strings(self) -> None:
        drift = {"expected": "KEY=secret", "actual": "KEY=different", "other": "keep"}
        result = _redact_drift_payload(drift)
        assert "expected_redacted" in result
        assert "actual_redacted" in result
        assert result["other"] == "keep"
        assert "expected" not in result
        assert "actual" not in result

    def test_non_string_values(self) -> None:
        drift: dict[str, object] = {"expected": 42, "actual": None}
        result = _redact_drift_payload(drift)
        assert "expected_redacted" not in result
        assert "actual_redacted" not in result


# ---------------------------------------------------------------------------
# _public_projection_payload
# ---------------------------------------------------------------------------


class TestPublicProjectionPayload:
    def test_hides_secrets_by_default(self) -> None:
        payload = {"ok": True, "current_env": "SECRET", "rendered_env": "SECRET", "env_exists": True}
        result = _public_projection_payload(payload)
        assert "current_env" not in result
        assert "rendered_env" not in result
        assert "env_exists" not in result

    def test_reveals_secrets_when_asked(self) -> None:
        payload = {"ok": True, "current_env": "SECRET", "rendered_env": "SECRET", "env_exists": True}
        result = _public_projection_payload(payload, reveal_secrets=True)
        assert result["current_env"] == "SECRET"
        assert result["rendered_env"] == "SECRET"

    def test_redacts_drift(self) -> None:
        payload = {"ok": False, "drift": {"expected": "a", "actual": "b", "keys": ["k"]}}
        result = _public_projection_payload(payload)
        assert "expected_redacted" in result["drift"]
        assert "actual_redacted" in result["drift"]
        assert result["drift"]["keys"] == ["k"]


# ---------------------------------------------------------------------------
# Golden test
# ---------------------------------------------------------------------------


@pytest.mark.golden
class TestRuntimeEnvGolden:
    def test_full_format_roundtrip(self) -> None:
        """Format env text with preferred order and sorted tail."""
        values = {"DATABASE_HOST": "db.local", "REDIS_HOST": "redis.local", "APP_PORT": "8080", "LOG_LEVEL": "info"}
        result = _format_env_text(values, ["DATABASE_HOST", "REDIS_HOST"])
        lines = result.strip().split("\n")
        assert lines[0] == "DATABASE_HOST=db.local"
        assert lines[1] == "REDIS_HOST=redis.local"
        # Remaining sorted
        assert "APP_PORT=8080" in lines[2:]
        assert "LOG_LEVEL=info" in lines[2:]

    def test_registry_entry_errors_roundtrip(self) -> None:
        """Full entry with wrong redis db produces specific error."""
        entry = {
            "owner_app": "sub2api",
            "postgres": {"database": "db", "user": "u", "secret_file": "secrets/hosts/prod0-main/apps/sub2api/resources/postgres.env"},
            "redis": {"db": 99, "key_prefix": "sub2api:", "secret_file": "secrets/hosts/prod0-main/apps/sub2api/resources/redis.env"},
        }
        errors = formal_registry_entry_errors("prod0-main", "sub2api", entry, required_kinds=("postgres", "redis"))
        assert len(errors) == 1
        assert any("redis.db" in i for i in errors[0]["issues"])
