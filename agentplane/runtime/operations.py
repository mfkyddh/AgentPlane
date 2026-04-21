from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any
import uuid


def next_operation_id(prefix: str) -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{prefix}-{timestamp}-{uuid.uuid4().hex[:8]}"


def operation_ledger_path(repo_root: Path, *, now: datetime | None = None) -> Path:
    moment = now or datetime.now(UTC)
    return repo_root / "tmp" / "operation-ledger" / f"{moment.strftime('%Y-%m-%d')}.jsonl"


def append_operation_ledger(
    repo_root: Path,
    *,
    command: str,
    action: str,
    target: str,
    op_id: str,
    dry_run: bool,
    result: str,
    details: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    moment = now or datetime.now(UTC)
    ledger_file = operation_ledger_path(repo_root, now=moment)
    ledger_file.parent.mkdir(parents=True, exist_ok=True)
    entry: dict[str, Any] = {
        "timestamp": moment.isoformat(),
        "command": command,
        "action": action,
        "target": target,
        "op_id": op_id,
        "dry_run": dry_run,
        "result": result,
    }
    if details:
        entry.update(details)
    with ledger_file.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
    return {
        "ledger_file": str(ledger_file),
        "entry": entry,
    }
