"""Tests for agentplane.domain.app.artifacts — contract parsing and artifact resolution."""

from __future__ import annotations

from pathlib import Path

import pytest
from agentplane.domain.app.artifacts import (
    SUPPORTED_PACKAGING_BACKENDS,
    artifact_output_path,
    contract_image_name,
    contract_image_tag_rule,
    detect_contract_mode,
    require_artifact_first_contract,
    resolve_delivery_contract_spec,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# detect_contract_mode
# ---------------------------------------------------------------------------


class TestDetectContractMode:
    def test_legacy_no_schema_version(self) -> None:
        assert detect_contract_mode({}) == ("legacy", None)

    def test_v1(self) -> None:
        assert detect_contract_mode({"schema_version": 1}) == ("v1", 1)

    def test_v2(self) -> None:
        assert detect_contract_mode({"schema_version": 2}) == ("v2", 2)

    def test_unsupported_version_raises(self) -> None:
        with pytest.raises(ValueError, match="不受支持"):
            detect_contract_mode({"schema_version": 99})

    def test_unsupported_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="不受支持"):
            detect_contract_mode({"schema_version": -1})


# ---------------------------------------------------------------------------
# resolve_delivery_contract_spec
# ---------------------------------------------------------------------------


class TestResolveDeliveryContractSpec:
    def test_v2_full_contract(self) -> None:
        payload = {
            "schema_version": 2,
            "artifact": {
                "build_command": "go build",
                "output_path": "bin/server",
                "runtime_os": "linux",
                "runtime_arch": "amd64",
            },
            "packaging": {
                "backend": "native-posix",
                "image_name": "myapp",
                "image_tag_rule": "{{.upstream_version}}",
                "package_command": "docker build",
            },
        }
        spec = resolve_delivery_contract_spec(payload)
        assert spec.contract_mode == "v2"
        assert spec.schema_version == 2
        assert spec.artifact.build_command == "go build"
        assert spec.packaging is not None
        assert spec.packaging.backend == "native-posix"

    def test_legacy_minimal(self) -> None:
        spec = resolve_delivery_contract_spec({})
        assert spec.contract_mode == "legacy"
        assert spec.schema_version == "legacy"
        assert spec.artifact.build_command is None
        assert spec.packaging is None

    def test_v1_with_artifact_infers_packaging(self) -> None:
        payload = {
            "schema_version": 1,
            "artifact": {
                "image_name": "myapp",
                "image_tag_rule": "latest",
                "build_command": "make build",
            },
        }
        spec = resolve_delivery_contract_spec(payload)
        assert spec.contract_mode == "v1"
        assert spec.packaging is not None
        assert spec.packaging.image_name == "myapp"
        assert spec.packaging.package_command == "make build"

    def test_non_dict_payload_handled(self) -> None:
        """Non-dict artifact/packaging payloads should be treated as empty."""
        payload = {"artifact": "bad", "packaging": 123}
        spec = resolve_delivery_contract_spec(payload)
        assert spec.artifact.build_command is None


# ---------------------------------------------------------------------------
# contract_image_name / contract_image_tag_rule
# ---------------------------------------------------------------------------


class TestContractImageAccessors:
    def test_image_name_from_v2(self) -> None:
        payload = {
            "schema_version": 2,
            "packaging": {"image_name": "nginx-proxy"},
        }
        assert contract_image_name(payload) == "nginx-proxy"

    def test_image_name_legacy_none(self) -> None:
        assert contract_image_name({}) is None

    def test_image_tag_rule(self) -> None:
        payload = {
            "schema_version": 2,
            "packaging": {"image_tag_rule": "{{.upstream}}-{{.sha}}"},
        }
        assert contract_image_tag_rule(payload) == "{{.upstream}}-{{.sha}}"


# ---------------------------------------------------------------------------
# artifact_output_path
# ---------------------------------------------------------------------------


