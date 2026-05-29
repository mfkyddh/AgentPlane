"""Tests for agentplane.domain.infra.onepanel — pure helper functions."""

from __future__ import annotations

import json
from typing import Any

import pytest
from agentplane.domain.infra.onepanel import (
    _bool_arg,
    _operation_result,
    _render_list_preview,
    _selector_values,
    classify_onepanel_error,
    render_onepanel_text,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# _bool_arg
# ---------------------------------------------------------------------------


class TestBoolArg:
    @pytest.mark.parametrize("value", ["1", "true", "True", "yes", "on", "YES"])
    def test_truthy(self, value: str) -> None:
        assert _bool_arg(value) is True

    @pytest.mark.parametrize("value", ["0", "false", "False", "no", "off", "NO"])
    def test_falsy(self, value: str) -> None:
        assert _bool_arg(value) is False

    def test_whitespace(self) -> None:
        assert _bool_arg("  true  ") is True
        assert _bool_arg("  false  ") is False


# ---------------------------------------------------------------------------
# _operation_result
# ---------------------------------------------------------------------------


class TestOperationResult:
    def test_plan(self) -> None:
        assert _operation_result("plan", {}, execute=False) == "planned"

    def test_apply_execute(self) -> None:
        assert _operation_result("apply", {}, execute=True) == "executed"

    def test_apply_no_execute(self) -> None:
        assert _operation_result("apply", {}, execute=False) == "planned"

    def test_refresh_ledger(self) -> None:
        assert _operation_result("refresh-ledger", {}, execute=False) == "refreshed"

    def test_verify_ok(self) -> None:
        assert _operation_result("verify", {"payload": {"ok": True}}, execute=False) == "verified"

    def test_verify_failed(self) -> None:
        assert _operation_result("verify", {"payload": {"ok": False}}, execute=False) == "verify-failed"

    def test_verify_no_body(self) -> None:
        assert _operation_result("verify", {}, execute=False) == "verified"

    def test_unknown_action(self) -> None:
        assert _operation_result("search", {}, execute=False) == "queried"


# ---------------------------------------------------------------------------
# _selector_values
# ---------------------------------------------------------------------------


class TestSelectorValues:
    def test_from_args(self) -> None:
        class Args:
            id = "123"
            name = "test"
            alias = ""
            info = None
            key = ""
            type = ""
            status = ""
            domain = ""

        payload: dict[str, Any] = {}
        result = _selector_values(Args(), payload)
        assert "123" in result
        assert "test" in result

    def test_deduplication(self) -> None:
        class Args:
            id = "same"
            name = "same"
            alias = ""
            info = None
            key = ""
            type = ""
            status = ""
            domain = ""

        result = _selector_values(Args(), {})
        assert result.count("same") == 1

    def test_from_payload_plan(self) -> None:
        class Args:
            id = ""
            name = ""
            alias = ""
            info = None
            key = ""
            type = ""
            status = ""
            domain = ""

        payload = {"payload": {"plan": {"object": "firewall", "mode": "list"}}}
        result = _selector_values(Args(), payload)
        assert "firewall" in result
        assert "list" in result


# ---------------------------------------------------------------------------
# _render_list_preview
# ---------------------------------------------------------------------------


class TestRenderListPreview:
    def test_empty(self) -> None:
        assert _render_list_preview([]) == ["items: 0"]

    def test_one_item(self) -> None:
        result = _render_list_preview([{"name": "svc1"}])
        assert "items: 1" in result
        assert "- svc1" in result

    def test_uses_alias(self) -> None:
        result = _render_list_preview([{"alias": "my-alias", "name": "svc1"}])
        assert "- my-alias" in result

    def test_truncates_at_3(self) -> None:
        items = [{"name": f"svc{i}"} for i in range(5)]
        result = _render_list_preview(items)
        assert "items: 5" in result
        # Only first 3 shown
        assert "- svc0" in result
        assert "- svc2" in result
        assert "- svc3" not in result


# ---------------------------------------------------------------------------
# render_onepanel_text
# ---------------------------------------------------------------------------


class TestRenderOnepanelText:
    def test_root_scope(self) -> None:
        payload = {"env": "wsl", "scope": "root", "action": "call", "hint": "Use --help"}
        result = render_onepanel_text(payload)
        assert "onepanel wsl root call" in result
        assert "Use --help" in result

    def test_counts(self) -> None:
        payload = {"env": "wsl", "scope": "firewall", "action": "list", "payload": {"counts": {"rules": 5}}}
        result = render_onepanel_text(payload)
        assert "rules: 5" in result

    def test_items_list(self) -> None:
        payload = {
            "env": "wsl",
            "scope": "tasks",
            "action": "list",
            "payload": {"items": [{"name": "task1"}, {"name": "task2"}]},
        }
        result = render_onepanel_text(payload)
        assert "items: 2" in result
        assert "- task1" in result

    def test_ok_field(self) -> None:
        payload = {"env": "wsl", "scope": "verify", "action": "verify", "payload": {"ok": True}}
        result = render_onepanel_text(payload)
        assert "ok: yes" in result

    def test_plan_field(self) -> None:
        payload = {
            "env": "wsl",
            "scope": "firewall",
            "action": "plan",
            "payload": {"plan": {"object": "firewall", "mode": "apply"}},
        }
        result = render_onepanel_text(payload)
        assert "plan: firewall / apply" in result

    def test_with_operation(self) -> None:
        # scope must not be "root" for operation to render (root returns early)
        payload = {
            "env": "wsl",
            "scope": "firewall",
            "action": "list",
            "payload": {"ok": True},
            "operation": {"op_id": "OP-001"},
        }
        result = render_onepanel_text(payload)
        assert "op_id: OP-001" in result

    def test_non_dict_body(self) -> None:
        payload = {"env": "wsl", "scope": "test", "action": "call", "payload": "raw string"}
        result = render_onepanel_text(payload)
        assert "raw string" in result


# ---------------------------------------------------------------------------
# classify_onepanel_error
# ---------------------------------------------------------------------------


class TestClassifyOnepanelError:
    def test_json_decode_error(self) -> None:
        assert classify_onepanel_error(json.JSONDecodeError("bad", "", 0)) == "onepanel.invalid_json"

    def test_not_found(self) -> None:
        assert classify_onepanel_error(ValueError("Object not found")) == "onepanel.object_not_found"

    def test_invalid_request(self) -> None:
        assert classify_onepanel_error(ValueError("must decode to an object")) == "onepanel.invalid_request"

    def test_api_failed(self) -> None:
        assert classify_onepanel_error(RuntimeError("API command failed")) == "onepanel.api_failed"

    def test_shell_failed(self) -> None:
        assert classify_onepanel_error(RuntimeError("shell command failed")) == "onepanel.api_failed"

    def test_value_error_generic(self) -> None:
        assert classify_onepanel_error(ValueError("something")) == "onepanel.invalid_request"

    def test_generic_exception(self) -> None:
        assert classify_onepanel_error(RuntimeError("unknown")) == "onepanel.command_failed"


# ---------------------------------------------------------------------------
# Golden test
# ---------------------------------------------------------------------------


@pytest.mark.golden
class TestOnepanelGolden:
    def test_full_render_roundtrip(self) -> None:
        """Full payload with counts, operation, and all fields renders correctly."""
        payload = {
            "env": "prod0-main",
            "scope": "firewall",
            "action": "list",
            "payload": {
                "counts": {"rules": 12, "blocked": 3},
                "items": [{"name": "allow-http"}, {"name": "allow-https"}],
            },
            "operation": {"op_id": "OP-42"},
        }
        result = render_onepanel_text(payload)
        assert "onepanel prod0-main firewall list" in result
        assert "rules: 12" in result
        assert "blocked: 3" in result
        assert "op_id: OP-42" in result
