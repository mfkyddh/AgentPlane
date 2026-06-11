"""Contract resolution and validation for delivery lifecycle."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentplane.domain.app import runtime as app_runtime
from agentplane.domain.app.artifacts import resolve_delivery_contract_spec
from agentplane.domain.app.catalog import resolve_app_contract, resolve_app_entry
from agentplane.domain.app.contracts import validate_contract
from agentplane.domain.app.models import AppCatalogEntry, DeliveryContractSpec


@dataclass(frozen=True)
class ValidatedDeliveryContract:
    app_cli: Any
    contract: dict[str, Any]
    delivery_contract: DeliveryContractSpec
    contract_file: Path
    app: str
    repo_name: str
    app_root: Path
    contract_relpath: str
    catalog_entry: AppCatalogEntry | None


def _resolve_contract_source(
    repo_root: Path,
    *,
    target: str,
    app: str,
    app_repo_root: str | None = None,
    repo_name: str | None = None,
    contract_path: str | None = None,
) -> tuple[AppCatalogEntry | None, str, Path, Path]:
    if app_repo_root:
        resolved_app_root = Path(app_repo_root).expanduser().resolve()
        resolved_repo_name = repo_name or resolved_app_root.name
        resolved_contract = (
            (resolved_app_root / contract_path).resolve()
            if contract_path and not Path(contract_path).is_absolute()
            else Path(contract_path).resolve()
            if contract_path
            else (resolved_app_root / "deploy" / "agentplane" / "contract.yaml").resolve()
        )
        if not resolved_contract.is_file():
            raise ValueError(f"missing onboarding contract file: {resolved_contract}")
        try:
            existing_entry = resolve_app_entry(repo_root, app=app)
        except ValueError:
            existing_entry = None
        try:
            contract_relpath = str(resolved_contract.relative_to(resolved_app_root))
        except ValueError as exc:
            raise ValueError("contract file must stay inside app repo root") from exc
        return existing_entry, resolved_repo_name, resolved_app_root, resolved_contract

    entry, contract_file = resolve_app_contract(repo_root, target=target, app=app)
    contract_relpath = entry.contracts.get(target)
    if not isinstance(contract_relpath, str) or not contract_relpath:
        raise ValueError(f"app catalog missing target mapping: target={target} app={app}")
    return entry, entry.repo_name, entry.repo_root.resolve(), contract_file


def load_validated_delivery_contract(
    repo_root: Path,
    *,
    target: str,
    app: str,
    app_repo_root: str | None = None,
    repo_name: str | None = None,
    contract_path: str | None = None,
) -> ValidatedDeliveryContract:
    catalog_entry, resolved_repo_name, resolved_app_root, resolved_contract = _resolve_contract_source(
        repo_root,
        target=target,
        app=app,
        app_repo_root=app_repo_root,
        repo_name=repo_name,
        contract_path=contract_path,
    )
    contract = validate_contract(resolved_contract, repo_root=repo_root, target=target)
    contract_app = str(contract.get("app_id") or "")
    if contract_app != app:
        raise ValueError(f"contract app_id mismatch: expected {app!r}, got {contract_app!r}")
    try:
        contract_relpath = str(resolved_contract.relative_to(resolved_app_root))
    except ValueError as exc:
        raise ValueError("contract file must stay inside app repo root") from exc
    return ValidatedDeliveryContract(
        app_cli=app_runtime,
        contract=contract,
        delivery_contract=resolve_delivery_contract_spec(contract),
        contract_file=resolved_contract,
        app=app,
        repo_name=resolved_repo_name,
        app_root=resolved_app_root,
        contract_relpath=contract_relpath,
        catalog_entry=catalog_entry,
    )
