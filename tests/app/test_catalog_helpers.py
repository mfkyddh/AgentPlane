"""Tests for agentplane.domain.app.catalog — pure helper functions."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from agentplane.domain.app.catalog import (
    _catalog_file,
    _coerce_catalog_repo_root,
    _normalize_repo_root_for_current_host,
    _resolved_contract_reference,
    _runtime_contract_relpaths,
    _runtime_repo_root_from_item,
)
from agentplane.domain.app.models import AppCatalogEntry

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# _catalog_file
# ---------------------------------------------------------------------------


class TestCatalogFile:
    def test_path(self, tmp_path: Path) -> None:
        result = _catalog_file(tmp_path)
        assert result == tmp_path / "inventory" / "apps" / "catalog.json"


# ---------------------------------------------------------------------------
# _normalize_repo_root_for_current_host
# ---------------------------------------------------------------------------


class TestNormalizeRepoRoot:
    def test_posix_passthrough(self) -> None:
        result = _normalize_repo_root_for_current_host("/opt/repos/myapp")
        # On Windows, POSIX paths may be converted to UNC paths
        if os.name == "nt":
            assert "repos" in result.lower() or "myapp" in result.lower()
        else:
            assert result == "/opt/repos/myapp"

    def test_empty(self) -> None:
        assert _normalize_repo_root_for_current_host("") == ""

    def test_windows_path(self) -> None:
        result = _normalize_repo_root_for_current_host("D:\\Projects\\myapp")
        assert result == "D:\\Projects\\myapp"


# ---------------------------------------------------------------------------
# _coerce_catalog_repo_root
# ---------------------------------------------------------------------------


class TestCoerceCatalogRepoRoot:
    def test_returns_path(self) -> None:
        result = _coerce_catalog_repo_root("/opt/repos/myapp")
        assert isinstance(result, Path)

    def test_expanduser(self) -> None:
        result = _coerce_catalog_repo_root("~/myapp")
        assert "~" not in str(result)


# ---------------------------------------------------------------------------
# _runtime_repo_root_from_item
# ---------------------------------------------------------------------------


class TestRuntimeRepoRootFromItem:
    def test_with_repo_root_value(self, tmp_path: Path) -> None:
        result = _runtime_repo_root_from_item(
            tmp_path, app="myapp", repo_name="myrepo", repo_ref_value=None, repo_root_value=str(tmp_path / "sub")
        )
        assert result.is_absolute()

    def test_relative_repo_root(self, tmp_path: Path) -> None:
        sub = tmp_path / "sub"
        sub.mkdir()
        result = _runtime_repo_root_from_item(
            tmp_path, app="myapp", repo_name="myrepo", repo_ref_value=None, repo_root_value="sub"
        )
        assert result == (tmp_path / "sub").resolve()

    def test_no_locator_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="missing repo locator"):
            _runtime_repo_root_from_item(
                tmp_path, app="myapp", repo_name="myrepo", repo_ref_value=None, repo_root_value=None
            )

    def test_empty_repo_root_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="missing repo locator"):
            _runtime_repo_root_from_item(
                tmp_path, app="myapp", repo_name="myrepo", repo_ref_value=None, repo_root_value=""
            )


# ---------------------------------------------------------------------------
# _runtime_contract_relpaths
# ---------------------------------------------------------------------------


class TestRuntimeContractRelpaths:
    def test_plain_relpath(self) -> None:
        result = _runtime_contract_relpaths("myapp", {"wsl": "contracts/wsl.yaml"})
        assert result["wsl"] == "contracts/wsl.yaml"

    def test_empty_value_skipped(self) -> None:
        result = _runtime_contract_relpaths("myapp", {"wsl": ""})
        assert "wsl" not in result

    def test_empty_key_skipped(self) -> None:
        result = _runtime_contract_relpaths("myapp", {"": "value"})
        assert "" not in result


# ---------------------------------------------------------------------------
# _resolved_contract_reference
# ---------------------------------------------------------------------------


class TestResolvedContractReference:
    def test_returns_resolved_reference(self, tmp_path: Path) -> None:
        entry = AppCatalogEntry(
            app="myapp",
            repo_name="myrepo",
            repo_root=tmp_path,
            service_key="myapp",
            contracts={"wsl": "contracts/wsl.yaml"},
        )
        ref = _resolved_contract_reference(entry, target="wsl", contract_rel="contracts/wsl.yaml")
        assert ref.canonical_ref
        assert ref.resolved_path


# ---------------------------------------------------------------------------
# Golden test
# ---------------------------------------------------------------------------


@pytest.mark.golden
class TestCatalogHelpersGolden:
    def test_full_catalog_roundtrip(self, tmp_path: Path) -> None:
        """Catalog file path, coerce, and contract relpaths all consistent."""
        cf = _catalog_file(tmp_path)
        assert cf.name == "catalog.json"
        assert "inventory" in cf.parts

        relpaths = _runtime_contract_relpaths("sub2api", {"wsl": "contracts/wsl.yaml", "prod0-main": "contracts/prod0.yaml"})
        assert len(relpaths) == 2
        assert "wsl" in relpaths
        assert "prod0-main" in relpaths
