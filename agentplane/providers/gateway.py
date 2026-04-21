from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


class ProviderGateway(Protocol):
    def refresh_onepanel_ledgers(self, repo_root: Path, target: str, *, write: bool) -> dict[str, object]:
        """Refresh provider-owned object ledgers."""

    def refresh_app_resource_ledgers(self, repo_root: Path, target: str, *, write: bool) -> dict[str, object]:
        """Refresh provider-owned app resource ledger projections."""

    def onepanel_target_executor(self, target: str) -> object:
        """Return an executor for the target's 1Panel API surface."""

    def search_onepanel_websites(self, executor: object, *, name: str) -> dict[str, Any]:
        """Search provider websites by name."""

    def get_onepanel_website(self, executor: object, *, website_id: int) -> dict[str, Any]:
        """Fetch a provider website by id."""

    def plan_onepanel_website_create(self, *, alias: str, domain: str, proxy: str, remark: str, ipv6: bool) -> object:
        """Build the provider request object for website creation."""


@dataclass(frozen=True)
class OnePanelProviderGateway:
    def refresh_onepanel_ledgers(self, repo_root: Path, target: str, *, write: bool) -> dict[str, object]:
        from agentplane.scripts.onepanel.ledger import refresh_ledgers

        return refresh_ledgers(repo_root, target, write=write)

    def refresh_app_resource_ledgers(self, repo_root: Path, target: str, *, write: bool) -> dict[str, object]:
        return self.refresh_onepanel_ledgers(repo_root, target, write=write)

    def onepanel_target_executor(self, target: str) -> object:
        from agentplane.scripts.onepanel.env_targets import get_target
        from agentplane.scripts.onepanel.executor import TargetExecutor

        return TargetExecutor(get_target(target))

    def search_onepanel_websites(self, executor: object, *, name: str) -> dict[str, Any]:
        from agentplane.scripts.onepanel.object_api import search_websites

        return search_websites(executor, name=name)

    def get_onepanel_website(self, executor: object, *, website_id: int) -> dict[str, Any]:
        from agentplane.scripts.onepanel.object_api import get_website

        return get_website(executor, website_id=website_id)

    def plan_onepanel_website_create(self, *, alias: str, domain: str, proxy: str, remark: str, ipv6: bool) -> object:
        from agentplane.scripts.onepanel.object_api import plan_website_create

        return plan_website_create(alias=alias, domain=domain, proxy=proxy, remark=remark, ipv6=ipv6)


def default_provider_gateway() -> ProviderGateway:
    return OnePanelProviderGateway()
