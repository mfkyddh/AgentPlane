"""Tests for agentplane.scripts.onepanel.ledger — pure helper functions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from agentplane.scripts.onepanel.ledger import (
    _app_rows,
    _automation_rows,
    _container_rows,
    _cronjob_rows,
    _firewall_rows,
    _latest_operation_for,
    _latest_scope_operations,
    _markdown_for,
    _operation_summary,
    _row_tokens,
    _services,
    _tenant_rows,
    _website_rows,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# _services
# ---------------------------------------------------------------------------


class TestServices:
    def test_with_services(self) -> None:
        assert _services({"services": {"pg": {}}}) == {"pg": {}}

    def test_missing(self) -> None:
        assert _services({}) == {}

    def test_non_dict(self) -> None:
        assert _services({"services": "bad"}) == {}


# ---------------------------------------------------------------------------
# _website_rows
# ---------------------------------------------------------------------------


class TestWebsiteRows:
    def test_with_ingresses(self) -> None:
        inv: dict[str, Any] = {"services": {"public_ingresses": [{"domain": "example.com"}, {"domain": "x.com"}]}}
        rows = _website_rows(inv)
        assert len(rows) == 2

    def test_non_list_ingresses(self) -> None:
        inv: dict[str, Any] = {"services": {"public_ingresses": "bad"}}
        assert _website_rows(inv) == []

    def test_non_dict_item(self) -> None:
        inv: dict[str, Any] = {"services": {"public_ingresses": ["bad", {"domain": "ok"}]}}
        rows = _website_rows(inv)
        assert len(rows) == 1

    def test_empty(self) -> None:
        assert _website_rows({}) == []


# ---------------------------------------------------------------------------
# _container_rows
# ---------------------------------------------------------------------------


class TestContainerRows:
    def test_with_containers(self) -> None:
        inv: dict[str, Any] = {"services": {"pg": {"container_name": "pg-dev"}, "redis": {"container_name": "redis-dev"}}}
        rows = _container_rows(inv)
        assert len(rows) == 2
        assert rows[0]["service_key"] == "pg"

    def test_skips_public_ingresses(self) -> None:
        inv: dict[str, Any] = {"services": {"public_ingresses": [{"container_name": "x"}], "pg": {"container_name": "pg"}}}
        rows = _container_rows(inv)
        assert len(rows) == 1

    def test_skips_no_container_name(self) -> None:
        inv: dict[str, Any] = {"services": {"pg": {"host": "127.0.0.1"}}}
        assert _container_rows(inv) == []

    def test_empty(self) -> None:
        assert _container_rows({}) == []


# ---------------------------------------------------------------------------
# _app_rows
# ---------------------------------------------------------------------------


class TestAppRows:
    def test_with_control_plane(self) -> None:
        inv: dict[str, Any] = {"services": {"myapp": {"control_plane": "compose"}}}
        rows = _app_rows(inv)
        assert len(rows) == 1

    def test_with_project_name(self) -> None:
        inv: dict[str, Any] = {"services": {"myapp": {"project_name": "proj"}}}
        rows = _app_rows(inv)
        assert len(rows) == 1

    def test_skips_non_dict(self) -> None:
        inv: dict[str, Any] = {"services": {"myapp": "bad"}}
        assert _app_rows(inv) == []

    def test_empty(self) -> None:
        assert _app_rows({}) == []


# ---------------------------------------------------------------------------
# _cronjob_rows
# ---------------------------------------------------------------------------


class TestCronjobRows:
    def test_with_cronjob(self) -> None:
        inv: dict[str, Any] = {"automations": [{"controller": "cronjob", "name": "backup"}]}
        rows = _cronjob_rows(inv)
        assert len(rows) == 1

    def test_case_insensitive(self) -> None:
        inv: dict[str, Any] = {"automations": [{"controller": "CronJob"}]}
        rows = _cronjob_rows(inv)
        assert len(rows) == 1

    def test_non_cronjob(self) -> None:
        inv: dict[str, Any] = {"automations": [{"controller": "webhook"}]}
        assert _cronjob_rows(inv) == []

    def test_non_list(self) -> None:
        assert _cronjob_rows({"automations": "bad"}) == []

    def test_empty(self) -> None:
        assert _cronjob_rows({}) == []


# ---------------------------------------------------------------------------
# _automation_rows
# ---------------------------------------------------------------------------


class TestAutomationRows:
    def test_with_items(self) -> None:
        inv: dict[str, Any] = {"automations": [{"name": "a"}, {"name": "b"}]}
        assert len(_automation_rows(inv)) == 2

    def test_non_list(self) -> None:
        assert _automation_rows({"automations": "bad"}) == []

    def test_empty(self) -> None:
        assert _automation_rows({}) == []


# ---------------------------------------------------------------------------
# _firewall_rows
# ---------------------------------------------------------------------------


class TestFirewallRows:
    def test_with_firewall(self) -> None:
        inv: dict[str, Any] = {"security": {"firewall": {"rules": []}}}
        rows = _firewall_rows(inv)
        assert len(rows) == 1

    def test_non_dict_security(self) -> None:
        assert _firewall_rows({"security": "bad"}) == []

    def test_no_firewall(self) -> None:
        assert _firewall_rows({"security": {}}) == []

    def test_empty(self) -> None:
        assert _firewall_rows({}) == []


# ---------------------------------------------------------------------------
# _row_tokens
# ---------------------------------------------------------------------------


class TestRowTokens:
    def test_extracts_all_keys(self) -> None:
        row: dict[str, Any] = {
            "id": "1", "alias": "a", "name": "n", "service_key": "sk",
            "app_id": "ai", "container_name": "cn", "primaryDomain": "pd",
            "primary_domain": "pd2", "project_name": "pn", "public_url": "pu",
        }
        tokens = _row_tokens(row)
        assert len(tokens) == 10

    def test_skips_none_and_empty(self) -> None:
        row: dict[str, Any] = {"id": None, "alias": "", "name": "ok"}
        tokens = _row_tokens(row)
        assert tokens == {"ok"}

    def test_empty(self) -> None:
        assert _row_tokens({}) == set()


# ---------------------------------------------------------------------------
# _operation_summary
# ---------------------------------------------------------------------------


class TestOperationSummary:
    def test_extracts_fields(self) -> None:
        entry: dict[str, Any] = {
            "action": "deploy", "result": "ok", "op_id": "op-1",
            "timestamp": "2025-01-01T00:00:00Z", "dry_run": True,
        }
        result = _operation_summary(entry)
        assert result["action"] == "deploy"
        assert result["dry_run"] is True

    def test_defaults(self) -> None:
        result = _operation_summary({})
        assert result["dry_run"] is False


# ---------------------------------------------------------------------------
# _latest_operation_for
# ---------------------------------------------------------------------------


class TestLatestOperationFor:
    def test_finds_matching(self) -> None:
        row: dict[str, Any] = {"container_name": "pg-dev"}
        entries: list[dict[str, Any]] = [
            {"scope": "container", "selectors": ["pg-dev"], "action": "restart", "result": "ok", "timestamp": "t1"},
        ]
        result = _latest_operation_for("container", row, entries)
        assert result is not None
        assert result["action"] == "restart"

    def test_no_match(self) -> None:
        row: dict[str, Any] = {"container_name": "pg-dev"}
        entries: list[dict[str, Any]] = [
            {"scope": "website", "selectors": ["other"], "action": "x", "result": "y", "timestamp": "t1"},
        ]
        assert _latest_operation_for("container", row, entries) is None

    def test_empty_tokens(self) -> None:
        assert _latest_operation_for("container", {}, [{"scope": "container", "selectors": ["x"]}]) is None


# ---------------------------------------------------------------------------
# _latest_scope_operations
# ---------------------------------------------------------------------------


class TestLatestScopeOperations:
    def test_groups_by_scope(self) -> None:
        entries: list[dict[str, Any]] = [
            {"scope": "container", "action": "restart", "result": "ok", "timestamp": "t1"},
            {"scope": "website", "action": "deploy", "result": "ok", "timestamp": "t2"},
            {"scope": "container", "action": "stop", "result": "ok", "timestamp": "t3"},
        ]
        result = _latest_scope_operations(entries)
        assert "container" in result
        assert "website" in result
        # First occurrence wins (sorted desc)
        assert result["container"]["action"] == "restart"

    def test_empty(self) -> None:
        assert _latest_scope_operations([]) == {}


# ---------------------------------------------------------------------------
# _tenant_rows
# ---------------------------------------------------------------------------


class TestTenantRows:
    def test_valid_registry(self, tmp_path: Path) -> None:
        server_root = tmp_path / "inventory" / "servers" / "wsl"
        server_root.mkdir(parents=True)
        (server_root / "app-resources.json").write_text(
            json.dumps({"myapp": {"owner_app": "myapp", "resource_kinds": ["postgres"]}}),
            encoding="utf-8",
        )
        rows = _tenant_rows(server_root)
        assert len(rows) == 1
        assert rows[0]["app_id"] == "myapp"

    def test_skips_non_owner(self, tmp_path: Path) -> None:
        server_root = tmp_path / "inventory" / "servers" / "wsl"
        server_root.mkdir(parents=True)
        (server_root / "app-resources.json").write_text(
            json.dumps({"myapp": {"owner_app": "other"}}),
            encoding="utf-8",
        )
        assert _tenant_rows(server_root) == []

    def test_missing_file(self, tmp_path: Path) -> None:
        assert _tenant_rows(tmp_path / "nope") == []


# ---------------------------------------------------------------------------
# _markdown_for
# ---------------------------------------------------------------------------


class TestMarkdownFor:
    def test_empty(self) -> None:
        result = _markdown_for("containers", [])
        assert "none" in result

    def test_with_rows(self) -> None:
        rows: list[dict[str, Any]] = [{"alias": "pg", "status": "running"}]
        result = _markdown_for("containers", rows)
        assert "pg" in result
        assert "running" in result

    def test_with_last_operation(self) -> None:
        rows: list[dict[str, Any]] = [
            {"name": "svc", "last_cli_operation": {"action": "deploy", "result": "ok", "timestamp": "t1"}},
        ]
        result = _markdown_for("containers", rows)
        assert "deploy" in result
        assert "ok" in result

    def test_label_fallback(self) -> None:
        rows: list[dict[str, Any]] = [{"service_key": "sk"}]
        result = _markdown_for("containers", rows)
        assert "sk" in result

    def test_app_resources_header(self) -> None:
        result = _markdown_for("app_resources", [])
        assert "Redis" in result


# ---------------------------------------------------------------------------
# Golden test
# ---------------------------------------------------------------------------


@pytest.mark.golden
class TestLedgerHelpersGolden:
    def test_full_inventory_parse(self) -> None:
        """Parse a realistic inventory through all row extractors."""
        inv: dict[str, Any] = {
            "services": {
                "public_ingresses": [{"domain": "app.example.com"}],
                "pg": {"container_name": "pg-dev"},
                "myapp": {"control_plane": "compose", "container_name": "myapp-dev"},
            },
            "automations": [
                {"controller": "cronjob", "name": "backup"},
                {"controller": "webhook", "name": "notify"},
            ],
            "security": {"firewall": {"rules": []}},
        }
        assert len(_website_rows(inv)) == 1
        assert len(_container_rows(inv)) == 2
        assert len(_app_rows(inv)) == 1
        assert len(_cronjob_rows(inv)) == 1
        assert len(_automation_rows(inv)) == 2
        assert len(_firewall_rows(inv)) == 1
