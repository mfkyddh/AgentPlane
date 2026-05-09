"""StubProvider — minimal plain-Docker provider for contract testing.

This is NOT a production implementation.  It exists solely to prove that
ProviderProtocol is generic enough for a non-1Panel backend.

Every method returns a sensible stub value so that contract tests pass.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class _StubTarget:
    """Opaque target handle — just a label."""

    name: str


@dataclass(frozen=True)
class StubProvider:
    """Minimal provider implementation for plain Docker hosts."""

    def get_target(self, target: str) -> _StubTarget:
        return _StubTarget(name=target)

    def refresh_ledgers(self, repo_root: Path, target: str, *, write: bool) -> dict[str, object]:
        return {"status": "stub", "target": target, "write": write}

    def refresh_app_resource_ledgers(self, repo_root: Path, target: str, *, write: bool) -> dict[str, object]:
        return {"status": "stub", "target": target, "write": write}

    def search_websites(self, tgt: _StubTarget, *, name: str) -> dict[str, Any]:
        return {"total": 0, "items": []}

    def get_website(self, tgt: _StubTarget, *, website_id: int) -> dict[str, Any]:
        return {"id": website_id, "name": "stub-website", "status": "stub"}

    def get_website_ssl(self, tgt: _StubTarget, *, ssl_id: int) -> dict[str, Any]:
        return {"id": ssl_id, "status": "stub"}

    def plan_website_create(
        self, *, alias: str, domain: str, proxy: str, remark: str, ipv6: bool,
    ) -> dict[str, Any]:
        return {
            "object_name": "website",
            "mode": "create",
            "body": {"alias": alias, "domain": domain, "proxy": proxy, "remark": remark, "ipv6": ipv6},
        }

    def search_installed_apps(self, tgt: _StubTarget, *, name: str = "") -> dict[str, Any]:
        return {"total": 0, "items": []}

    def get_installed_app(self, tgt: _StubTarget, *, install_id: int) -> dict[str, Any]:
        return {"id": install_id, "name": "stub-app", "status": "stub"}

    def search_databases(self, tgt: _StubTarget, *, db_type: str = "mysql") -> dict[str, Any]:
        return {"total": 0, "items": []}

    def app_lifecycle_step(
        self,
        repo_root: Path,
        *,
        target: str,
        operate: str,
        rollback_entry: dict[str, Any],
    ) -> tuple[list[str], str]:
        argv = ["echo", f"stub-app-lifecycle:{operate}"]
        return argv, " ".join(argv)

    def project_lifecycle_step(
        self,
        repo_root: Path,
        *,
        target: str,
        operate: str,
        rollback_entry: dict[str, Any],
    ) -> tuple[list[str], str]:
        argv = ["echo", f"stub-project-lifecycle:{operate}"]
        return argv, " ".join(argv)

    def get_dashboard(self, tgt: _StubTarget) -> dict[str, Any]:
        return {
            "cpu": {"used": 0, "total": 100},
            "memory": {"used": 0, "total": 100},
            "load": {"load1": 0, "load5": 0, "load15": 0},
        }
