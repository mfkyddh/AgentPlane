from __future__ import annotations

from .gateway import ProviderGateway, default_provider_gateway
from .onepanel_adapter import OnePanelAdapter
from .protocol import ProviderProtocol


def get_provider() -> ProviderProtocol:
    """Return the active provider implementation.

    Defaults to OnePanelAdapter.  Override via AGENTPLANE_PROVIDER env var
    (only "onepanel" and "stub" are currently supported).
    """
    import os

    name = os.environ.get("AGENTPLANE_PROVIDER", "onepanel").lower()
    if name == "stub":
        from .stub_provider import StubProvider

        return StubProvider()
    return OnePanelAdapter()


__all__ = [
    "ProviderGateway",
    "ProviderProtocol",
    "default_provider_gateway",
    "get_provider",
]
