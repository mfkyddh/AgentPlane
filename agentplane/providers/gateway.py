from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shlex
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

    def onepanel_app_lifecycle_step(
        self,
        repo_root: Path,
        *,
        target: str,
        operate: str,
        rollback_entry: dict[str, Any],
    ) -> tuple[list[str], str]:
        package_root = Path(__file__).resolve().parents[2]
        script_path = package_root / "agentplane" / "scripts" / "onepanel" / "app_lifecycle.py"
        argv = [
            "python3",
            str(script_path),
            "--env",
            target,
            operate,
        ]
        install_id = rollback_entry.get("install_id")
        app_key = rollback_entry.get("app_key")
        if install_id is not None:
            argv.extend(["--install-id", str(install_id)])
        elif isinstance(app_key, str) and app_key:
            argv.extend(["--app", app_key])
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
        package_root = Path(__file__).resolve().parents[2]
        script_path = package_root / "agentplane" / "scripts" / "onepanel" / "project_lifecycle.py"
        argv = [
            "python3",
            str(script_path),
            "--env",
            target,
            "operate",
            "--name",
            project_name,
            "--operation",
            operate,
        ]
        return argv, " ".join(shlex.quote(part) for part in argv)


def default_provider_gateway() -> ProviderGateway:
    return OnePanelProviderGateway()
