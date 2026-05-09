"""Adapter: implements ProviderProtocol by delegating to OnePanelProviderGateway.

This is the bridge between the generic provider interface and the existing
1Panel-specific implementation.  No business logic lives here — pure delegation.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentplane.providers.gateway import OnePanelProviderGateway
from agentplane.providers.protocol import ProviderTarget


@dataclass(frozen=True)
class OnePanelAdapter:
    """Wraps OnePanelProviderGateway to satisfy ProviderProtocol."""

    _gw: OnePanelProviderGateway

    def __init__(self) -> None:
        object.__setattr__(self, "_gw", OnePanelProviderGateway())

    # --- Executor / target ---------------------------------------------------

    def get_target(self, target: str) -> ProviderTarget:
        return self._gw.onepanel_target_executor(target)  # type: ignore[return-value]

    # --- Ledger / projection -------------------------------------------------

    def refresh_ledgers(self, repo_root: Path, target: str, *, write: bool) -> dict[str, object]:
        return self._gw.refresh_onepanel_ledgers(repo_root, target, write=write)

    def refresh_app_resource_ledgers(self, repo_root: Path, target: str, *, write: bool) -> dict[str, object]:
        return self._gw.refresh_app_resource_ledgers(repo_root, target, write=write)

    # --- Website / ingress ---------------------------------------------------

    def search_websites(self, tgt: ProviderTarget, *, name: str) -> dict[str, Any]:
        return self._gw.search_onepanel_websites(tgt, name=name)  # type: ignore[arg-type]

    def get_website(self, tgt: ProviderTarget, *, website_id: int) -> dict[str, Any]:
        return self._gw.get_onepanel_website(tgt, website_id=website_id)  # type: ignore[arg-type]

    def get_website_ssl(self, tgt: ProviderTarget, *, ssl_id: int) -> dict[str, Any]:
        return self._gw.get_onepanel_website_ssl(tgt, ssl_id=ssl_id)  # type: ignore[arg-type]

    def plan_website_create(
        self, *, alias: str, domain: str, proxy: str, remark: str, ipv6: bool,
    ) -> object:
        return self._gw.plan_onepanel_website_create(
            alias=alias, domain=domain, proxy=proxy, remark=remark, ipv6=ipv6,
        )

    # --- App operations ------------------------------------------------------

    def search_installed_apps(self, tgt: ProviderTarget, *, name: str = "") -> dict[str, Any]:
        return self._gw.search_onepanel_installed_apps(tgt, name=name)  # type: ignore[arg-type]

    def get_installed_app(self, tgt: ProviderTarget, *, install_id: int) -> dict[str, Any]:
        return self._gw.get_onepanel_installed_app(tgt, install_id=install_id)  # type: ignore[arg-type]

    def search_databases(self, tgt: ProviderTarget, *, db_type: str = "mysql") -> dict[str, Any]:
        return self._gw.search_onepanel_databases(tgt, db_type=db_type)  # type: ignore[arg-type]

    # --- Lifecycle -----------------------------------------------------------

    def app_lifecycle_step(
        self,
        repo_root: Path,
        *,
        target: str,
        operate: str,
        rollback_entry: dict[str, Any],
    ) -> tuple[list[str], str]:
        return self._gw.onepanel_app_lifecycle_step(
            repo_root, target=target, operate=operate, rollback_entry=rollback_entry,
        )

    def project_lifecycle_step(
        self,
        repo_root: Path,
        *,
        target: str,
        operate: str,
        rollback_entry: dict[str, Any],
    ) -> tuple[list[str], str]:
        return self._gw.onepanel_project_lifecycle_step(
            repo_root, target=target, operate=operate, rollback_entry=rollback_entry,
        )

    # --- Health / monitoring -------------------------------------------------

    def get_dashboard(self, tgt: ProviderTarget) -> dict[str, Any]:
        return self._gw.get_onepanel_dashboard_current(tgt)  # type: ignore[arg-type]
