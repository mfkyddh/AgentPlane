"""Shared fixtures for infra tests."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def fake_ssh_bin_dir(tmp_path: Path) -> Path:
    """Create a temporary bin directory for fake SSH scripts."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    return bin_dir
