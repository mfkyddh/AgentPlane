"""Tests for agentplane.domain.app.resource_handlers — pure helper functions."""

from __future__ import annotations

from typing import Any

import pytest
from agentplane.domain.app.resource_handlers import (
    _declared_payload,
    _expected_app_resource_summary,
    _summary,
)
from agentplane.domain.app.resource_models import AppResourceDefinition

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# _summary
# ---------------------------------------------------------------------------


class TestSummary:
    def test_basic(self) -> None:
        definition = AppResourceDefinition(app="myapp", owner_app="myapp", resource_kinds=("postgres", "redis"))
        result = _summary(definition)
        assert result["app"] == "myapp"
        assert result["owner_app"] == "myapp"
        assert "postgres" in result["resource_kinds"]
        assert "redis" in result["resource_kinds"]

    def test_empty_kinds(self) -> None:
        definition = AppResourceDefinition(app="myapp", owner_app="myapp", resource_kinds=())
        result = _summary(definition)
        assert result["resource_kinds"] == []


# ---------------------------------------------------------------------------
# _declared_payload
# ---------------------------------------------------------------------------


class TestDeclaredPayload:
    def test_filters_known_keys(self) -> None:
        raw: dict[str, Any] = {
            "owner_app": "myapp",
            "ledger_status": {"status": "ok"},
            "postgres": {"database": "db"},
            "redis": {"db": 1},
            "unknown_key": "ignored",
        }
        result = _declared_payload(raw)
        assert result["owner_app"] == "myapp"
        assert "postgres" in result
        assert "unknown_key" not in result

    def test_empty(self) -> None:
        assert _declared_payload({}) == {}


# ---------------------------------------------------------------------------
# _expected_app_resource_summary
# ---------------------------------------------------------------------------


class TestExpectedAppResourceSummary:
    def test_postgres(self) -> None:
        raw: dict[str, Any] = {
            "postgres": {"database": "mydb", "user": "myuser", "secret_file": "path/to/pg.env"},
        }
        result = _expected_app_resource_summary(raw)
        assert "postgres" in result
        assert result["postgres"]["database"] == "mydb"

    def test_redis(self) -> None:
        raw: dict[str, Any] = {
            "redis": {"db": 1, "key_prefix": "app:", "secret_file": "path/to/redis.env"},
        }
        result = _expected_app_resource_summary(raw)
        assert "redis" in result
        assert result["redis"]["db"] == 1

    def test_empty_values_skipped(self) -> None:
        raw: dict[str, Any] = {
            "postgres": {"database": "db", "user": ""},
        }
        result = _expected_app_resource_summary(raw)
        assert "user" not in result["postgres"]

    def test_non_dict_resource(self) -> None:
        raw: dict[str, Any] = {"postgres": "invalid"}
        result = _expected_app_resource_summary(raw)
        assert "postgres" not in result

    def test_empty(self) -> None:
        assert _expected_app_resource_summary({}) == {}


# ---------------------------------------------------------------------------
# Golden test
# ---------------------------------------------------------------------------


@pytest.mark.golden
class TestResourceHandlersGolden:
    def test_full_summary_roundtrip(self) -> None:
        """Summary + declared + expected all consistent for a full entry."""
        definition = AppResourceDefinition(
            app="sub2api",
            owner_app="sub2api",
            resource_kinds=("postgres", "redis", "minio"),
            secret_files=("secrets/pg.env", "secrets/redis.env"),
        )
        summary = _summary(definition)
        assert summary["app"] == "sub2api"
        assert len(summary["resource_kinds"]) == 3

        raw: dict[str, Any] = {
            "owner_app": "sub2api",
            "postgres": {"database": "sub2api", "user": "sub2api", "secret_file": "secrets/pg.env"},
            "redis": {"db": 1, "key_prefix": "sub2api:", "secret_file": "secrets/redis.env"},
            "minio": {"bucket": "sub2api", "secret_file": "secrets/minio.env"},
            "secret_files": ["secrets/pg.env", "secrets/redis.env"],
        }
        declared = _declared_payload(raw)
        assert declared["owner_app"] == "sub2api"
        assert "postgres" in declared

        expected = _expected_app_resource_summary(raw)
        assert "postgres" in expected
        assert "redis" in expected
        assert "minio" in expected
