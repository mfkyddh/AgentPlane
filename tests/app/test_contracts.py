"""Tests for agentplane.domain.app.contracts — pure helper functions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from agentplane.domain.app.contracts import (
    _contract_error,
    _inventory_container_names,
    _registry_entry_for_declared_kinds,
    _required_tenant_resource_errors,
    _tenant_dependency_kinds,
    _validate_previous_control_plane,
    contract_app_root,
    contract_validation_target,
    has_public_ingress,
    ingress_mode,
    nested_get,
    public_sites,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# _contract_error
# ---------------------------------------------------------------------------


class TestContractError:
    def test_creates_value_error(self) -> None:
        err = _contract_error("app.test", "something broke")
        assert isinstance(err, ValueError)
        assert "app.test" in str(err)
        assert "something broke" in str(err)


# ---------------------------------------------------------------------------
# contract_app_root
# ---------------------------------------------------------------------------


class TestContractAppRoot:
    def test_deploy_op_path(self, tmp_path: Path) -> None:
        deploy_dir = tmp_path / "deploy" / "op"
        deploy_dir.mkdir(parents=True)
        contract = deploy_dir / "contract.yaml"
        contract.write_text("app_id: test", encoding="utf-8")
        result = contract_app_root(contract)
        assert result == tmp_path

    def test_deploy_agentplane_path(self, tmp_path: Path) -> None:
        deploy_dir = tmp_path / "deploy" / "agentplane"
        deploy_dir.mkdir(parents=True)
        contract = deploy_dir / "contract.yaml"
        contract.write_text("app_id: test", encoding="utf-8")
        result = contract_app_root(contract)
        assert result == tmp_path

    def test_plain_path(self, tmp_path: Path) -> None:
        contract = tmp_path / "contract.yaml"
        contract.write_text("app_id: test", encoding="utf-8")
        result = contract_app_root(contract)
        assert result == tmp_path


# ---------------------------------------------------------------------------
# contract_validation_target
# ---------------------------------------------------------------------------


class TestContractValidationTarget:
    def test_passthrough(self) -> None:
        assert contract_validation_target("wsl") == "wsl"
        assert contract_validation_target("prod0-main") == "prod0-main"


# ---------------------------------------------------------------------------
# nested_get
# ---------------------------------------------------------------------------


class TestNestedGet:
    def test_simple_key(self) -> None:
        assert nested_get({"a": 1}, "a") == 1

    def test_dotted_key(self) -> None:
        assert nested_get({"a": {"b": 2}}, "a.b") == 2

    def test_missing_key(self) -> None:
        assert nested_get({"a": 1}, "b") is None

    def test_missing_nested(self) -> None:
        assert nested_get({"a": {"b": 2}}, "a.c") is None

    def test_non_dict_intermediate(self) -> None:
        assert nested_get({"a": "string"}, "a.b") is None

    def test_deep_nesting(self) -> None:
        payload = {"a": {"b": {"c": {"d": 42}}}}
        assert nested_get(payload, "a.b.c.d") == 42

    def test_empty_key(self) -> None:
        # Empty string split gives [""], which won't match
        assert nested_get({"a": 1}, "") is None


# ---------------------------------------------------------------------------
# ingress_mode
# ---------------------------------------------------------------------------


class TestIngressMode:
    def test_no_ingress(self) -> None:
        assert ingress_mode({}) == "public"

    def test_ingress_no_mode(self) -> None:
        assert ingress_mode({"ingress": {}}) == "public"

    def test_ingress_empty_mode(self) -> None:
        assert ingress_mode({"ingress": {"mode": ""}}) == "public"

    def test_ingress_private(self) -> None:
        assert ingress_mode({"ingress": {"mode": "private"}}) == "private"

    def test_ingress_non_dict(self) -> None:
        assert ingress_mode({"ingress": "bad"}) == "public"


# ---------------------------------------------------------------------------
# public_sites
# ---------------------------------------------------------------------------


class TestPublicSites:
    def test_no_ingress(self) -> None:
        assert public_sites({}) == []

    def test_no_public_sites(self) -> None:
        assert public_sites({"ingress": {}}) == []

    def test_non_list_public_sites(self) -> None:
        assert public_sites({"ingress": {"public_sites": "bad"}}) == []

    def test_valid_public_sites(self) -> None:
        sites = [{"domain": "example.com", "port": 80}]
        assert public_sites({"ingress": {"public_sites": sites}}) == sites


# ---------------------------------------------------------------------------
# has_public_ingress
# ---------------------------------------------------------------------------


class TestHasPublicIngress:
    def test_public_by_default(self) -> None:
        assert has_public_ingress({}) is True

    def test_internal_mode(self) -> None:
        assert has_public_ingress({"ingress": {"mode": "internal"}}) is False

    def test_private_mode(self) -> None:
        assert has_public_ingress({"ingress": {"mode": "private"}}) is True


# ---------------------------------------------------------------------------
# _inventory_container_names
# ---------------------------------------------------------------------------


class TestInventoryContainerNames:
    def test_valid_services(self) -> None:
        payload: dict[str, Any] = {
            "services": {
                "myapp": {"container_name": "myapp-dev"},
                "redis": {"container_name": "redis-dev"},
            }
        }
        names = _inventory_container_names(payload)
        assert names == {"myapp-dev", "redis-dev"}

    def test_empty_services(self) -> None:
        assert _inventory_container_names({}) == set()

    def test_non_dict_services(self) -> None:
        assert _inventory_container_names({"services": "bad"}) == set()

    def test_non_dict_service_entry(self) -> None:
        payload: dict[str, Any] = {"services": {"myapp": "invalid"}}
        assert _inventory_container_names(payload) == set()

    def test_missing_container_name(self) -> None:
        payload: dict[str, Any] = {"services": {"myapp": {"other": "val"}}}
        assert _inventory_container_names(payload) == set()


# ---------------------------------------------------------------------------
# _validate_previous_control_plane
# ---------------------------------------------------------------------------


class TestValidatePreviousControlPlane:
    def test_none_kind(self) -> None:
        _validate_previous_control_plane({"kind": "none"})

    def test_systemd_valid(self) -> None:
        _validate_previous_control_plane({"kind": "systemd", "service_name": "myapp"})

    def test_systemd_missing_service_name(self) -> None:
        with pytest.raises(ValueError, match="service_name"):
            _validate_previous_control_plane({"kind": "systemd"})

    def test_1panel_app_with_install_id(self) -> None:
        _validate_previous_control_plane({"kind": "1panel-app", "install_id": 42})

    def test_1panel_app_with_app_key(self) -> None:
        _validate_previous_control_plane({"kind": "1panel-app", "app_key": "myapp"})

    def test_1panel_app_missing_both(self) -> None:
        with pytest.raises(ValueError, match="install_id"):
            _validate_previous_control_plane({"kind": "1panel-app"})

    def test_1panel_compose_valid(self) -> None:
        _validate_previous_control_plane({"kind": "1panel-compose", "project_name": "proj"})

    def test_1panel_compose_missing_project_name(self) -> None:
        with pytest.raises(ValueError, match="project_name"):
            _validate_previous_control_plane({"kind": "1panel-compose"})

    def test_1panel_compose_bad_field(self) -> None:
        with pytest.raises(ValueError, match="container_name"):
            _validate_previous_control_plane({"kind": "1panel-compose", "project_name": "p", "container_name": ""})

    def test_unknown_kind(self) -> None:
        with pytest.raises(ValueError, match="不支持"):
            _validate_previous_control_plane({"kind": "unknown"})

    def test_non_dict(self) -> None:
        with pytest.raises(ValueError, match="必须是对象"):
            _validate_previous_control_plane("invalid")


# ---------------------------------------------------------------------------
# _tenant_dependency_kinds
# ---------------------------------------------------------------------------


class TestTenantDependencyKinds:
    def test_infers_from_container_name(self) -> None:
        inventory: dict[str, Any] = {
            "services": {
                "postgres-main": {"container_name": "pg-dev"},
                "redis-main": {"container_name": "redis-dev"},
            }
        }
        kinds = _tenant_dependency_kinds(["pg-dev", "redis-dev"], inventory)
        assert kinds == {"postgres", "redis"}

    def test_infers_from_dep_name(self) -> None:
        kinds = _tenant_dependency_kinds(["postgres-prod", "redis-prod"], {})
        assert kinds == {"postgres", "redis"}

    def test_minio(self) -> None:
        kinds = _tenant_dependency_kinds(["minio-prod"], {})
        assert kinds == {"minio"}

    def test_unknown_dep(self) -> None:
        kinds = _tenant_dependency_kinds(["something-else"], {})
        assert kinds == set()

    def test_empty(self) -> None:
        assert _tenant_dependency_kinds([], {}) == set()


# ---------------------------------------------------------------------------
# _required_tenant_resource_errors
# ---------------------------------------------------------------------------


class TestRequiredTenantResourceErrors:
    def test_no_required(self) -> None:
        assert _required_tenant_resource_errors("myapp", set(), {}) == []

    def test_all_present(self) -> None:
        resources: dict[str, Any] = {"postgres": {}, "redis": {}}
        assert _required_tenant_resource_errors("myapp", {"postgres", "redis"}, resources) == []

    def test_missing_resources_dict(self) -> None:
        errors = _required_tenant_resource_errors("myapp", {"postgres"}, None)
        assert len(errors) == 1
        assert "missing infra.tenant_resources" in errors[0]

    def test_missing_kind(self) -> None:
        errors = _required_tenant_resource_errors("myapp", {"postgres", "redis"}, {"postgres": {}})
        assert len(errors) == 1
        assert "redis" in errors[0]


# ---------------------------------------------------------------------------
# _registry_entry_for_declared_kinds
# ---------------------------------------------------------------------------


class TestRegistryEntryForDeclaredKinds:
    def test_filters_kinds(self) -> None:
        entry: dict[str, Any] = {
            "owner_app": "myapp",
            "postgres": {"database": "db"},
            "redis": {"db": 1},
            "minio": {"bucket": "b"},
        }
        result = _registry_entry_for_declared_kinds(entry, kinds_to_check={"postgres", "redis"})
        assert "postgres" in result
        assert "redis" in result
        assert "minio" not in result
        assert result["owner_app"] == "myapp"

    def test_empty_kinds(self) -> None:
        entry: dict[str, Any] = {"owner_app": "myapp"}
        result = _registry_entry_for_declared_kinds(entry, kinds_to_check=set())
        assert result["owner_app"] == "myapp"
        assert result["secret_files"] == []


# ---------------------------------------------------------------------------
# Golden test
# ---------------------------------------------------------------------------


@pytest.mark.golden
class TestContractsGolden:
    def test_nested_get_roundtrip(self) -> None:
        """Full dotted path traversal with mixed types."""
        payload = {
            "runtime": {
                "container_name": "myapp",
                "container_port": 8080,
                "healthcheck": {"path": "/health"},
            },
            "ingress": {
                "mode": "private",
                "public_sites": [{"domain": "app.example.com"}],
            },
        }
        assert nested_get(payload, "runtime.container_name") == "myapp"
        assert nested_get(payload, "runtime.healthcheck.path") == "/health"
        assert nested_get(payload, "ingress.mode") == "private"
        assert nested_get(payload, "ingress.public_sites") == [{"domain": "app.example.com"}]
        assert nested_get(payload, "runtime.missing") is None
        assert ingress_mode(payload) == "private"
        assert len(public_sites(payload)) == 1
