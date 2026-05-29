"""Tests for agentplane.scripts.onepanel.verification — pure helper functions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from agentplane.scripts.onepanel.verification import (
    _check,
    _error_payload,
    _render_report_markdown,
    _report_paths,
    _run_check,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# _check
# ---------------------------------------------------------------------------


class TestCheck:
    def test_ok(self) -> None:
        result = _check("panel", True, {"version": "1.0"})
        assert result["scope"] == "panel"
        assert result["ok"] is True
        assert result["payload"]["version"] == "1.0"

    def test_fail(self) -> None:
        result = _check("website", False, {"error": "not found"})
        assert result["ok"] is False


# ---------------------------------------------------------------------------
# _error_payload
# ---------------------------------------------------------------------------


class TestErrorPayload:
    def test_plain_message(self) -> None:
        result = _error_payload(RuntimeError("something broke"))
        assert result["error"]["message"] == "something broke"

    def test_json_message(self) -> None:
        exc = RuntimeError('{"code": "ERR", "detail": "bad"}')
        result = _error_payload(exc)
        assert result["error"]["code"] == "ERR"

    def test_invalid_json_message(self) -> None:
        exc = RuntimeError("{not valid json")
        result = _error_payload(exc)
        assert "message" in result["error"]


# ---------------------------------------------------------------------------
# _run_check
# ---------------------------------------------------------------------------


class TestRunCheck:
    def test_success(self) -> None:
        result = _run_check("panel", lambda: {"version": "1.0"}, lambda p: bool(p.get("version")))
        assert result["ok"] is True
        assert result["scope"] == "panel"

    def test_predicate_false(self) -> None:
        result = _run_check("panel", lambda: {"version": ""}, lambda p: bool(p.get("version")))
        assert result["ok"] is False

    def test_exception(self) -> None:
        def boom() -> dict[str, Any]:
            raise RuntimeError("connection failed")

        result = _run_check("panel", boom, lambda p: True)
        assert result["ok"] is False
        assert "connection failed" in str(result["payload"])


# ---------------------------------------------------------------------------
# _report_paths
# ---------------------------------------------------------------------------


class TestReportPaths:
    def test_generates_paths(self, tmp_path: Path) -> None:
        json_path, md_path = _report_paths(tmp_path, "wsl", "default")
        assert json_path.name == "verification-default.json"
        assert md_path.name == "verification-default.md"
        assert "ledgers" in str(json_path)


# ---------------------------------------------------------------------------
# _render_report_markdown
# ---------------------------------------------------------------------------


class TestRenderReportMarkdown:
    def test_ok_report(self) -> None:
        payload: dict[str, Any] = {
            "profile": "default",
            "env": "wsl",
            "ok": True,
            "checks": [
                {"scope": "panel", "ok": True},
                {"scope": "website", "ok": True},
            ],
        }
        result = _render_report_markdown(payload)
        assert "default" in result
        assert "yes" in result
        assert "panel" in result
        assert "website" in result

    def test_fail_report(self) -> None:
        payload: dict[str, Any] = {
            "profile": "default",
            "env": "wsl",
            "ok": False,
            "checks": [
                {"scope": "panel", "ok": False},
            ],
        }
        result = _render_report_markdown(payload)
        assert "no" in result
        assert "fail" in result


# ---------------------------------------------------------------------------
# Golden test
# ---------------------------------------------------------------------------


@pytest.mark.golden
class TestVerificationHelpersGolden:
    def test_full_check_render_roundtrip(self) -> None:
        """Run check → render markdown → verify consistency."""
        checks = [
            _run_check("panel", lambda: {"version": "1.0"}, lambda p: bool(p.get("version"))),
            _run_check("website", lambda: {"alias": "test"}, lambda p: bool(p.get("alias"))),
        ]
        assert all(c["ok"] for c in checks)

        payload: dict[str, Any] = {
            "profile": "default",
            "env": "wsl",
            "ok": all(c["ok"] for c in checks),
            "checks": checks,
        }
        md = _render_report_markdown(payload)
        assert "yes" in md
        assert "panel" in md
        assert "website" in md
