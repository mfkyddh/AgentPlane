from __future__ import annotations

from .gateway import ProviderGateway
from .onepanel_adapter import OnePanelAdapter
from .protocol import HealthProviderProtocol, InfraOpsProviderProtocol, ProviderProtocol


class UnsupportedProviderProtocol(TypeError):
    """Raised when the active provider does not support the requested protocol."""


def get_provider(protocol: type | None = None) -> ProviderProtocol:
    """Return the active provider implementation.

    Defaults to OnePanelAdapter.  Override via AGENTPLANE_PROVIDER env var
    (only "onepanel" and "stub" are currently supported).

    When *protocol* is given, the returned provider is checked against it
    via ``isinstance`` (requires ``@runtime_checkable``).  If the provider
    does not satisfy the requested protocol, ``UnsupportedProviderProtocol``
    is raised.
    """
    import os

    name = os.environ.get("AGENTPLANE_PROVIDER", "onepanel").lower()
    if name == "stub":
        from .stub_provider import StubProvider

        provider: ProviderProtocol = StubProvider()
    else:
        provider = OnePanelAdapter()

    if protocol is not None and not isinstance(provider, protocol):
        raise UnsupportedProviderProtocol(
            f"Active provider '{name}' does not satisfy {protocol.__name__}"
        )

    return provider


__all__ = [
    "ProviderGateway",
    "ProviderProtocol",
    "HealthProviderProtocol",
    "InfraOpsProviderProtocol",
    "UnsupportedProviderProtocol",
    "get_provider",
]
