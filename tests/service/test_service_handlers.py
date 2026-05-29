"""Tests for agentplane.domain.service.handlers — pure helper functions."""

from __future__ import annotations

from typing import Any

import pytest
from agentplane.domain.service.handlers import (
    _projection_handoff,
    _service_canonical_ref,
    _service_ledger_fields,
    _service_summary,
)
from agentplane.domain.service.models import ServiceDefinition

pytestmark = pytest.mark.unit


def _make_definition(**overrides: Any) -> ServiceDefinition:
    defaults: dict[str, Any] = {
        "name": "postgres",
        "runtime_kind": "systemd",
        "control_plane": "systemd",
        "supported_operations": ("restart",),
        "supported_targets": ("wsl", "prod0-main"),
        "metadata": {},
    }
    defaults.update(overrides)
    return ServiceDefinition(**defaults)


# ---------------------------------------------------------------------------
# _service_summary
# ---------------------------------------------------------------------------


class TestServiceSummary:
    def test_basic(self) -> None:
        definition = _make_definition()
        result = _service_summary(definition, {"host": "prod0"})
        assert result["name"] == "postgres"
        assert result["kind"] == "systemd"
        assert result["declared"]["host"] == "prod0"

    def test_none_declared(self) -> None:
        definition = _make_definition()
        result = _service_summary(definition, None)
        assert result["declared"] == {}


# ---------------------------------------------------------------------------
# _service_canonical_ref
# ---------------------------------------------------------------------------


class TestServiceCanonicalRef:
    def test_format(self) -> None:
        ref = _service_canonical_ref("wsl", "postgres")
        assert ref == "targets/wsl/services/postgres"

    def test_prod0(self) -> None:
        ref = _service_canonical_ref("prod0-main", "redis")
        assert ref == "targets/prod0-main/services/redis"


# ---------------------------------------------------------------------------
# _service_ledger_fields
# ---------------------------------------------------------------------------


class TestServiceLedgerFields:
    def test_includes_target(self) -> None:
        definition = _make_definition()
        result = _service_ledger_fields(definition, None, target="wsl")
        assert result["target"] == "wsl"
        assert result["name"] == "postgres"

    def test_includes_summary(self) -> None:
        definition = _make_definition()
        result = _service_ledger_fields(definition, {"key": "val"}, target="prod0-main")
        assert result["declared"]["key"] == "val"


# ---------------------------------------------------------------------------
# _projection_handoff
# ---------------------------------------------------------------------------


class TestProjectionHandoff:
    def test_recompose_triggers_required(self) -> None:
        definition = _make_definition(control_plane="compose")
        result = _projection_handoff(definition, None, target="wsl", trigger="reconcile")
        assert result["required"] is True
        assert len(result["steps"]) >= 1

    def test_non_reconcile_not_required(self) -> None:
        definition = _make_definition()
        result = _projection_handoff(definition, None, target="wsl", trigger="verify")
        assert result["required"] is False

    def test_with_projection_app(self) -> None:
        definition = _make_definition(control_plane="compose")
        declared: dict[str, Any] = {"app_id": "sub2api"}
        result = _projection_handoff(definition, declared, target="wsl", trigger="reconcile")
        assert len(result["steps"]) == 2
        assert result["steps"][1]["action"] == "runtime-env.verify"

    def test_metadata_fallback(self) -> None:
        definition = _make_definition(metadata={"projection_app": "myapp"})
        result = _projection_handoff(definition, None, target="wsl", trigger="verify")
        assert len(result["steps"]) == 2


# ---------------------------------------------------------------------------
# Golden test
# ---------------------------------------------------------------------------


@pytest.mark.golden
class TestServiceHandlersGolden:
    def test_full_service_roundtrip(self) -> None:
        """Full definition with declared, projection_app, and reconcile trigger."""
        definition = _make_definition(
            control_plane="onepanel-compose",
            supported_operations=("restart", "stop"),
            metadata={"projection_app": "sub2api"},
        )
        declared: dict[str, Any] = {"host": "prod0", "app_id": "sub2api"}
        summary = _service_summary(definition, declared)
        assert summary["name"] == "postgres"
        assert summary["control_plane"] == "onepanel-compose"

        handoff = _projection_handoff(definition, declared, target="prod0-main", trigger="reconcile")
        assert handoff["required"] is True
        assert len(handoff["steps"]) == 2

        ref = _service_canonical_ref("prod0-main", "postgres")
        assert ref == "targets/prod0-main/services/postgres"

        fields = _service_ledger_fields(definition, declared, target="prod0-main")
        assert fields["target"] == "prod0-main"
        assert fields["declared"]["host"] == "prod0"
