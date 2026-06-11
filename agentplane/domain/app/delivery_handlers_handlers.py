"""Simple public delivery handlers — thin delegation wrappers for non-deploy operations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agentplane.domain.app.delivery_handlers_shared import _load_validated_contract
from agentplane.domain.app.lifecycle import offboard_delivery_for_app, onboard_delivery_for_app


def onboard_for_app(
    repo_root: Path,
    *,
    target: str,
    app: str,
    dry_run: bool,
    write: bool,
    app_repo_root: str | None = None,
    repo_name: str | None = None,
    contract_path: str | None = None,
) -> dict[str, Any]:
    payload = onboard_delivery_for_app(
        repo_root,
        target=target,
        app=app,
        dry_run=dry_run,
        write=write,
        app_repo_root=app_repo_root,
        repo_name=repo_name,
        contract_path=contract_path,
    )
    return {"command": "app", "action": "onboard", "target": target, "payload": payload}


def offboard_for_app(
    repo_root: Path,
    *,
    target: str,
    app: str,
    dry_run: bool,
    write: bool,
) -> dict[str, Any]:
    payload = offboard_delivery_for_app(repo_root, target=target, app=app, dry_run=dry_run, write=write)
    return {"command": "app", "action": "offboard", "target": target, "payload": payload}


def validate_contract_for_app(
    repo_root: Path, *, target: str, app: str, app_repo_root: str | None = None
) -> dict[str, Any]:
    app_cli, contract, _ = _load_validated_contract(repo_root, target=target, app=app, app_repo_root=app_repo_root)
    return {"command": "app", "action": "validate-contract", "valid": True, "payload": contract}


def validate_contract_standalone_for_app(
    contract_path: Path,
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Standalone contract validation without inventory dependency."""
    from agentplane.domain.app.contracts import validate_contract_standalone

    contract = validate_contract_standalone(contract_path, repo_root=repo_root)
    return {"command": "app", "action": "validate-contract", "valid": True, "standalone": True, "payload": contract}


def render_runtime_for_app(
    repo_root: Path,
    *,
    target: str,
    app: str,
    image_ref: str | None,
    app_repo_root: str | None = None,
) -> dict[str, Any]:
    app_cli, contract, _ = _load_validated_contract(repo_root, target=target, app=app, app_repo_root=app_repo_root)
    payload = app_cli.render_runtime(contract, repo_root=repo_root, target=target, image_ref=image_ref)
    return {"command": "app", "action": "render-runtime", "payload": payload}


def inventory_refresh_for_app(
    repo_root: Path,
    *,
    target: str,
    app: str,
    write: bool,
    app_repo_root: str | None = None,
) -> dict[str, Any]:
    app_cli, _, contract_file = _load_validated_contract(repo_root, target=target, app=app, app_repo_root=app_repo_root)
    payload = app_cli.inventory_refresh(repo_root=repo_root, target=target, contract_paths=[contract_file], write=write)
    return {"command": "app", "action": "inventory-refresh", "target": target, "payload": payload}


def doc_sync_for_app(
    repo_root: Path,
    *,
    target: str,
    app: str,
    write: bool,
    app_repo_root: str | None = None,
) -> dict[str, Any]:
    app_cli, _, contract_file = _load_validated_contract(repo_root, target=target, app=app, app_repo_root=app_repo_root)
    payload = app_cli.doc_sync(repo_root=repo_root, target=target, contract_paths=[contract_file], write=write)
    return {"command": "app", "action": "doc-sync", "target": target, **payload}


def build_artifact_for_app(
    repo_root: Path,
    *,
    target: str,
    app: str,
    image_tag: str | None,
    auto_version: bool,
    dry_run: bool,
    app_repo_root: str | None = None,
) -> dict[str, Any]:
    app_cli, contract, _ = _load_validated_contract(repo_root, target=target, app=app, app_repo_root=app_repo_root)
    payload = app_cli.build_artifact(
        contract,
        repo_root=repo_root,
        target=target,
        image_tag=image_tag,
        auto_version=auto_version,
        dry_run=dry_run,
    )
    return {"command": "app", "action": "build-artifact", "payload": payload}


def package_runtime_for_app(
    repo_root: Path,
    *,
    target: str,
    app: str,
    image_tag: str | None,
    auto_version: bool,
    dry_run: bool,
    app_repo_root: str | None = None,
) -> dict[str, Any]:
    app_cli, contract, _ = _load_validated_contract(repo_root, target=target, app=app, app_repo_root=app_repo_root)
    payload = app_cli.package_runtime(
        contract,
        repo_root=repo_root,
        target=target,
        image_tag=image_tag,
        auto_version=auto_version,
        dry_run=dry_run,
    )
    return {"command": "app", "action": "package-runtime", "payload": payload}


def ship_image_for_app(
    repo_root: Path,
    *,
    target: str,
    app: str,
    image_ref: str | None,
    archive_dir: Path,
    dry_run: bool,
    app_repo_root: str | None = None,
) -> dict[str, Any]:
    app_cli, contract, _ = _load_validated_contract(repo_root, target=target, app=app, app_repo_root=app_repo_root)
    payload = app_cli.ship_image(
        contract, repo_root=repo_root, target=target, image_ref=image_ref, archive_dir=archive_dir, dry_run=dry_run
    )
    return {"command": "app", "action": "ship-image", "target": target, "payload": payload}
