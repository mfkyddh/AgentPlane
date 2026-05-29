"""Tests for agentplane.runtime.redaction — pure redaction functions."""

from __future__ import annotations

import pytest
from agentplane.runtime.redaction import (
    is_sensitive_key,
    redact_env_text,
    redact_execution_payload,
    redact_output_text,
    redact_sensitive_value,
    scrub_persisted_payload,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# is_sensitive_key
# ---------------------------------------------------------------------------


class TestIsSensitiveKey:
    def test_password(self) -> None:
        assert is_sensitive_key("DB_PASSWORD") is True

    def test_token(self) -> None:
        assert is_sensitive_key("API_TOKEN") is True

    def test_secret(self) -> None:
        assert is_sensitive_key("JWT_SECRET") is True

    def test_key(self) -> None:
        assert is_sensitive_key("ENCRYPTION_KEY") is True

    def test_dsn(self) -> None:
        assert is_sensitive_key("DATABASE_DSN") is True

    def test_database_url(self) -> None:
        assert is_sensitive_key("DATABASE_URL") is True

    def test_redis_url(self) -> None:
        assert is_sensitive_key("REDIS_URL") is True

    def test_access(self) -> None:
        assert is_sensitive_key("ACCESS_KEY") is True

    def test_private(self) -> None:
        assert is_sensitive_key("PRIVATE_KEY") is True

    def test_passwd(self) -> None:
        assert is_sensitive_key("ROOT_PASSWD") is True

    def test_case_insensitive(self) -> None:
        assert is_sensitive_key("db_password") is True
        assert is_sensitive_key("Api_Token") is True

    def test_not_sensitive(self) -> None:
        assert is_sensitive_key("HOST") is False
        assert is_sensitive_key("PORT") is False
        assert is_sensitive_key("APP_NAME") is False

    def test_empty_string(self) -> None:
        assert is_sensitive_key("") is False


# ---------------------------------------------------------------------------
# redact_env_text
# ---------------------------------------------------------------------------


class TestRedactEnvText:
    def test_redacts_password_line(self) -> None:
        text = "DB_HOST=localhost\nDB_PASSWORD=secret123\n"
        result = redact_env_text(text)
        assert "DB_HOST=localhost" in result
        assert "secret123" not in result
        assert "DB_PASSWORD=<redacted>" in result

    def test_preserves_non_sensitive(self) -> None:
        text = "APP_NAME=myapp\nPORT=8080"
        result = redact_env_text(text)
        assert result == text

    def test_preserves_comments(self) -> None:
        text = "# This is a comment\nDB_HOST=localhost"
        result = redact_env_text(text)
        assert "# This is a comment" in result

    def test_preserves_empty_lines(self) -> None:
        text = "\nDB_HOST=localhost\n"
        result = redact_env_text(text)
        assert result.startswith("\n")

    def test_preserves_trailing_newline(self) -> None:
        text = "DB_PASSWORD=secret\n"
        result = redact_env_text(text)
        assert result.endswith("\n")

    def test_no_trailing_newline(self) -> None:
        text = "DB_PASSWORD=secret"
        result = redact_env_text(text)
        assert not result.endswith("\n")

    def test_value_with_equals(self) -> None:
        text = "DATABASE_URL=postgres://user:pass@host/db?opt=val"
        result = redact_env_text(text)
        assert "DATABASE_URL=<redacted>" in result
        assert "pass@host" not in result

    def test_no_equals_sign(self) -> None:
        text = "just some text without equals"
        result = redact_env_text(text)
        assert result == text


# ---------------------------------------------------------------------------
# redact_output_text
# ---------------------------------------------------------------------------


class TestRedactOutputText:
    def test_empty_string(self) -> None:
        assert redact_output_text("") == ""

    def test_env_format(self) -> None:
        text = "DB_PASSWORD=secret\nHOST=localhost"
        result = redact_output_text(text)
        assert "DB_PASSWORD=<redacted>" in result
        assert "HOST=localhost" in result

    def test_json_with_sensitive_key(self) -> None:
        text = '{"token": "abc123", "name": "test"}'
        result = redact_output_text(text)
        assert "abc123" not in result
        assert "test" in result

    def test_json_without_sensitive_keys(self) -> None:
        text = '{"name": "test", "port": 8080}'
        result = redact_output_text(text)
        # No sensitive keys, should return original
        assert result == text

    def test_json_array(self) -> None:
        text = '[{"password": "secret"}]'
        result = redact_output_text(text)
        assert "secret" not in result

    def test_invalid_json_falls_back_to_env(self) -> None:
        text = '{"DB_PASSWORD=secret"'
        result = redact_output_text(text)
        assert "secret" not in result or "<redacted>" in result

    def test_non_json_non_env_text(self) -> None:
        text = "some plain log output"
        result = redact_output_text(text)
        assert result == text


# ---------------------------------------------------------------------------
# redact_sensitive_value
# ---------------------------------------------------------------------------


class TestRedactSensitiveValue:
    def test_string_with_sensitive_key(self) -> None:
        result = redact_sensitive_value({"DB_PASSWORD": "secret", "HOST": "localhost"})
        assert result["DB_PASSWORD"] == "<redacted>"
        assert result["HOST"] == "localhost"

    def test_nested_dict(self) -> None:
        result = redact_sensitive_value({"config": {"API_TOKEN": "tok123"}})
        assert result["config"]["API_TOKEN"] == "<redacted>"

    def test_list(self) -> None:
        result = redact_sensitive_value([{"TOKEN": "abc"}, {"NAME": "test"}])
        assert result[0]["TOKEN"] == "<redacted>"
        assert result[1]["NAME"] == "test"

    def test_plain_string(self) -> None:
        result = redact_sensitive_value("DB_PASSWORD=secret")
        assert "<redacted>" in result

    def test_non_sensitive_string(self) -> None:
        result = redact_sensitive_value("just plain text")
        assert result == "just plain text"

    def test_number_passthrough(self) -> None:
        assert redact_sensitive_value(42) == 42

    def test_none_passthrough(self) -> None:
        assert redact_sensitive_value(None) is None

    def test_bool_passthrough(self) -> None:
        assert redact_sensitive_value(True) is True


# ---------------------------------------------------------------------------
# redact_execution_payload
# ---------------------------------------------------------------------------


class TestRedactExecutionPayload:
    def test_redacts_stdout(self) -> None:
        payload = {"stdout": "DB_PASSWORD=secret\nok", "stderr": "", "ok": True}
        result = redact_execution_payload(payload)
        assert "secret" not in result["stdout"]
        assert "<redacted>" in result["stdout"]
        assert result["ok"] is True

    def test_redacts_stderr(self) -> None:
        payload = {"stdout": "", "stderr": "TOKEN=abc123", "ok": False}
        result = redact_execution_payload(payload)
        assert "abc123" not in result["stderr"]

    def test_non_string_stdout_skipped(self) -> None:
        payload = {"stdout": None, "stderr": None, "ok": True}
        result = redact_execution_payload(payload)
        assert result["stdout"] is None

    def test_preserves_other_keys(self) -> None:
        payload = {"stdout": "ok", "stderr": "", "returncode": 0}
        result = redact_execution_payload(payload)
        assert result["returncode"] == 0

    def test_empty_payload(self) -> None:
        result = redact_execution_payload({})
        assert result == {}


# ---------------------------------------------------------------------------
# scrub_persisted_payload
# ---------------------------------------------------------------------------


class TestScrubPersistedPayload:
    def test_scrubs_sensitive_keys(self) -> None:
        data = {"DB_PASSWORD": "secret", "HOST": "localhost"}
        result = scrub_persisted_payload(data)
        assert result["DB_PASSWORD"] == "[REDACTED]"
        assert result["HOST"] == "localhost"

    def test_nested_dict(self) -> None:
        data = {"config": {"API_TOKEN": "tok", "name": "app"}}
        result = scrub_persisted_payload(data)
        assert result["config"]["API_TOKEN"] == "[REDACTED]"
        assert result["config"]["name"] == "app"

    def test_list(self) -> None:
        data = [{"SECRET": "s1"}, {"NAME": "n1"}]
        result = scrub_persisted_payload(data)
        assert result[0]["SECRET"] == "[REDACTED]"
        assert result[1]["NAME"] == "n1"

    def test_non_dict_non_list(self) -> None:
        assert scrub_persisted_payload("text") == "text"
        assert scrub_persisted_payload(42) == 42
        assert scrub_persisted_payload(None) is None


# ---------------------------------------------------------------------------
# Golden test
# ---------------------------------------------------------------------------


@pytest.mark.golden
class TestRedactionGolden:
    def test_full_redaction_roundtrip(self) -> None:
        """End-to-end: env text → output text → execution payload → persisted scrub."""
        env_text = "DB_HOST=localhost\nDB_PASSWORD=supersecret\nAPI_TOKEN=tok123\nAPP_NAME=myapp"
        redacted_env = redact_env_text(env_text)
        assert "supersecret" not in redacted_env
        assert "tok123" not in redacted_env
        assert "APP_NAME=myapp" in redacted_env

        payload = {"stdout": redacted_env, "stderr": "", "ok": True}
        exec_result = redact_execution_payload(payload)
        assert "supersecret" not in exec_result["stdout"]

        persisted = scrub_persisted_payload({
            "deployment": {"DB_PASSWORD": "secret", "HOST": "localhost"},
            "results": [{"TOKEN": "abc"}],
        })
        assert persisted["deployment"]["DB_PASSWORD"] == "[REDACTED]"
        assert persisted["deployment"]["HOST"] == "localhost"
        assert persisted["results"][0]["TOKEN"] == "[REDACTED]"
