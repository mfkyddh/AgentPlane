"""Tests for agentplane.domain.infra.audit — pure helper functions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from agentplane.domain.infra.audit import (
    _as_list,
    _duplicate_json_key_paths,
    _find_legacy_flat_secret_references,
    _formal_app_services,
    _host_path_exists,
    _host_path_is_symlink,
    _inventory_compose_service_names,
    _openresty_declared_public_ports,
    _sub2api_inventory_entry,
    _violation,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# _violation
# ---------------------------------------------------------------------------


class TestViolation:
    def test_basic(self) -> None:
        v = _violation("wsl", "rule.1", "message")
        assert v["scope"] == "wsl"
        assert v["id"] == "rule.1"
        assert v["severity"] == "error"
        assert v["message"] == "message"
        assert "path" not in v
        assert "details" not in v

    def test_with_path(self, tmp_path: Path) -> None:
        p = tmp_path / "file.txt"
        v = _violation("wsl", "rule.1", "msg", path=p)
        assert v["path"] == str(p)

    def test_with_details(self) -> None:
        v = _violation("wsl", "rule.1", "msg", details={"key": "val"})
        assert v["details"] == {"key": "val"}


# ---------------------------------------------------------------------------
# _as_list
# ---------------------------------------------------------------------------


class TestAsList:
    def test_list(self) -> None:
        assert _as_list([1, 2, 3]) == [1, 2, 3]

    def test_none(self) -> None:
        assert _as_list(None) == []

    def test_string(self) -> None:
        assert _as_list("bad") == []

    def test_dict(self) -> None:
        assert _as_list({"a": 1}) == []

    def test_empty_list(self) -> None:
        assert _as_list([]) == []


# ---------------------------------------------------------------------------
# _sub2api_inventory_entry
# ---------------------------------------------------------------------------


class TestSub2apiInventoryEntry:
    def test_modern_entry(self) -> None:
        services: dict[str, Any] = {"sub2api": {"host": "127.0.0.1", "port": 8080}}
        result = _sub2api_inventory_entry(services)
        assert result["host"] == "127.0.0.1"

    def test_legacy_entry(self) -> None:
        services: dict[str, Any] = {"token_backend": {"host": "10.0.0.1"}}
        result = _sub2api_inventory_entry(services)
        assert result["host"] == "10.0.0.1"

    def test_empty_services(self) -> None:
        assert _sub2api_inventory_entry({}) == {}

    def test_modern_empty_dict_falls_back(self) -> None:
        services: dict[str, Any] = {"sub2api": {}, "token_backend": {"host": "legacy"}}
        result = _sub2api_inventory_entry(services)
        assert result["host"] == "legacy"


# ---------------------------------------------------------------------------
# _inventory_compose_service_names
# ---------------------------------------------------------------------------


class TestInventoryComposeServiceNames:
    def test_missing_file(self, tmp_path: Path) -> None:
        assert _inventory_compose_service_names(tmp_path / "nope.json", target="wsl") == set()

    def test_invalid_json(self, tmp_path: Path) -> None:
        f = tmp_path / "inventory.json"
        f.write_text("not json", encoding="utf-8")
        assert _inventory_compose_service_names(f, target="wsl") == set()

    def test_wsl_all_services(self, tmp_path: Path) -> None:
        f = tmp_path / "inventory.json"
        f.write_text('{"services": {"postgres": {}, "redis": {}}}', encoding="utf-8")
        result = _inventory_compose_service_names(f, target="wsl")
        assert result == {"postgres", "redis"}

    def test_prod0_only_compose(self, tmp_path: Path) -> None:
        f = tmp_path / "inventory.json"
        f.write_text(
            '{"services": {"postgres": {"control_plane": "compose"}, "redis": {"control_plane": "systemd"}}}',
            encoding="utf-8",
        )
        result = _inventory_compose_service_names(f, target="prod0-main")
        assert result == {"postgres"}

    def test_non_dict_services(self, tmp_path: Path) -> None:
        f = tmp_path / "inventory.json"
        f.write_text('{"services": "bad"}', encoding="utf-8")
        assert _inventory_compose_service_names(f, target="wsl") == set()


# ---------------------------------------------------------------------------
# _host_path_exists / _host_path_is_symlink
# ---------------------------------------------------------------------------


class TestHostPathHelpers:
    def test_exists_file(self, tmp_path: Path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("x", encoding="utf-8")
        assert _host_path_exists(f) is True

    def test_exists_missing(self, tmp_path: Path) -> None:
        assert _host_path_exists(tmp_path / "nope") is False

    def test_symlink_file(self, tmp_path: Path) -> None:
        assert _host_path_is_symlink(tmp_path / "nope") is False

    def test_symlink_actual(self, tmp_path: Path) -> None:
        target = tmp_path / "target.txt"
        target.write_text("x", encoding="utf-8")
        link = tmp_path / "link.txt"
        link.symlink_to(target)
        assert _host_path_is_symlink(link) is True


# ---------------------------------------------------------------------------
# _find_legacy_flat_secret_references
# ---------------------------------------------------------------------------


class TestFindLegacyFlatSecretReferences:
    def test_empty(self) -> None:
        assert _find_legacy_flat_secret_references({}) == []

    def test_dict_recursive(self) -> None:
        node = {"key": "some flat secret ref"}
        refs = _find_legacy_flat_secret_references(node)
        assert isinstance(refs, list)

    def test_list_recursive(self) -> None:
        node = ["item1", "item2"]
        refs = _find_legacy_flat_secret_references(node)
        assert isinstance(refs, list)

    def test_non_container(self) -> None:
        assert _find_legacy_flat_secret_references(42) == []
        assert _find_legacy_flat_secret_references(None) == []


# ---------------------------------------------------------------------------
# _duplicate_json_key_paths
# ---------------------------------------------------------------------------


class TestDuplicateJsonKeyPaths:
    def test_no_duplicates(self) -> None:
        assert _duplicate_json_key_paths('{"a": 1, "b": 2}') == set()

    def test_duplicate_key(self) -> None:
        result = _duplicate_json_key_paths('{"a": 1, "a": 2}')
        assert "a" in result

    def test_invalid_json(self) -> None:
        assert _duplicate_json_key_paths("not json") == set()

    def test_nested_duplicate(self) -> None:
        result = _duplicate_json_key_paths('{"x": {"a": 1, "a": 2}}')
        assert "x.a" in result


# ---------------------------------------------------------------------------
# _formal_app_services
# ---------------------------------------------------------------------------


class TestFormalAppServices:
    def test_valid_services(self) -> None:
        services: dict[str, Any] = {
            "myapp": {
                "container_name": "myapp-dev",
                "control_plane": "compose",
                "depends_on_containers": ["postgres-dev", "redis-dev"],
            },
        }
        result = _formal_app_services(services)
        assert "myapp" in result

    def test_missing_depends(self) -> None:
        services: dict[str, Any] = {
            "myapp": {"container_name": "myapp-dev", "control_plane": "compose"},
        }
        result = _formal_app_services(services)
        assert "myapp" not in result

    def test_depends_without_resource_kind(self) -> None:
        services: dict[str, Any] = {
            "myapp": {
                "control_plane": "compose",
                "depends_on_containers": ["other-service"],
            },
        }
        result = _formal_app_services(services)
        assert "myapp" not in result

    def test_non_dict_service(self) -> None:
        services: dict[str, Any] = {"myapp": "invalid"}
        result = _formal_app_services(services)
        assert "myapp" not in result

    def test_empty(self) -> None:
        assert _formal_app_services({}) == {}


# ---------------------------------------------------------------------------
# _openresty_declared_public_ports
# ---------------------------------------------------------------------------


class TestOpenrestyDeclaredPublicPorts:
    def test_security_ports(self) -> None:
        payload: dict[str, Any] = {
            "security": {"openresty_public_listen": {"ports": [80, 443]}},
        }
        security, service, declared = _openresty_declared_public_ports(payload)
        assert security == [80, 443]
        assert service == []
        assert declared == [80, 443]

    def test_service_ports_fallback(self) -> None:
        payload: dict[str, Any] = {
            "services": {"onepanel_openresty": {"listen_ports": [8080]}},
        }
        security, service, declared = _openresty_declared_public_ports(payload)
        assert security == []
        assert service == [8080]
        assert declared == [8080]

    def test_empty(self) -> None:
        security, service, declared = _openresty_declared_public_ports({})
        assert security == []
        assert service == []
        assert declared == []

    def test_security_takes_priority(self) -> None:
        payload: dict[str, Any] = {
            "security": {"openresty_public_listen": {"ports": [443]}},
            "services": {"onepanel_openresty": {"listen_ports": [8080]}},
        }
        security, service, declared = _openresty_declared_public_ports(payload)
        assert declared == [443]


# ---------------------------------------------------------------------------
# Golden test
# ---------------------------------------------------------------------------


@pytest.mark.golden
class TestAuditGolden:
    def test_violation_with_all_fields(self, tmp_path: Path) -> None:
        """Violation with path and details renders correctly."""
        p = tmp_path / "some" / "path"
        v = _violation(
            "prod0-main",
            "prod0.legacy.marker",
            "Found forbidden marker",
            path=p,
            details={"marker": "nginx-ui"},
        )
        assert v["scope"] == "prod0-main"
        assert v["id"] == "prod0.legacy.marker"
        assert v["severity"] == "error"
        assert v["path"] == str(p)
        assert v["details"]["marker"] == "nginx-ui"
