"""Shared fixtures for provider unit tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from agentplane.providers.onepanel_adapter import OnePanelAdapter


@pytest.fixture
def mock_gateway():
    """Create a mock OnePanelProviderGateway."""
    return MagicMock()


@pytest.fixture
def adapter(mock_gateway):
    """Create a OnePanelAdapter with a mocked gateway."""
    with patch.object(OnePanelAdapter, "__init__", lambda self: None):
        adapter = OnePanelAdapter.__new__(OnePanelAdapter)
        object.__setattr__(adapter, "_gw", mock_gateway)
        return adapter