class TestArtifactOutputPath:
    def test_resolves_relative(self, tmp_path: Path) -> None:
        from agentplane.domain.app.models import DeliveryArtifactSpec

        DeliveryArtifactSpec(
            build_command=None, output_path="bin/server", runtime_os=None, runtime_arch=None,
        )
        result = artifact_output_path(tmp_path, resolve_delivery_contract_spec({
            "schema_version": 2,
            "artifact": {"output_path": "bin/server"},
        }))
        assert result is not None
        assert result.name == "server"

    def test_none_output_path(self) -> None:

        spec = resolve_delivery_contract_spec({"schema_version": 2})
        assert artifact_output_path(Path("/tmp"), spec) is None


# ---------------------------------------------------------------------------
# require_artifact_first_contract
# ---------------------------------------------------------------------------


class TestRequireArtifactFirstContract:
    def test_non_v2_raises(self) -> None:
        with pytest.raises(ValueError, match="仅支持 schema_version: 2"):
            require_artifact_first_contract({"schema_version": 1})

    def test_v2_missing_packaging_fields_raises(self) -> None:
        payload = {
            "schema_version": 2,
            "artifact": {
                "build_command": "go build",
                "output_path": "bin/server",
                "runtime_os": "linux",
                "runtime_arch": "amd64",
            },
        }
        with pytest.raises(ValueError, match="缺少必填字段"):
            require_artifact_first_contract(payload)

    def test_v2_missing_fields_raises(self) -> None:
        payload = {
            "schema_version": 2,
            "artifact": {},
            "packaging": {},
        }
        with pytest.raises(ValueError, match="缺少必填字段"):
            require_artifact_first_contract(payload)

    def test_v2_invalid_backend_raises(self) -> None:
        payload = {
            "schema_version": 2,
            "artifact": {
                "build_command": "go build",
                "output_path": "bin/server",
                "runtime_os": "linux",
                "runtime_arch": "amd64",
            },
            "packaging": {
                "backend": "unsupported-backend",
                "image_name": "myapp",
                "image_tag_rule": "latest",
                "package_command": "docker build",
            },
        }
        with pytest.raises(ValueError, match="packaging.backend 只支持"):
            require_artifact_first_contract(payload)

    def test_v2_valid_contract(self) -> None:
        payload = {
            "schema_version": 2,
            "artifact": {
                "build_command": "go build",
                "output_path": "bin/server",
                "runtime_os": "linux",
                "runtime_arch": "amd64",
            },
            "packaging": {
                "backend": "native-posix",
                "image_name": "myapp",
                "image_tag_rule": "latest",
                "package_command": "docker build",
            },
        }
        spec = require_artifact_first_contract(payload)
        assert spec.contract_mode == "v2"
        assert spec.packaging is not None
        assert spec.packaging.backend == "native-posix"

    def test_all_valid_backends(self) -> None:
        """Every backend in SUPPORTED_PACKAGING_BACKENDS should be accepted."""
        for backend in SUPPORTED_PACKAGING_BACKENDS:
            payload = {
                "schema_version": 2,
                "artifact": {
                    "build_command": "go build",
                    "output_path": "bin/server",
                    "runtime_os": "linux",
                    "runtime_arch": "amd64",
                },
                "packaging": {
                    "backend": backend,
                    "image_name": "myapp",
                    "image_tag_rule": "latest",
                    "package_command": "docker build",
                },
            }
            spec = require_artifact_first_contract(payload)
            assert spec.packaging is not None
            assert spec.packaging.backend == backend


# ---------------------------------------------------------------------------
# Golden test
# ---------------------------------------------------------------------------


@pytest.mark.golden
class TestArtifactsGolden:
    def test_full_v2_roundtrip(self) -> None:
        """Full v2 contract → spec → accessors roundtrip."""
        payload = {
            "schema_version": 2,
            "artifact": {
                "build_command": "cargo build --release",
                "output_path": "target/release/server",
                "runtime_os": "linux",
                "runtime_arch": "arm64",
            },
            "packaging": {
                "backend": "ssh-linux",
                "image_name": "my-service",
                "image_tag_rule": "{{.upstream_version}}-{{.fork_version}}",
                "package_command": "docker buildx build --platform linux/arm64",
            },
        }
        spec = require_artifact_first_contract(payload)
        assert spec.contract_mode == "v2"
        assert spec.artifact.runtime_arch == "arm64"
        assert contract_image_name(payload) == "my-service"
        assert contract_image_tag_rule(payload) == "{{.upstream_version}}-{{.fork_version}}"
