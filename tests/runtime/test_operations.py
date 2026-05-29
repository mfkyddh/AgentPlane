"""Tests for agentplane.runtime.operations — pure helper functions."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from agentplane.runtime.operations import (
    append_operation_ledger,
    next_operation_id,
    operation_ledger_path,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# next_operation_id
# ---------------------------------------------------------------------------


class TestNextOperationId:
    def test_prefix(self) -> None:
        op_id = next_operation_id("deploy")
        assert op_id.startswith("deploy-")

    def test_unique(self) -> None:
        id1 = next_operation_id("deploy")
        id2 = next_operation_id("deploy")
        assert id1 != id2

    def test_contains_timestamp(self) -> None:
        op_id = next_operation_id("verify")
        # Format: prefix-YYYYMMDDTHHMMSSZ-xxxxxxxx
        parts = op_id.split("-")
        assert len(parts) >= 3
        assert parts[0] == "verify"


# ---------------------------------------------------------------------------
# operation_ledger_path
# ---------------------------------------------------------------------------


class TestOperationLedgerPath:
    def test_date_based(self, tmp_path: Path) -> None:
        now = datetime(2025, 6, 15, 12, 0, 0, tzinfo=UTC)
        result = operation_ledger_path(tmp_path, now=now)
        assert "2025-06-15" in result.name
        assert result.suffix == ".jsonl"
        assert "operation-ledger" in str(result)


# ---------------------------------------------------------------------------
# append_operation_ledger
# ---------------------------------------------------------------------------


class TestAppendOperationLedger:
    def test_creates_entry(self, tmp_path: Path) -> None:
        now = datetime(2025, 6, 15, 12, 0, 0, tzinfo=UTC)
        result = append_operation_ledger(
            tmp_path,
            command="app",
            action="deploy",
            target="wsl",
            op_id="deploy-20250615T120000Z-abc12345",
            dry_run=False,
            result="ok",
            now=now,
        )
        assert "ledger_file" in result
        assert result["entry"]["command"] == "app"
        assert result["entry"]["action"] == "deploy"
        assert result["entry"]["op_id"] == "deploy-20250615T120000Z-abc12345"

    def test_creates_file(self, tmp_path: Path) -> None:
        now = datetime(2025, 6, 15, 12, 0, 0, tzinfo=UTC)
        append_operation_ledger(
            tmp_path,
            command="app",
            action="deploy",
            target="wsl",
            op_id="op-1",
            dry_run=True,
            result="ok",
            now=now,
        )
        ledger_file = tmp_path / "tmp" / "operation-ledger" / "2025-06-15.jsonl"
        assert ledger_file.exists()
        content = ledger_file.read_text(encoding="utf-8")
        assert "deploy" in content
        assert "op-1" in content

    def test_with_details(self, tmp_path: Path) -> None:
        now = datetime(2025, 6, 15, 12, 0, 0, tzinfo=UTC)
        result = append_operation_ledger(
            tmp_path,
            command="app",
            action="deploy",
            target="wsl",
            op_id="op-2",
            dry_run=False,
            result="ok",
            details={"app": "myapp", "image": "myapp:latest"},
            now=now,
        )
        assert result["entry"]["app"] == "myapp"
        assert result["entry"]["image"] == "myapp:latest"

    def test_appends_multiple(self, tmp_path: Path) -> None:
        now = datetime(2025, 6, 15, 12, 0, 0, tzinfo=UTC)
        append_operation_ledger(
            tmp_path, command="app", action="deploy", target="wsl",
            op_id="op-1", dry_run=False, result="ok", now=now,
        )
        append_operation_ledger(
            tmp_path, command="app", action="verify", target="wsl",
            op_id="op-2", dry_run=False, result="ok", now=now,
        )
        ledger_file = tmp_path / "tmp" / "operation-ledger" / "2025-06-15.jsonl"
        lines = ledger_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2


# ---------------------------------------------------------------------------
# Golden test
# ---------------------------------------------------------------------------


@pytest.mark.golden
class TestOperationsGolden:
    def test_full_operation_roundtrip(self, tmp_path: Path) -> None:
        """Generate ID → write ledger → verify file content."""
        op_id = next_operation_id("deploy")
        assert op_id.startswith("deploy-")

        now = datetime(2025, 6, 15, 12, 0, 0, tzinfo=UTC)
        result = append_operation_ledger(
            tmp_path,
            command="app",
            action="deploy",
            target="wsl",
            op_id=op_id,
            dry_run=False,
            result="ok",
            details={"app": "myapp"},
            now=now,
        )
        assert result["entry"]["op_id"] == op_id

        ledger_file = Path(result["ledger_file"])
        assert ledger_file.exists()
