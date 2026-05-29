"""Tests for agentplane.domain.app.runtime — pure helper functions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from agentplane.domain.app.runtime import (
    _compose_template_path,
    _default_dependency_env,
    _healthcheck_url,
    _inventory_host_binding,
    _inventory_public_url,
    _is_production_target,
    _load_inventory,
    _origin_health_wait_command,
    _payload_path,
    _port_mapping,
    _prod0_data_env_path,
    _remote_compose_filename,
    _remote_env_parent,
    _remote_env_path,
    _runtime_base_url,
    _runtime_container_name,
    _service_env_path,
    _split_host_binding,
    _target_alias,
    _target_config_files,
    _target_dependency_names,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# _is_production_target
# ---------------------------------------------------------------------------


class TestIsProductionTarget:
    def test_prod0(self) -> None:
        assert _is_production_target("prod0-main") is True

    def test_wsl(self) -> None:
        assert _is_production_target("wsl") is False

    def test_unknown(self) -> None:
        assert _is_production_target("staging") is False


# ---------------------------------------------------------------------------
# _target_alias
# ---------------------------------------------------------------------------


class TestTargetAlias:
    def test_wsl(self) -> None:
        assert _target_alias("wsl") == "wsl"

    def test_prod0(self) -> None:
        assert _target_alias("prod0-main") == "prod0"


# ---------------------------------------------------------------------------
# _remote_compose_filename
# ---------------------------------------------------------------------------


class TestRemoteComposeFilename:
    def test_wsl(self) -> None:
        assert _remote_compose_filename("wsl") == "docker-compose.wsl.yml"

    def test_prod0(self) -> None:
        assert _remote_compose_filename("prod0-main") == "docker-compose.prod0.yml"


# ---------------------------------------------------------------------------
# _prod0_data_env_path
# ---------------------------------------------------------------------------


class TestProd0DataEnvPath:
    def test_sub2api(self) -> None:
        result = _prod0_data_env_path("sub2api")
        assert result == "/data/sub2api/config/sub2api-prod.env"

    def test_sub2api_with_candidate(self) -> None:
        result = _prod0_data_env_path("sub2api", candidate_suffix="abc")
        assert "candidate.abc" in result

    def test_non_sub2api(self) -> None:
        assert _prod0_data_env_path("myapp") is None


# ---------------------------------------------------------------------------
# _remote_env_path
# ---------------------------------------------------------------------------


class TestRemoteEnvPath:
    def test_wsl(self) -> None:
        result = _remote_env_path("myapp", "wsl")
        assert result == "/opt/agentplane/secrets/services/myapp.wsl.env"

    def test_prod0_sub2api(self) -> None:
        result = _remote_env_path("sub2api", "prod0-main")
        assert "/data/sub2api/" in result

    def test_prod0_non_sub2api(self) -> None:
        result = _remote_env_path("myapp", "prod0-main")
        assert "myapp.prod0.env" in result

    def test_with_candidate(self) -> None:
        result = _remote_env_path("myapp", "wsl", candidate_suffix="v1")
        assert "candidate.v1" in result


# ---------------------------------------------------------------------------
# _remote_env_parent
# ---------------------------------------------------------------------------


class TestRemoteEnvParent:
    def test_parent(self) -> None:
        assert _remote_env_parent("/opt/secrets/services/app.env") == "/opt/secrets/services"

    def test_root_path(self) -> None:
        assert _remote_env_parent("/app.env") == "/"


# ---------------------------------------------------------------------------
# _payload_path
# ---------------------------------------------------------------------------


class TestPayloadPath:
    def test_posix_path(self) -> None:
        assert _payload_path("/opt/secrets/app.env") == "/opt/secrets/app.env"

    def test_windows_path(self) -> None:
        result = _payload_path("D:\\Projects\\test")
        # Windows paths with drive letter are kept as-is
        assert "D:" in result

    def test_relative_backslash(self) -> None:
        result = _payload_path("some\\path")
        assert "\\" not in result or ":" in result


# ---------------------------------------------------------------------------
# _load_inventory
# ---------------------------------------------------------------------------


class TestLoadInventory:
    def test_valid(self, tmp_path: Path) -> None:
        inv_dir = tmp_path / "inventory" / "servers" / "wsl"
        inv_dir.mkdir(parents=True)
        inv_file = inv_dir / "inventory.json"
        inv_file.write_text('{"hostname": "test"}', encoding="utf-8")
        path, data = _load_inventory(tmp_path, "wsl")
        assert data["hostname"] == "test"

    def test_missing(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="缺少 inventory"):
            _load_inventory(tmp_path, "wsl")

    def test_non_dict(self, tmp_path: Path) -> None:
        inv_dir = tmp_path / "inventory" / "servers" / "wsl"
        inv_dir.mkdir(parents=True)
        inv_file = inv_dir / "inventory.json"
        inv_file.write_text('"string"', encoding="utf-8")
        with pytest.raises(ValueError, match="顶层必须是对象"):
            _load_inventory(tmp_path, "wsl")


# ---------------------------------------------------------------------------
# _split_host_binding
# ---------------------------------------------------------------------------


class TestSplitHostBinding:
    def test_with_ip(self) -> None:
        host, port = _split_host_binding("127.0.0.1:8080")
        assert host == "127.0.0.1"
        assert port == "8080"

    def test_without_host(self) -> None:
        host, port = _split_host_binding(":8080")
        assert host == "127.0.0.1"
        assert port == "8080"

    def test_custom_host(self) -> None:
        host, port = _split_host_binding("0.0.0.0:3000")
        assert host == "0.0.0.0"
        assert port == "3000"

    def test_invalid_no_port(self) -> None:
        with pytest.raises(ValueError, match="格式不合法"):
            _split_host_binding("127.0.0.1")

    def test_invalid_empty(self) -> None:
        with pytest.raises(ValueError, match="格式不合法"):
            _split_host_binding("")

    def test_only_colon(self) -> None:
        with pytest.raises(ValueError, match="格式不合法"):
            _split_host_binding(":")


# ---------------------------------------------------------------------------
# _port_mapping
# ---------------------------------------------------------------------------


class TestPortMapping:
    def test_wsl(self) -> None:
        runtime: dict[str, Any] = {"host_binding": "127.0.0.1:8080", "container_port": 8080}
        result = _port_mapping(runtime, target="wsl")
        assert result == "0.0.0.0:8080:8080"

    def test_production(self) -> None:
        runtime: dict[str, Any] = {"host_binding": "127.0.0.1:3000", "container_port": 3000}
        result = _port_mapping(runtime, target="prod0-main")
        assert result == "127.0.0.1:3000:3000"

    def test_different_ports(self) -> None:
        runtime: dict[str, Any] = {"host_binding": "0.0.0.0:9090", "container_port": 80}
        result = _port_mapping(runtime, target="wsl")
        assert result == "0.0.0.0:9090:80"


# ---------------------------------------------------------------------------
# _runtime_base_url
# ---------------------------------------------------------------------------


class TestRuntimeBaseUrl:
    def test_wsl(self) -> None:
        runtime: dict[str, Any] = {"host_binding": "127.0.0.1:8080"}
        result = _runtime_base_url(runtime, target="wsl")
        assert result == "http://127.0.0.1:8080"

    def test_production_returns_empty(self) -> None:
        runtime: dict[str, Any] = {"host_binding": "127.0.0.1:8080"}
        result = _runtime_base_url(runtime, target="prod0-main")
        assert result == ""


# ---------------------------------------------------------------------------
# _runtime_container_name
# ---------------------------------------------------------------------------


class TestRuntimeContainerName:
    def test_wsl(self) -> None:
        runtime: dict[str, Any] = {"container_name": "myapp-prod"}
        result = _runtime_container_name("myapp", runtime, target="wsl")
        assert result == "myapp-dev"

    def test_production(self) -> None:
        runtime: dict[str, Any] = {"container_name": "myapp-prod"}
        result = _runtime_container_name("myapp", runtime, target="prod0-main")
        assert result == "myapp-prod"


# ---------------------------------------------------------------------------
# _inventory_host_binding
# ---------------------------------------------------------------------------


class TestInventoryHostBinding:
    def test_wsl(self) -> None:
        runtime: dict[str, Any] = {"host_binding": "127.0.0.1:8080"}
        result = _inventory_host_binding(runtime, target="wsl")
        assert result == "0.0.0.0:8080"

    def test_production(self) -> None:
        runtime: dict[str, Any] = {"host_binding": "127.0.0.1:3000"}
        result = _inventory_host_binding(runtime, target="prod0-main")
        assert result == "127.0.0.1:3000"


# ---------------------------------------------------------------------------
# _target_dependency_names
# ---------------------------------------------------------------------------


class TestTargetDependencyNames:
    def test_wsl_transforms_prod_to_dev(self) -> None:
        result = _target_dependency_names(["postgres-prod", "redis-prod"], target="wsl")
        assert result == ["postgres-dev", "redis-dev"]

    def test_wsl_keeps_non_prod(self) -> None:
        result = _target_dependency_names(["postgres-dev", "redis"], target="wsl")
        assert result == ["postgres-dev", "redis"]

    def test_wsl_mixed(self) -> None:
        result = _target_dependency_names(["postgres-prod", "redis"], target="wsl")
        assert result == ["postgres-dev", "redis"]

    def test_non_wsl_passthrough(self) -> None:
        result = _target_dependency_names(["postgres-prod", "redis-prod"], target="prod0-main")
        assert result == ["postgres-prod", "redis-prod"]

    def test_empty(self) -> None:
        assert _target_dependency_names([], target="wsl") == []


# ---------------------------------------------------------------------------
# _healthcheck_url
# ---------------------------------------------------------------------------


class TestHealthcheckUrl:
    def test_wsl(self) -> None:
        contract: dict[str, Any] = {
            "runtime": {
                "host_binding": "127.0.0.1:8080",
                "healthcheck": {"path": "/health"},
            }
        }
        result = _healthcheck_url(contract, target="wsl")
        assert result == "http://127.0.0.1:8080/health"

    def test_non_wsl_with_public_sites(self) -> None:
        contract: dict[str, Any] = {
            "runtime": {
                "host_binding": "127.0.0.1:8080",
                "healthcheck": {"path": "/health"},
            },
            "ingress": {
                "public_sites": [
                    {"alias": "myapp", "public_url": "https://myapp.example.com"}
                ]
            },
        }
        result = _healthcheck_url(contract, target="prod0-main")
        assert result == "https://myapp.example.com/health"

    def test_non_wsl_no_public_sites(self) -> None:
        contract: dict[str, Any] = {
            "runtime": {
                "host_binding": "127.0.0.1:9090",
                "healthcheck": {"path": "/ping"},
            }
        }
        result = _healthcheck_url(contract, target="prod0-main")
        assert result == "http://127.0.0.1:9090/ping"


# ---------------------------------------------------------------------------
# _origin_health_wait_command
# ---------------------------------------------------------------------------


class TestOriginHealthWaitCommand:
    def test_basic(self) -> None:
        contract: dict[str, Any] = {
            "runtime": {
                "host_binding": "127.0.0.1:8080",
                "healthcheck": {"path": "/health"},
            }
        }
        result = _origin_health_wait_command(contract, container_name="myapp-dev")
        assert "myapp-dev" in result
        assert "127.0.0.1:8080/health" in result
        assert "docker inspect" in result
        assert "seq 1 12" in result


# ---------------------------------------------------------------------------
# _inventory_public_url
# ---------------------------------------------------------------------------


class TestInventoryPublicUrl:
    def test_wsl(self) -> None:
        contract: dict[str, Any] = {
            "runtime": {"host_binding": "127.0.0.1:8080"}
        }
        result = _inventory_public_url(contract, target="wsl")
        assert result == "http://127.0.0.1:8080"

    def test_non_wsl_with_public_ingress(self) -> None:
        contract: dict[str, Any] = {
            "runtime": {"host_binding": "127.0.0.1:8080"},
            "ingress": {
                "public_sites": [
                    {"alias": "myapp", "public_url": "https://myapp.example.com"}
                ]
            },
        }
        result = _inventory_public_url(contract, target="prod0-main")
        assert result == "https://myapp.example.com"

    def test_non_wsl_no_public_ingress(self) -> None:
        contract: dict[str, Any] = {
            "runtime": {"host_binding": "127.0.0.1:8080"},
            "ingress": {"mode": "internal"},
        }
        result = _inventory_public_url(contract, target="prod0-main")
        assert result == "internal://127.0.0.1:8080"


# ---------------------------------------------------------------------------
# _default_dependency_env
# ---------------------------------------------------------------------------


class TestDefaultDependencyEnv:
    def test_with_postgres_and_redis(self) -> None:
        contract: dict[str, Any] = {
            "infra": {
                "tenant_resources": {
                    "postgres": {},
                    "redis": {},
                }
            }
        }
        result = _default_dependency_env(["postgres-prod", "redis-prod"], contract, target="wsl")
        assert result["DATABASE_HOST"] == "postgres-dev"
        assert result["REDIS_HOST"] == "redis-dev"

    def test_postgres_only(self) -> None:
        contract: dict[str, Any] = {
            "infra": {"tenant_resources": {"postgres": {}}}
        }
        result = _default_dependency_env(["postgres-prod"], contract, target="wsl")
        assert "DATABASE_HOST" in result
        assert "REDIS_HOST" not in result

    def test_no_tenant_resources(self) -> None:
        contract: dict[str, Any] = {}
        assert _default_dependency_env(["postgres-prod"], contract, target="wsl") == {}

    def test_empty_depends(self) -> None:
        contract: dict[str, Any] = {
            "infra": {"tenant_resources": {"postgres": {}, "redis": {}}}
        }
        result = _default_dependency_env([], contract, target="wsl")
        assert result == {}

    def test_non_wsl_passthrough(self) -> None:
        contract: dict[str, Any] = {
            "infra": {"tenant_resources": {"postgres": {}}}
        }
        result = _default_dependency_env(["postgres-prod"], contract, target="prod0-main")
        assert result["DATABASE_HOST"] == "postgres-prod"


# ---------------------------------------------------------------------------
# _compose_template_path
# ---------------------------------------------------------------------------


class TestComposeTemplatePath:
    def test_wsl(self, tmp_path: Path) -> None:
        result = _compose_template_path(tmp_path, "myapp", target="wsl")
        assert result == tmp_path / "infra" / "compose" / "myapp" / "docker-compose.wsl.yml"

    def test_production(self, tmp_path: Path) -> None:
        result = _compose_template_path(tmp_path, "myapp", target="prod0-main")
        assert result == tmp_path / "infra" / "compose" / "myapp" / "docker-compose.prod0.yml"


# ---------------------------------------------------------------------------
# _service_env_path
# ---------------------------------------------------------------------------


class TestServiceEnvPath:
    def test_wsl(self, tmp_path: Path) -> None:
        result = _service_env_path(tmp_path, "myapp", "wsl")
        assert result.name == "myapp.wsl.env"
        assert "services" in result.parts

    def test_production(self, tmp_path: Path) -> None:
        result = _service_env_path(tmp_path, "myapp", "prod0-main")
        assert result.name == "myapp.prod0.env"
        assert "services" in result.parts

    def test_unsupported_target(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="Unsupported target"):
            _service_env_path(tmp_path, "myapp", "unknown")


# ---------------------------------------------------------------------------
# _target_config_files
# ---------------------------------------------------------------------------


class TestTargetConfigFiles:
    def test_wsl(self, tmp_path: Path) -> None:
        runtime: dict[str, Any] = {}
        result = _target_config_files(tmp_path, "myapp", runtime, target="wsl")
        assert len(result) == 1
        assert "myapp.wsl.env" in result[0]

    def test_sub2api_prod0(self, tmp_path: Path) -> None:
        runtime: dict[str, Any] = {}
        result = _target_config_files(tmp_path, "sub2api", runtime, target="prod0-main")
        assert len(result) == 1
        assert "/data/sub2api/config/sub2api-prod.env" == result[0]

    def test_other_app_prod0_with_config_files(self, tmp_path: Path) -> None:
        runtime: dict[str, Any] = {"config_files": ["/opt/custom/app.env"]}
        result = _target_config_files(tmp_path, "myapp", runtime, target="prod0-main")
        assert result == ["/opt/custom/app.env"]

    def test_other_app_prod0_fallback(self, tmp_path: Path) -> None:
        runtime: dict[str, Any] = {}
        result = _target_config_files(tmp_path, "myapp", runtime, target="prod0-main")
        assert len(result) == 1
        assert "myapp.prod0.env" in result[0]


# ---------------------------------------------------------------------------
# Golden test
# ---------------------------------------------------------------------------


@pytest.mark.golden
class TestRuntimeHelpersGolden:
    def test_full_remote_env_roundtrip(self) -> None:
        """Remote env path for sub2api on prod0 with candidate suffix."""
        path = _remote_env_path("sub2api", "prod0-main", candidate_suffix="deploy-42")
        assert "/data/sub2api/" in path
        assert "candidate.deploy-42" in path
        parent = _remote_env_parent(path)
        assert parent.endswith("config")

    def test_full_runtime_roundtrip(self) -> None:
        """Complete runtime config with host_binding, container_port, healthcheck."""
        runtime: dict[str, Any] = {
            "host_binding": "127.0.0.1:8080",
            "container_port": 8080,
            "container_name": "myapp-prod",
        }
        contract: dict[str, Any] = {
            "runtime": {
                **runtime,
                "healthcheck": {"path": "/health"},
            },
            "infra": {
                "tenant_resources": {"postgres": {}, "redis": {}},
            },
            "ingress": {
                "public_sites": [
                    {"alias": "myapp", "public_url": "https://myapp.example.com"},
                ]
            },
        }

        # Split
        host, port = _split_host_binding(runtime["host_binding"])
        assert host == "127.0.0.1"
        assert port == "8080"

        # WSL path
        assert _port_mapping(runtime, target="wsl") == "0.0.0.0:8080:8080"
        assert _runtime_base_url(runtime, target="wsl") == "http://127.0.0.1:8080"
        assert _runtime_container_name("myapp", runtime, target="wsl") == "myapp-dev"
        assert _inventory_host_binding(runtime, target="wsl") == "0.0.0.0:8080"
        assert _inventory_public_url(contract, target="wsl") == "http://127.0.0.1:8080"

        # Production path
        assert _port_mapping(runtime, target="prod0-main") == "127.0.0.1:8080:8080"
        assert _runtime_base_url(runtime, target="prod0-main") == ""
        assert _runtime_container_name("myapp", runtime, target="prod0-main") == "myapp-prod"

        # Dependencies
        depends = ["postgres-prod", "redis-prod"]
        assert _target_dependency_names(depends, target="wsl") == ["postgres-dev", "redis-dev"]
        assert _target_dependency_names(depends, target="prod0-main") == depends

        env = _default_dependency_env(depends, contract, target="wsl")
        assert env["DATABASE_HOST"] == "postgres-dev"
        assert env["REDIS_HOST"] == "redis-dev"

        # Healthcheck
        health = _healthcheck_url(contract, target="wsl")
        assert health == "http://127.0.0.1:8080/health"

        wait_cmd = _origin_health_wait_command(contract, container_name="myapp-dev")
        assert "myapp-dev" in wait_cmd
        assert "127.0.0.1:8080/health" in wait_cmd
