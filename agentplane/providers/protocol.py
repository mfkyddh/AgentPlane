"""Generic provider protocol — domain-neutral, not tied to any specific provider (e.g. 1Panel).

Implementations:
  - OnePanelAdapter  (wraps existing OnePanelProviderGateway)
  - StubProvider      (minimal plain-Docker stub for contract testing)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class ProviderTarget(Protocol):
    """Opaque handle returned by the provider for targeting API calls.

    In 1Panel this is a ``TargetExecutor``; other providers may use
    a different mechanism.  Callers must not assume any specific type.
    """

    ...


class ProviderProtocol(Protocol):
    """Provider-agnostic interface for infrastructure operations.

    Design constraints (from foundation-replan v3):
    - Method count ≤ 15 (abort threshold)
    - No provider-specific naming (no ``onepanel_*`` prefixes)
    - Parameters use primitive types or domain-neutral objects
    """

    # --- Executor / target ---------------------------------------------------

    def get_target(self, target: str) -> ProviderTarget:
        """Return an opaque target handle for subsequent API calls."""

    # --- Ledger / projection -------------------------------------------------

    def refresh_ledgers(self, repo_root: Path, target: str, *, write: bool) -> dict[str, object]:
        """Refresh provider-owned object ledgers."""

    def refresh_app_resource_ledgers(self, repo_root: Path, target: str, *, write: bool) -> dict[str, object]:
        """Refresh provider-owned app resource ledger projections."""

    # --- Website / ingress ---------------------------------------------------

    def search_websites(self, tgt: ProviderTarget, *, name: str) -> dict[str, Any]:
        """Search websites / ingress rules by name."""

    def get_website(self, tgt: ProviderTarget, *, website_id: int) -> dict[str, Any]:
        """Fetch a website / ingress rule by id."""

    def get_website_ssl(self, tgt: ProviderTarget, *, ssl_id: int) -> dict[str, Any]:
        """Fetch SSL certificate detail for a website."""

    def plan_website_create(
        self, *, alias: str, domain: str, proxy: str, remark: str, ipv6: bool,
    ) -> object:
        """Build a provider request object for website creation."""

    # --- App operations ------------------------------------------------------

    def search_installed_apps(self, tgt: ProviderTarget, *, name: str = "") -> dict[str, Any]:
        """Search installed apps by name."""

    def get_installed_app(self, tgt: ProviderTarget, *, install_id: int) -> dict[str, Any]:
        """Fetch an installed app by id."""

    def search_databases(self, tgt: ProviderTarget, *, db_type: str = "mysql") -> dict[str, Any]:
        """Search databases by type."""

    # --- Lifecycle -----------------------------------------------------------

    def app_lifecycle_step(
        self,
        repo_root: Path,
        *,
        target: str,
        operate: str,
        rollback_entry: dict[str, Any],
    ) -> tuple[list[str], str]:
        """Build a provider-owned app lifecycle command step (argv, display)."""

    def project_lifecycle_step(
        self,
        repo_root: Path,
        *,
        target: str,
        operate: str,
        rollback_entry: dict[str, Any],
    ) -> tuple[list[str], str]:
        """Build a provider-owned compose/project lifecycle command step."""

    # --- Health / monitoring -------------------------------------------------

    def get_dashboard(self, tgt: ProviderTarget) -> dict[str, Any]:
        """Fetch current dashboard metrics (CPU, memory, load, disk, network)."""
