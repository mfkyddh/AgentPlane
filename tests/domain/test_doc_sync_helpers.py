"""Tests for agentplane.domain.app.doc_sync — pure helper functions."""

from __future__ import annotations

import json

import pytest
from agentplane.domain.app.doc_sync import (
    ONEPANEL_LEDGER_BEGIN,
    ONEPANEL_LEDGER_END,
    _output_app_resource_summary,
    _payload_path,
    _preserve_onepanel_ledger_section,
    render_rollback_entry,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# _payload_path
# ---------------------------------------------------------------------------


class TestPayloadPath:
    def test_windows_drive_letter(self) -> None:
        result = _payload_path("C:\\Users\\test\\file.txt")
        assert result == "C:\\Users\\test\\file.txt"

    def test_posix_path(self) -> None:
        result = _payload_path("/home/user/file.txt")
        assert result == "/home/user/file.txt"

    def test_relative_backslash(self) -> None:
        result = _payload_path("some\\path\\file.txt")
        assert "\\" not in result or ":" in result


# ---------------------------------------------------------------------------
# render_rollback_entry
# ---------------------------------------------------------------------------


class TestRenderRollbackEntry:
    def test_none_kind_with_note(self) -> None:
        result = render_rollback_entry({"kind": "none", "note": "No rollback"})
        assert result == "No rollback"

    def test_none_kind_without_note(self) -> None:
        result = render_rollback_entry({"kind": "none"})
        assert result == "无独立旧控制面"

    def test_systemd(self) -> None:
        result = render_rollback_entry({"kind": "systemd", "service_name": "myapp"})
        assert result == "myapp"

    def test_1panel_app_basic(self) -> None:
        result = render_rollback_entry({"kind": "1panel-app", "app_key": "myapp"})
        assert "myapp" in result

    def test_1panel_app_with_install_id(self) -> None:
        result = render_rollback_entry({"kind": "1panel-app", "app_key": "myapp", "install_id": 42})
        assert "install_id=42" in result

    def test_1panel_app_with_container(self) -> None:
        result = render_rollback_entry({
            "kind": "1panel-app", "app_key": "myapp", "container_name": "c1"
        })
        assert "container=c1" in result

    def test_1panel_compose_basic(self) -> None:
        result = render_rollback_entry({"kind": "1panel-compose", "project_name": "proj"})
        assert "proj" in result

    def test_1panel_compose_with_details(self) -> None:
        result = render_rollback_entry({
            "kind": "1panel-compose",
            "project_name": "proj",
            "container_name": "c1",
            "project_path": "/opt/proj",
            "compose_file": "docker-compose.yml",
        })
        assert "container=c1" in result
        assert "path=/opt/proj" in result
        assert "compose=docker-compose.yml" in result

    def test_unknown_kind_json_fallback(self) -> None:
        entry = {"kind": "unknown-kind", "foo": "bar"}
        result = render_rollback_entry(entry)
        parsed = json.loads(result)
        assert parsed["kind"] == "unknown-kind"

    def test_missing_kind_json_fallback(self) -> None:
        entry = {"foo": "bar"}
        result = render_rollback_entry(entry)
        parsed = json.loads(result)
        assert parsed["foo"] == "bar"


# ---------------------------------------------------------------------------
# _output_app_resource_summary
# ---------------------------------------------------------------------------


class TestOutputAppResourceSummary:
    def test_none_input(self) -> None:
        assert _output_app_resource_summary(None) == {}

    def test_non_dict_input(self) -> None:
        assert _output_app_resource_summary("invalid") == {}

    def test_postgres(self) -> None:
        summary = {"postgres": {"database": "db", "user": "u"}}
        result = _output_app_resource_summary(summary)
        assert result["postgres"]["database"] == "db"

    def test_redis_strips_user(self) -> None:
        summary = {"redis": {"db": 1, "user": "default"}}
        result = _output_app_resource_summary(summary)
        assert "user" not in result["redis"]
        assert result["redis"]["db"] == 1

    def test_empty_values_removed(self) -> None:
        summary = {"postgres": {"database": "db", "user": None, "extra": ""}}
        result = _output_app_resource_summary(summary)
        assert "user" not in result["postgres"]
        assert "extra" not in result["postgres"]

    def test_empty_after_cleanup_skipped(self) -> None:
        summary = {"postgres": {"database": None, "user": ""}}
        result = _output_app_resource_summary(summary)
        assert "postgres" not in result


# ---------------------------------------------------------------------------
# _preserve_onepanel_ledger_section
# ---------------------------------------------------------------------------


class TestPreserveOnepanelLedgerSection:
    def test_no_existing_ledger(self) -> None:
        result = _preserve_onepanel_ledger_section("", "new content")
        assert result == "new content"

    def test_existing_has_ledger_rendered_does_not(self) -> None:
        existing = f"before\n{ONEPANEL_LEDGER_BEGIN}\nledger data\n{ONEPANEL_LEDGER_END}\n"
        rendered = "rendered content\n"
        result = _preserve_onepanel_ledger_section(existing, rendered)
        assert "ledger data" in result
        assert "rendered content" in result

    def test_both_have_ledger_uses_rendered(self) -> None:
        existing = f"{ONEPANEL_LEDGER_BEGIN}\nold\n{ONEPANEL_LEDGER_END}"
        rendered = f"{ONEPANEL_LEDGER_BEGIN}\nnew\n{ONEPANEL_LEDGER_END}"
        result = _preserve_onepanel_ledger_section(existing, rendered)
        assert result == rendered

    def test_neither_has_ledger(self) -> None:
        result = _preserve_onepanel_ledger_section("old content", "new content")
        assert result == "new content"


# ---------------------------------------------------------------------------
# Golden test
# ---------------------------------------------------------------------------


@pytest.mark.golden
class TestDocSyncGolden:
    def test_full_rollback_render_roundtrip(self) -> None:
        """All rollback kinds render correctly."""
        entries = [
            {"kind": "none", "note": "N/A"},
            {"kind": "systemd", "service_name": "svc"},
            {"kind": "1panel-app", "app_key": "app", "install_id": 1},
            {"kind": "1panel-compose", "project_name": "proj", "container_name": "c"},
        ]
        for entry in entries:
            result = render_rollback_entry(entry)
            assert result  # non-empty

        summary = _output_app_resource_summary({
            "postgres": {"database": "db", "user": "u"},
            "redis": {"db": 0, "user": "default"},
        })
        assert "postgres" in summary
        assert "user" not in summary.get("redis", {})
