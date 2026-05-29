"""Tests for agentplane.domain.app.object_handlers — pure helper functions."""

from __future__ import annotations

from pathlib import Path

import pytest
from agentplane.domain.app.object_handlers import (
    _contract_payload,
    _resolved_summary_path,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# _resolved_summary_path
# ---------------------------------------------------------------------------


class TestResolvedSummaryPath:
    def test_valid_relative(self, tmp_path: Path) -> None:
        sub = tmp_path / "docs"
        sub.mkdir()
        result = _resolved_summary_path(tmp_path, "docs/summary.md")
        assert result == (tmp_path / "docs" / "summary.md").resolve()

    def test_escape_returns_none(self, tmp_path: Path) -> None:
        result = _resolved_summary_path(tmp_path, "../etc/passwd")
        assert result is None

    def test_absolute_within_repo(self, tmp_path: Path) -> None:
        sub = tmp_path / "sub"
        sub.mkdir()
        result = _resolved_summary_path(tmp_path, "sub/file.txt")
        assert result is not None
        assert result.name == "file.txt"

    def test_empty_string(self, tmp_path: Path) -> None:
        result = _resolved_summary_path(tmp_path, "")
        assert result == tmp_path.resolve()


# ---------------------------------------------------------------------------
# _contract_payload
# ---------------------------------------------------------------------------


class TestContractPayload:
    def test_valid_yaml(self, tmp_path: Path) -> None:
        f = tmp_path / "contract.yaml"
        f.write_text("app: myapp\nruntime:\n  container_port: 8080\n", encoding="utf-8")
        result = _contract_payload(f)
        assert result["app"] == "myapp"
        assert result["runtime"]["container_port"] == 8080

    def test_missing_file(self, tmp_path: Path) -> None:
        result = _contract_payload(tmp_path / "nonexistent.yaml")
        assert result == {}

    def test_invalid_yaml(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.yaml"
        f.write_text("{{{{invalid", encoding="utf-8")
        result = _contract_payload(f)
        assert result == {}

    def test_non_dict_yaml(self, tmp_path: Path) -> None:
        f = tmp_path / "list.yaml"
        f.write_text("- item1\n- item2\n", encoding="utf-8")
        result = _contract_payload(f)
        assert result == {}

    def test_empty_yaml(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.yaml"
        f.write_text("", encoding="utf-8")
        result = _contract_payload(f)
        assert result == {}


# ---------------------------------------------------------------------------
# Golden test
# ---------------------------------------------------------------------------


@pytest.mark.golden
class TestObjectHandlersGolden:
    def test_contract_roundtrip(self, tmp_path: Path) -> None:
        """Full contract with nested structure parses correctly."""
        f = tmp_path / "contract.yaml"
        f.write_text(
            "app: sub2api\nruntime:\n  container_port: 3000\n  healthcheck:\n    path: /health\npackaging:\n  image_name: sub2api:latest\ndocs:\n  app_summary_file: docs/summary.md\n",
            encoding="utf-8",
        )
        result = _contract_payload(f)
        assert result["app"] == "sub2api"
        assert result["runtime"]["healthcheck"]["path"] == "/health"
        assert result["packaging"]["image_name"] == "sub2api:latest"

        resolved = _resolved_summary_path(tmp_path, result["docs"]["app_summary_file"])
        assert resolved is not None
        assert resolved.name == "summary.md"
