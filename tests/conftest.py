from __future__ import annotations

from pathlib import Path

import pytest
from tests.support.markers import apply_marker_rules

# ---------------------------------------------------------------------------
# Hooks
# ---------------------------------------------------------------------------


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    apply_marker_rules(items)


# ---------------------------------------------------------------------------
# Shared fixtures (available to all test directories)
# ---------------------------------------------------------------------------


@pytest.fixture
def cli_tmpdir(tmp_path: Path) -> Path:
    """A per-test (per-worker) mini-repo structure for CLI E2E tests.

    Creates the minimal directory skeleton that ``agentplane`` CLI expects,
    so every test gets its own isolated workspace — no shared state, no
    write contention, xdist-safe.
    """
    (tmp_path / "inventory" / "servers").mkdir(parents=True)
    (tmp_path / "secrets" / "ssh").mkdir(parents=True)
    (tmp_path / "templates").mkdir(parents=True)
    (tmp_path / "infra" / "compose").mkdir(parents=True)
    (tmp_path / ".agents").mkdir(parents=True)
    return tmp_path


@pytest.fixture
def isolated_registry():
    """A fresh BackendRegistry that does NOT pollute the global singleton.

    Use this in integration/unit tests that need to register backends
    without side-effects on other tests.
    """
    from agentplane.runtime.backends.registry import BackendRegistry

    return BackendRegistry()
