from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentplane.domain.app import delivery_handlers


@dataclass(frozen=True)
class AppDeliveryService:
    repo_root: Path

    def validate_contract(self, *, target: str, app: str, app_repo_root: str | None = None) -> dict[str, Any]:
        return delivery_handlers.validate_contract_for_app(
            self.repo_root, target=target, app=app, app_repo_root=app_repo_root
        )

    def render_runtime(
        self, *, target: str, app: str, image_ref: str | None, app_repo_root: str | None = None
    ) -> dict[str, Any]:
        return delivery_handlers.render_runtime_for_app(
            self.repo_root,
            target=target,
            app=app,
            image_ref=image_ref,
            app_repo_root=app_repo_root,
        )

    def inventory_refresh(
        self, *, target: str, app: str, write: bool, app_repo_root: str | None = None
    ) -> dict[str, Any]:
        return delivery_handlers.inventory_refresh_for_app(
            self.repo_root,
            target=target,
            app=app,
            write=write,
            app_repo_root=app_repo_root,
        )

    def doc_sync(self, *, target: str, app: str, write: bool, app_repo_root: str | None = None) -> dict[str, Any]:
        return delivery_handlers.doc_sync_for_app(
            self.repo_root,
            target=target,
            app=app,
            write=write,
            app_repo_root=app_repo_root,
        )

    def build_artifact(
        self,
        *,
        target: str,
        app: str,
        image_tag: str | None,
        auto_version: bool,
        dry_run: bool,
        app_repo_root: str | None = None,
    ) -> dict[str, Any]:
        return delivery_handlers.build_artifact_for_app(
            self.repo_root,
            target=target,
            app=app,
            image_tag=image_tag,
            auto_version=auto_version,
            dry_run=dry_run,
            app_repo_root=app_repo_root,
        )

    def package_runtime(
        self,
        *,
        target: str,
        app: str,
        image_tag: str | None,
        auto_version: bool,
        dry_run: bool,
        app_repo_root: str | None = None,
    ) -> dict[str, Any]:
        return delivery_handlers.package_runtime_for_app(
            self.repo_root,
            target=target,
            app=app,
            image_tag=image_tag,
            auto_version=auto_version,
            dry_run=dry_run,
            app_repo_root=app_repo_root,
        )

    def ship_image(
        self,
        *,
        target: str,
        app: str,
        image_ref: str | None,
        archive_dir: Path,
        dry_run: bool,
        app_repo_root: str | None = None,
    ) -> dict[str, Any]:
        return delivery_handlers.ship_image_for_app(
            self.repo_root,
            target=target,
            app=app,
            image_ref=image_ref,
            archive_dir=archive_dir,
            dry_run=dry_run,
            app_repo_root=app_repo_root,
        )

    def deploy(
        self,
        *,
        target: str,
        app: str,
        image_ref: str | None,
        dry_run: bool,
        execute: bool,
        app_repo_root: str | None = None,
    ) -> dict[str, Any]:
        return delivery_handlers.deploy_for_app(
            self.repo_root,
            target=target,
            app=app,
            image_ref=image_ref,
            dry_run=dry_run,
            execute=execute,
            app_repo_root=app_repo_root,
        )

    def verify(
        self,
        *,
        target: str,
        app: str,
        dry_run: bool,
        execute: bool,
        app_repo_root: str | None = None,
    ) -> dict[str, Any]:
        return delivery_handlers.verify_delivery_for_app(
            self.repo_root,
            target=target,
            app=app,
            dry_run=dry_run,
            execute=execute,
            app_repo_root=app_repo_root,
        )

    def rollback(
        self,
        *,
        target: str,
        app: str,
        dry_run: bool,
        execute: bool,
        app_repo_root: str | None = None,
    ) -> dict[str, Any]:
        return delivery_handlers.rollback_for_app(
            self.repo_root,
            target=target,
            app=app,
            dry_run=dry_run,
            execute=execute,
            app_repo_root=app_repo_root,
        )

    def onboard(
        self,
        *,
        target: str,
        app: str,
        dry_run: bool,
        write: bool,
        app_repo_root: str | None = None,
        repo_name: str | None = None,
        contract_path: str | None = None,
    ) -> dict[str, Any]:
        return delivery_handlers.onboard_for_app(
            self.repo_root,
            target=target,
            app=app,
            dry_run=dry_run,
            write=write,
            app_repo_root=app_repo_root,
            repo_name=repo_name,
            contract_path=contract_path,
        )

    def offboard(self, *, target: str, app: str, dry_run: bool, write: bool) -> dict[str, Any]:
        return delivery_handlers.offboard_for_app(
            self.repo_root,
            target=target,
            app=app,
            dry_run=dry_run,
            write=write,
        )
