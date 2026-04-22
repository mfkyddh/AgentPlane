from __future__ import annotations

from pathlib import Path
from typing import Any

from agentplane.scripts.onepanel.ledger import refresh_ledgers


def refresh_onepanel_ledgers(repo_root: Path, target: str, *, write: bool) -> dict[str, Any]:
    return refresh_ledgers(repo_root, target, write=write)
