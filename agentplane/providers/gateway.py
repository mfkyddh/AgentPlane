from __future__ import annotations

import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from agentplane.providers.onepanel_ledgers import refresh_onepanel_ledgers
from agentplane.providers.onepanel_objects import (
    get_ingress,
    onepanel_target_executor,
    plan_website_create,
    search_ingresses,
)


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

    def onepanel_app_lifecycle_step(
        self,
        repo_root: Path,
        *,
        target: str,
        operate: str,
        rollback_entry: dict[str, Any],
    ) -> tuple[list[str], str]:
        """Build a provider-owned 1Panel app lifecycle command step."""

    def onepanel_project_lifecycle_step(
        self,
        repo_root: Path,
        *,
        target: str,
        operate: str,
        rollback_entry: dict[str, Any],
    ) -> tuple[list[str], str]:
        """Build a provider-owned 1Panel compose lifecycle command step."""


@dataclass(frozen=True)
class OnePanelProviderGateway:
    def refresh_onepanel_ledgers(self, repo_root: Path, target: str, *, write: bool) -> dict[str, object]:
        return refresh_onepanel_ledgers(repo_root, target, write=write)

    def refresh_app_resource_ledgers(self, repo_root: Path, target: str, *, write: bool) -> dict[str, object]:
        return self.refresh_onepanel_ledgers(repo_root, target, write=write)

    def onepanel_target_executor(self, target: str) -> object:
        return onepanel_target_executor(target)

    def search_onepanel_websites(self, executor: object, *, name: str) -> dict[str, Any]:
        return search_ingresses(executor, name=name)

    def get_onepanel_website(self, executor: object, *, website_id: int) -> dict[str, Any]:
        return get_ingress(executor, website_id=website_id)

    def plan_onepanel_website_create(self, *, alias: str, domain: str, proxy: str, remark: str, ipv6: bool) -> object:
        return plan_website_create(alias=alias, domain=domain, proxy=proxy, remark=remark, ipv6=ipv6)

    def onepanel_app_lifecycle_step(
        self,
        repo_root: Path,
        *,
        target: str,
        operate: str,
        rollback_entry: dict[str, Any],
    ) -> tuple[list[str], str]:
        argv = [
            "uv",
            "run",
            "python",
            "-m",
            "agentplane.providers.onepanel_transition",
            "--target",
            target,
            "app",
            "--operate",
            operate,
        ]
        install_id = rollback_entry.get("install_id")
        app_key = rollback_entry.get("app_key")
        if install_id is not None:
            argv.extend(["--install-id", str(install_id)])
        elif isinstance(app_key, str) and app_key:
            argv.extend(["--name", app_key])
        else:
            raise ValueError(f"rollback.previous_control_plane.kind=1panel-app 缺少 install_id/app_key: {rollback_entry}")
        return argv, " ".join(shlex.quote(part) for part in argv)

    def onepanel_project_lifecycle_step(
        self,
        repo_root: Path,
        *,
        target: str,
        operate: str,
        rollback_entry: dict[str, Any],
    ) -> tuple[list[str], str]:
        project_name = rollback_entry.get("project_name")
        if not isinstance(project_name, str) or not project_name:
            raise ValueError(f"rollback.previous_control_plane.kind=1panel-compose 缺少 project_name: {rollback_entry}")
        argv = [
            "uv",
            "run",
            "python",
            "-m",
            "agentplane.providers.onepanel_transition",
            "--target",
            target,
            "project",
            "--name",
            project_name,
            "--operate",
            operate,
        ]
        return argv, " ".join(shlex.quote(part) for part in argv)


def default_provider_gateway() -> ProviderGateway:
    return OnePanelProviderGateway()
