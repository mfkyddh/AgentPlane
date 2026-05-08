"""Shared fixtures for service tests."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def service_tmpdir(tmp_path: Path) -> Path:
    """Create service test directory skeleton with inventory and secrets."""
    (tmp_path / "inventory" / "servers").mkdir(parents=True)
    (tmp_path / "secrets" / "ssh").mkdir(parents=True)
    return tmp_path
