"""Tests for agentplane.domain.app.lifecycle — pure helper functions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from agentplane.domain.app.lifecycle import (
    _canonical_secret_files,
    _catalog_step_payload,
    _ingress_sites,
    _record_step,
    _resource_registry_path,
    _secret_files_from_registry_entry,
)
from agentplane.domain.app.truth_lifecycle import CatalogMutationResult

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# _record_step
# ---------------------------------------------------------------------------


class TestRecordStep:
    def test_basic(self) -> None:
        result = _record_step("test.action", write=True, ok=True, changed=False, payload={"key": "val"})
        assert result["action"] == "test.action"
        assert result["write"] is True
        assert result["ok"] is True
        assert result["changed"] is False
        assert result["payload"]["key"] == "val"


# ---------------------------------------------------------------------------
# _ingress_sites
# ---------------------------------------------------------------------------


class TestIngressSites:
    def test_top_level(self) -> None:
        contract: dict[str, Any] = {"public_sites": [{"alias": "a"}, {"alias": "b"}]}
        sites = _ingress_sites(contract)
        assert len(sites) == 2

    def test_nested(self) -> None:
        contract: dict[str, Any] = {"ingress": {"public_sites": [{"alias": "x"}]}}
        sites = _ingress_sites(contract)
        assert len(sites) == 1

    def test_none(self) -> None:
        assert _ingress_sites({}) == []

    def test_non_dict_filtered(self) -> None:
        contract: dict[str, Any] = {"public_sites": [{"alias": "a"}, "invalid", 42]}
        sites = _ingress_sites(contract)
        assert len(sites) == 1


# ---------------------------------------------------------------------------
# _canonical_secret_files
# ---------------------------------------------------------------------------


class TestCanonicalSecretFiles:
    def test_sorted(self) -> None:
        result = _canonical_secret_files(target="wsl", app="myapp", tenant_resources={"redis": {}, "postgres": {}})
        assert len(result) == 2
        assert result == sorted(result)

    def test_empty(self) -> None:
        assert _canonical_secret_files(target="wsl", app="myapp", tenant_resources={}) == []


# ---------------------------------------------------------------------------
# _resource_registry_path
# ---------------------------------------------------------------------------


class TestResourceRegistryPath:
    def test_path(self, tmp_path: Path) -> None:
        result = _resource_registry_path(tmp_path, "wsl")
        assert result == tmp_path / "inventory" / "servers" / "wsl" / "app-resources.json"


# ---------------------------------------------------------------------------
# _secret_files_from_registry_entry
# ---------------------------------------------------------------------------


class TestSecretFilesFromRegistryEntry:
    def test_from_entry(self) -> None:
        entry: dict[str, Any] = {"secret_files": ["path/a.env", "path/b.env"]}
        result = _secret_files_from_registry_entry(entry, target="wsl", app="myapp")
        assert result == ["path/a.env", "path/b.env"]

    def test_fallback(self) -> None:
        result = _secret_files_from_registry_entry(None, target="wsl", app="myapp", tenant_resources={"postgres": {}})
        assert len(result) == 1

    def test_empty_entry(self) -> None:
        result = _secret_files_from_registry_entry({}, target="wsl", app="myapp", tenant_resources={})
        assert result == []


# ---------------------------------------------------------------------------
# _catalog_step_payload
# ---------------------------------------------------------------------------


class TestCatalogStepPayload:
    def test_with_entry(self) -> None:
        from agentplane.domain.app.models import AppCatalogEntry

        entry = AppCatalogEntry(
            app="myapp", repo_name="repo", repo_root=Path("/tmp/repo"), service_key="myapp", contracts={"wsl": "c.yaml"}
        )
        result = CatalogMutationResult(path=Path("/tmp/catalog.json"), before_count=0, after_count=1, entry=entry, changed=True)
        payload = _catalog_step_payload(result)
        assert payload["before_count"] == 0
        assert payload["after_count"] == 1
        assert payload["entry"]["app"] == "myapp"

    def test_without_entry(self) -> None:
        result = CatalogMutationResult(path=Path("/tmp/catalog.json"), before_count=1, after_count=0, entry=None, changed=True)
        payload = _catalog_step_payload(result)
        assert payload["entry"] is None


# ---------------------------------------------------------------------------
# Golden test
# ---------------------------------------------------------------------------


@pytest.mark.golden
class TestLifecycleHelpersGolden:
    def test_full_record_step_roundtrip(self) -> None:
        """Full step record with all fields populated."""
        step = _record_step(
            "app.delivery.onboard.catalog",
            write=True,
            ok=True,
            changed=True,
            payload={"path": "/tmp/catalog.json", "before_count": 0, "after_count": 1},
        )
        assert step["action"] == "app.delivery.onboard.catalog"
        assert step["write"] is True
        assert step["payload"]["after_count"] == 1

        # Ingress sites from contract
        contract: dict[str, Any] = {
            "public_sites": [
                {"alias": "myapp", "domain": "myapp.example.com", "public_url": "https://myapp.example.com"},
            ]
        }
        sites = _ingress_sites(contract)
        assert sites[0]["alias"] == "myapp"
