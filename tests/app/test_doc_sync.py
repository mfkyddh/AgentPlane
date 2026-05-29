"""Tests for agentplane.domain.app.doc_sync — pure rendering and helper functions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from agentplane.domain.app.doc_sync import (
    ONEPANEL_LEDGER_BEGIN,
    ONEPANEL_LEDGER_END,
    _output_app_resource_summary,
    _payload_path,
    _preserve_onepanel_ledger_section,
    _render_server_readme,
    _resolve_app_summary_path,
    render_rollback_entry,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# _payload_path
# ---------------------------------------------------------------------------


class TestPayloadPath:
    def test_windows_drive_letter(self) -> None:
        """Windows drive letter paths are returned as-is."""
        assert _payload_path("C:/Users/test/file.txt") == "C:/Users/test/file.txt"

    def test_backslash_to_forward_slash(self) -> None:
        assert _payload_path("some\\path\\file.txt") == "some/path/file.txt"

    def test_already_forward_slash(self) -> None:
        assert _payload_path("some/path/file.txt") == "some/path/file.txt"

    def test_path_object(self) -> None:
        assert _payload_path(Path("some/path/file.txt")) == "some/path/file.txt"


# ---------------------------------------------------------------------------
# render_rollback_entry
# ---------------------------------------------------------------------------


class TestRenderRollbackEntry:
    def test_kind_none_with_note(self) -> None:
        assert render_rollback_entry({"kind": "none", "note": "无旧控制面"}) == "无旧控制面"

    def test_kind_none_without_note(self) -> None:
        assert render_rollback_entry({"kind": "none"}) == "无独立旧控制面"

    def test_kind_systemd(self) -> None:
        assert render_rollback_entry({"kind": "systemd", "service_name": "myapp"}) == "myapp"

    def test_kind_systemd_no_service_name(self) -> None:
        assert render_rollback_entry({"kind": "systemd"}) == "-"

    def test_kind_1panel_app(self) -> None:
        entry = {"kind": "1panel-app", "app_key": "myapp", "install_id": 42, "container_name": "c1"}
        result = render_rollback_entry(entry)
        assert "1panel-app" in result
        assert "myapp" in result
        assert "install_id=42" in result
        assert "container=c1" in result

    def test_kind_1panel_app_minimal(self) -> None:
        result = render_rollback_entry({"kind": "1panel-app", "app_key": "x"})
        assert "1panel-app" in result
        assert "x" in result

    def test_kind_1panel_compose(self) -> None:
        entry = {
            "kind": "1panel-compose",
            "project_name": "proj",
            "container_name": "c1",
            "project_path": "/opt/proj",
            "compose_file": "docker-compose.yaml",
        }
        result = render_rollback_entry(entry)
        assert "1panel-compose" in result
        assert "proj" in result
        assert "container=c1" in result
        assert "path=/opt/proj" in result
        assert "compose=docker-compose.yaml" in result

    def test_kind_1panel_compose_minimal(self) -> None:
        result = render_rollback_entry({"kind": "1panel-compose", "project_name": "p"})
        assert "1panel-compose" in result

    def test_unknown_kind_json_fallback(self) -> None:
        entry = {"kind": "unknown-kind", "foo": "bar"}
        result = render_rollback_entry(entry)
        parsed = json.loads(result)
        assert parsed["kind"] == "unknown-kind"

    def test_no_kind_json_fallback(self) -> None:
        entry = {"foo": "bar"}
        result = render_rollback_entry(entry)
        parsed = json.loads(result)
        assert parsed["foo"] == "bar"


# ---------------------------------------------------------------------------
# _output_app_resource_summary
# ---------------------------------------------------------------------------


class TestOutputAppResourceSummary:
    def test_non_dict_returns_empty(self) -> None:
        assert _output_app_resource_summary(None) == {}
        assert _output_app_resource_summary("bad") == {}
        assert _output_app_resource_summary([]) == {}

    def test_postgres(self) -> None:
        summary = _output_app_resource_summary({"postgres": {"host": "pg.local", "db": "mydb"}})
        assert "postgres" in summary
        assert summary["postgres"]["host"] == "pg.local"

    def test_redis_strips_user(self) -> None:
        summary = _output_app_resource_summary({"redis": {"host": "redis.local", "user": "ignored"}})
        assert "redis" in summary
        assert "user" not in summary["redis"]

    def test_minio(self) -> None:
        summary = _output_app_resource_summary({"minio": {"bucket": "data", "policy_name": "rw"}})
        assert "minio" in summary
        assert summary["minio"]["bucket"] == "data"

    def test_skips_empty(self) -> None:
        summary = _output_app_resource_summary({"postgres": {}})
        assert summary == {}

    def test_skips_none_values(self) -> None:
        summary = _output_app_resource_summary({"postgres": {"host": "pg.local", "db": None}})
        assert "db" not in summary["postgres"]

    def test_unknown_kind_ignored(self) -> None:
        summary = _output_app_resource_summary({"mysql": {"host": "x"}})
        assert summary == {}


# ---------------------------------------------------------------------------
# _preserve_onepanel_ledger_section
# ---------------------------------------------------------------------------


class TestPreserveOnepanelLedger:
    def test_no_markers_returns_rendered(self) -> None:
        existing = "old content"
        rendered = "new content"
        assert _preserve_onepanel_ledger_section(existing, rendered) == rendered

    def test_both_markers_in_rendered(self) -> None:
        existing = f"before{ONEPANEL_LEDGER_BEGIN}ledger{ONEPANEL_LEDGER_END}after"
        rendered = f"new{ONEPANEL_LEDGER_BEGIN}newledger{ONEPANEL_LEDGER_END}end"
        assert _preserve_onepanel_ledger_section(existing, rendered) == rendered

    def test_preserves_existing_ledger(self) -> None:
        existing = f"before\n{ONEPANEL_LEDGER_BEGIN}\nmy ledger\n{ONEPANEL_LEDGER_END}\nafter"
        rendered = "completely new content\n"
        result = _preserve_onepanel_ledger_section(existing, rendered)
        assert "my ledger" in result
        assert ONEPANEL_LEDGER_BEGIN in result
        assert ONEPANEL_LEDGER_END in result
        assert "completely new content" in result

    def test_missing_end_marker_returns_rendered(self) -> None:
        existing = f"before{ONEPANEL_LEDGER_BEGIN}incomplete"
        rendered = "new content"
        assert _preserve_onepanel_ledger_section(existing, rendered) == rendered


# ---------------------------------------------------------------------------
# _resolve_app_summary_path
# ---------------------------------------------------------------------------


class TestResolveAppSummaryPath:
    def test_per_target_path(self) -> None:
        contract = {"docs": {"app_summary_files": {"wsl": "docs/wsl-summary.md", "prod0-main": "docs/prod.md"}}}
        assert _resolve_app_summary_path(contract, target="wsl") == "docs/wsl-summary.md"

    def test_fallback_to_single_path(self) -> None:
        contract = {"docs": {"app_summary_file": "docs/summary.md"}}
        assert _resolve_app_summary_path(contract, target="wsl") == "docs/summary.md"

    def test_no_path_returns_none(self) -> None:
        assert _resolve_app_summary_path({}, target="wsl") is None

    def test_empty_dict_returns_none(self) -> None:
        assert _resolve_app_summary_path({"docs": {}}, target="wsl") is None

    def test_per_target_empty_falls_back(self) -> None:
        contract = {"docs": {"app_summary_files": {}, "app_summary_file": "docs/summary.md"}}
        assert _resolve_app_summary_path(contract, target="wsl") == "docs/summary.md"


# ---------------------------------------------------------------------------
# _render_server_readme
# ---------------------------------------------------------------------------


class TestRenderServerReadme:
    def test_basic(self) -> None:
        inventory: dict[str, Any] = {"label": "test server", "provider": "aws"}
        result = _render_server_readme("wsl", inventory)
        assert "wsl 摘要" in result
        assert "test server" in result
        assert "aws" in result

    def test_with_services(self) -> None:
        inventory: dict[str, Any] = {
            "services": {
                "myapp": {
                    "control_plane": "compose",
                    "container_name": "myapp-dev",
                    "public_url": "http://localhost:8080",
                }
            }
        }
        result = _render_server_readme("wsl", inventory)
        assert "myapp" in result
        assert "compose" in result

    def test_with_public_ip(self) -> None:
        inventory: dict[str, Any] = {"public_ip": "1.2.3.4", "public_domain": "example.com"}
        result = _render_server_readme("prod0-main", inventory)
        assert "1.2.3.4" in result
        assert "example.com" in result

    def test_with_ssh_alias(self) -> None:
        inventory: dict[str, Any] = {"ssh": {"aliases": ["my-server"]}}
        result = _render_server_readme("wsl", inventory)
        assert "my-server" in result

    def test_empty_inventory(self) -> None:
        result = _render_server_readme("wsl", {})
        assert "wsl 摘要" in result


# ---------------------------------------------------------------------------
# Golden test
# ---------------------------------------------------------------------------


@pytest.mark.golden
class TestDocSyncGolden:
    def test_rollback_entry_all_kinds(self) -> None:
        """Every rollback kind renders without error."""
        kinds = [
            {"kind": "none", "note": "test"},
            {"kind": "systemd", "service_name": "svc"},
            {"kind": "1panel-app", "app_key": "k"},
            {"kind": "1panel-compose", "project_name": "p"},
            {"kind": "totally-unknown"},
        ]
        for entry in kinds:
            result = render_rollback_entry(entry)
            assert isinstance(result, str)
            assert len(result) > 0
