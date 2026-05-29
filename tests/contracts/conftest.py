"""Shared fixtures for provider contract tests."""

from __future__ import annotations

import pytest
from agentplane.providers.stub_provider import StubProvider


def _has_onepanel_target() -> bool:
    """Check if a real 1Panel target is configured and reachable."""
    try:
        from agentplane.scripts.onepanel.env_targets import supported_targets
        targets = supported_targets()
        if not targets:
            return False
        # Quick reachability check: try to get a dashboard (will fail fast if unreachable)
        from agentplane.providers.onepanel_adapter import OnePanelAdapter
        adapter = OnePanelAdapter()
        tgt = adapter.get_target(targets[0])
        adapter.get_dashboard(tgt)
        return True
    except Exception:
        return False


def _make_onepanel_adapter():
    from agentplane.providers.onepanel_adapter import OnePanelAdapter
    return OnePanelAdapter()


def _make_onepanel_target_name() -> str:
    from agentplane.scripts.onepanel.env_targets import supported_targets
    targets = supported_targets()
    return targets[0] if targets else ""


def _provider_params():
    """Yield parametrize args: always include stub, include onepanel only if configured."""
    params = [pytest.param("stub", id="stub")]
    if _has_onepanel_target():
        params.append(pytest.param("onepanel", id="onepanel"))
    return params


@pytest.fixture(params=_provider_params())
def provider(request):
    """Yield (provider, default_target_name) for parametrized contract tests.

    OnePanel adapter is only tested when a real 1Panel target is configured.
    """
    if request.param == "onepanel":
        return _make_onepanel_adapter(), _make_onepanel_target_name()
    return StubProvider(), "test-target"


@pytest.fixture
def onepanel_target_name():
    """Return the first configured 1Panel target name, or skip."""
    if not _has_onepanel_target():
        pytest.skip("No 1Panel target configured")
    return _make_onepanel_target_name()
