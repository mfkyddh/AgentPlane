"""Tests for runtime_build module - build/package/ship pipeline."""

from __future__ import annotations

import importlib
import json
import tempfile
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


def _import_runtime_build():
    """Import runtime_build module lazily to avoid circular imports."""
    mod = importlib.import_module("agentplane.domain.app.runtime_build")
    return (
        mod._maybe_recommended_versions,
        mod._recommended_versions,
        mod.build_artifact,
        mod.package_runtime,
        mod.ship_image,
    )


class TestRecommendedVersions:
    """Tests for _recommended_versions helper."""

    def test_recommended_versions_returns_version_info(self) -> None:
        """Test that _recommended_versions returns version information."""
        _, _recommended_versions, _, _, _ = _import_runtime_build()

        contract = {
            "app_id": "test-app",
            "_meta": {"app_root": "/tmp/test-app"},
            "artifact": {
                "build_command": "echo build",
                "output_path": "dist",
            },
            "packaging": {
                "image_name": "test-app-prod",
                "backend": "native-posix",
            },
        }

        with patch("agentplane.domain.app.runtime_build.recommended_versions") as mock_versions:
            mock_versions.return_value = {
                "upstream_version": "0.1.0",
                "fork_version": "zzz.20260618.v1.gabc1234",
                "delivery_version": "0.1.0+zzz.20260618.v1.gabc1234",
                "image_tag": "0.1.0-zzz.20260618.v1.gabc1234",
                "build_date": "20260618",
                "fork_sequence": 1,
                "git_sha": "abc1234",
            }

            result = _recommended_versions(contract, repo_root=Path("/tmp"))

            assert result["upstream_version"] == "0.1.0"
            assert "fork_version" in result
            assert "delivery_version" in result
            assert "image_tag" in result


class TestMaybeRecommendedVersions:
    """Tests for _maybe_recommended_versions helper."""

    def test_returns_none_on_file_not_found(self) -> None:
        """Test that returns None when VERSION file not found."""
        _maybe_recommended_versions, _, _, _, _ = _import_runtime_build()

        contract = {
            "app_id": "test-app",
            "_meta": {"app_root": "/tmp/nonexistent"},
        }

        with patch("agentplane.domain.app.runtime_build._recommended_versions") as mock:
            mock.side_effect = FileNotFoundError("VERSION not found")

            result = _maybe_recommended_versions(contract, repo_root=Path("/tmp"))

            assert result is None

    def test_returns_none_on_value_error(self) -> None:
        """Test that returns None on ValueError."""
        _maybe_recommended_versions, _, _, _, _ = _import_runtime_build()

        contract = {
            "app_id": "test-app",
            "_meta": {"app_root": "/tmp/test-app"},
        }

        with patch("agentplane.domain.app.runtime_build._recommended_versions") as mock:
            mock.side_effect = ValueError("Invalid version")

            result = _maybe_recommended_versions(contract, repo_root=Path("/tmp"))

            assert result is None

    def test_returns_none_on_json_decode_error(self) -> None:
        """Test that returns None on JSONDecodeError."""
        _maybe_recommended_versions, _, _, _, _ = _import_runtime_build()

        contract = {
            "app_id": "test-app",
            "_meta": {"app_root": "/tmp/test-app"},
        }

        with patch("agentplane.domain.app.runtime_build._recommended_versions") as mock:
            mock.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)

            result = _maybe_recommended_versions(contract, repo_root=Path("/tmp"))

            assert result is None

    def test_returns_version_info_on_success(self) -> None:
        """Test that returns version info on success."""
        _maybe_recommended_versions, _, _, _, _ = _import_runtime_build()

        contract = {
            "app_id": "test-app",
            "_meta": {"app_root": "/tmp/test-app"},
        }

        expected = {
            "upstream_version": "0.1.0",
            "fork_version": "zzz.20260618.v1.gabc1234",
        }

        with patch("agentplane.domain.app.runtime_build._recommended_versions") as mock:
            mock.return_value = expected

            result = _maybe_recommended_versions(contract, repo_root=Path("/tmp"))

            assert result == expected


class TestBuildArtifact:
    """Tests for build_artifact function."""

    def test_raises_on_missing_artifact_output_path(self) -> None:
        """Test that raises ValueError when artifact.output_path is missing."""
        _, _, build_artifact, _, _ = _import_runtime_build()

        contract = {
            "app_id": "test-app",
            "_meta": {"app_root": "/tmp/test-app"},
            "artifact": {
                "build_command": "echo build",
            },
            "packaging": {
                "image_name": "test-app-prod",
                "backend": "native-posix",
            },
        }

        with patch("agentplane.domain.app.runtime_build.require_artifact_first_contract") as mock_require:
            mock_spec = MagicMock()
            mock_spec.artifact.output_path = None
            mock_require.return_value = mock_spec

            with pytest.raises(ValueError, match="artifact.output_path"):
                build_artifact(
                    contract,
                    repo_root=Path("/tmp"),
                    target="wsl",
                    image_tag=None,
                    auto_version=False,
                    dry_run=True,
                )

    def test_dry_run_returns_planned_result(self) -> None:
        """Test that dry_run returns planned result without executing."""
        _, _, build_artifact, _, _ = _import_runtime_build()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app_root = root / "test-app"
            app_root.mkdir()

            contract = {
                "app_id": "test-app",
                "_meta": {"app_root": str(app_root)},
                "artifact": {
                    "build_command": "echo build",
                    "output_path": "dist",
                },
                "packaging": {
                    "image_name": "test-app-prod",
                    "backend": "native-posix",
                },
            }

            with (
                patch("agentplane.domain.app.runtime_build.require_artifact_first_contract") as mock_require,
                patch("agentplane.domain.app.runtime_build.artifact_output_path") as mock_output,
                patch("agentplane.domain.app.runtime_build._maybe_recommended_versions") as mock_versions,
                patch("agentplane.domain.app.runtime._record_app_operation") as mock_record,
                patch("agentplane.domain.app.runtime_build.next_operation_id") as mock_op_id,
            ):
                mock_spec = MagicMock()
                mock_spec.artifact.output_path = "dist"
                mock_spec.packaging.image_name = "test-app-prod"
                mock_spec.packaging.backend = "native-posix"
                mock_require.return_value = mock_spec

                mock_output.return_value = app_root / "dist"
                mock_versions.return_value = None
                mock_record.return_value = {"action": "build-artifact", "result": "planned"}
                mock_op_id.return_value = "op-123"

                result = build_artifact(
                    contract,
                    repo_root=root,
                    target="wsl",
                    image_tag="test-tag",
                    auto_version=False,
                    dry_run=True,
                )

                assert result["dry_run"] is True
                assert "operation" in result
                assert result["packaging"]["image_ref"] == "test-app-prod:test-tag"

    def test_raises_when_auto_version_without_recommended_versions(self) -> None:
        """Test that raises ValueError when auto_version=True but no recommended versions."""
        _, _, build_artifact, _, _ = _import_runtime_build()

        contract = {
            "app_id": "test-app",
            "_meta": {"app_root": "/tmp/test-app"},
            "artifact": {
                "build_command": "echo build",
                "output_path": "dist",
            },
            "packaging": {
                "image_name": "test-app-prod",
                "backend": "native-posix",
            },
        }

        with (
            patch("agentplane.domain.app.runtime_build.require_artifact_first_contract") as mock_require,
            patch("agentplane.domain.app.runtime_build.artifact_output_path") as mock_output,
            patch("agentplane.domain.app.runtime_build._maybe_recommended_versions") as mock_versions,
        ):
            mock_spec = MagicMock()
            mock_spec.artifact.output_path = "dist"
            mock_require.return_value = mock_spec

            mock_output.return_value = Path("/tmp/test-app/dist")
            mock_versions.return_value = None

            with pytest.raises(ValueError, match="无法自动生成版本号"):
                build_artifact(
                    contract,
                    repo_root=Path("/tmp"),
                    target="wsl",
                    image_tag=None,
                    auto_version=True,
                    dry_run=True,
                )


class TestPackageRuntime:
    """Tests for package_runtime function."""

    def test_raises_on_missing_artifact_output_path(self) -> None:
        """Test that raises ValueError when artifact.output_path is missing."""
        _, _, _, package_runtime, _ = _import_runtime_build()

        contract = {
            "app_id": "test-app",
            "_meta": {"app_root": "/tmp/test-app"},
            "artifact": {
                "build_command": "echo build",
            },
            "packaging": {
                "image_name": "test-app-prod",
                "backend": "native-posix",
            },
        }

        with patch("agentplane.domain.app.runtime_build.require_artifact_first_contract") as mock_require:
            mock_spec = MagicMock()
            mock_spec.artifact.output_path = None
            mock_require.return_value = mock_spec

            with pytest.raises(ValueError, match="artifact.output_path"):
                package_runtime(
                    contract,
                    repo_root=Path("/tmp"),
                    target="wsl",
                    image_tag=None,
                    auto_version=False,
                    dry_run=True,
                )

    def test_dry_run_returns_planned_result(self) -> None:
        """Test that dry_run returns planned result without executing."""
        _, _, _, package_runtime, _ = _import_runtime_build()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app_root = root / "test-app"
            app_root.mkdir()
            dist_dir = app_root / "dist"
            dist_dir.mkdir()

            contract = {
                "app_id": "test-app",
                "_meta": {"app_root": str(app_root)},
                "artifact": {
                    "build_command": "echo build",
                    "output_path": "dist",
                },
                "packaging": {
                    "image_name": "test-app-prod",
                    "package_command": "echo package",
                    "backend": "native-posix",
                },
            }

            with (
                patch("agentplane.domain.app.runtime_build.require_artifact_first_contract") as mock_require,
                patch("agentplane.domain.app.runtime_build.artifact_output_path") as mock_output,
                patch("agentplane.domain.app.runtime_build._maybe_recommended_versions") as mock_versions,
                patch("agentplane.domain.app.runtime._record_app_operation") as mock_record,
                patch("agentplane.domain.app.runtime_build.next_operation_id") as mock_op_id,
            ):
                mock_spec = MagicMock()
                mock_spec.artifact.output_path = "dist"
                mock_spec.artifact.runtime_os = "linux"
                mock_spec.artifact.runtime_arch = "amd64"
                mock_spec.packaging.image_name = "test-app-prod"
                mock_spec.packaging.package_command = "echo package"
                mock_spec.packaging.backend = "native-posix"
                mock_require.return_value = mock_spec

                mock_output.return_value = dist_dir
                mock_versions.return_value = None
                mock_record.return_value = {"action": "package-runtime", "result": "planned"}
                mock_op_id.return_value = "op-456"

                result = package_runtime(
                    contract,
                    repo_root=root,
                    target="wsl",
                    image_tag="test-tag",
                    auto_version=False,
                    dry_run=True,
                )

                assert result["dry_run"] is True
                assert "operation" in result
                assert result["image_ref"] == "test-app-prod:test-tag"


class TestShipImage:
    """Tests for ship_image function."""

    def test_raises_when_image_ref_is_none(self) -> None:
        """Test that raises ValueError when image_ref is None."""
        _, _, _, _, ship_image = _import_runtime_build()

        contract = {
            "app_id": "test-app",
            "_meta": {"app_root": "/tmp/test-app"},
        }

        with pytest.raises(ValueError, match="必须显式传入 image_ref"):
            ship_image(
                contract,
                repo_root=Path("/tmp"),
                target="wsl",
                image_ref=None,
                archive_dir=Path("archives"),
                dry_run=True,
            )

    def test_raises_when_image_ref_is_empty(self) -> None:
        """Test that raises ValueError when image_ref is empty string."""
        _, _, _, _, ship_image = _import_runtime_build()

        contract = {
            "app_id": "test-app",
            "_meta": {"app_root": "/tmp/test-app"},
        }

        with pytest.raises(ValueError, match="必须显式传入 image_ref"):
            ship_image(
                contract,
                repo_root=Path("/tmp"),
                target="wsl",
                image_ref="",
                archive_dir=Path("archives"),
                dry_run=True,
            )

    def test_wsl_target_returns_local_result(self) -> None:
        """Test that wsl target returns local-only result."""
        _, _, _, _, ship_image = _import_runtime_build()

        contract = {
            "app_id": "test-app",
            "_meta": {"app_root": "/tmp/test-app"},
        }

        with (
            patch("agentplane.domain.app.runtime._record_app_operation") as mock_record,
            patch("agentplane.domain.app.runtime_build.next_operation_id") as mock_op_id,
        ):
            mock_record.return_value = {"action": "ship-image", "result": "local-only"}
            mock_op_id.return_value = "op-789"

            result = ship_image(
                contract,
                repo_root=Path("/tmp"),
                target="wsl",
                image_ref="test-image:latest",
                archive_dir=Path("archives"),
                dry_run=False,
            )

            assert result["image_ref"] == "test-image:latest"
            assert result["target"] == "wsl"
            assert "archive_path" in result

    def test_dry_run_returns_planned_result(self) -> None:
        """Test that dry_run returns planned result."""
        _, _, _, _, ship_image = _import_runtime_build()

        contract = {
            "app_id": "test-app",
            "_meta": {"app_root": "/tmp/test-app"},
        }

        with (
            patch("agentplane.domain.app.runtime._record_app_operation") as mock_record,
            patch("agentplane.domain.app.runtime_build.next_operation_id") as mock_op_id,
        ):
            mock_record.return_value = {"action": "ship-image", "result": "planned"}
            mock_op_id.return_value = "op-789"

            result = ship_image(
                contract,
                repo_root=Path("/tmp"),
                target="wsl",
                image_ref="test-image:latest",
                archive_dir=Path("archives"),
                dry_run=True,
            )

            assert result["dry_run"] is True
            assert result["image_ref"] == "test-image:latest"


class TestBuildArtifactExecutePath:
    """Tests for build_artifact execute path (dry_run=False)."""

    @contextmanager
    def _build_artifact_patches(self):
        with (
            patch("agentplane.domain.app.runtime_build.require_artifact_first_contract") as mock_require,
            patch("agentplane.domain.app.runtime_build.artifact_output_path") as mock_output,
            patch("agentplane.domain.app.runtime_build._maybe_recommended_versions") as mock_versions,
            patch("agentplane.domain.app.runtime._record_app_operation") as mock_record,
            patch("agentplane.domain.app.runtime_build.next_operation_id") as mock_op_id,
            patch("agentplane.domain.app.runtime._run_linux_backend_command") as mock_run,
        ):
            yield (mock_require, mock_output, mock_versions, mock_record, mock_op_id, mock_run)

    def test_execute_runs_build_command_and_records_operation(self, tmp_path: Path) -> None:
        """Test that execute path runs build command and records operation."""
        _, _, build_artifact, _, _ = _import_runtime_build()
        contract = {"app_id": "test-app", "_meta": {"app_root": str(tmp_path / "app")}}
        output_file = tmp_path / "app" / "dist" / "artifact.tar"
        output_file.parent.mkdir(parents=True)
        output_file.write_bytes(b"x")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        with self._build_artifact_patches() as (
            mock_require, mock_output, mock_versions, mock_record, mock_op_id, mock_run
        ):
            mock_spec = MagicMock()
            mock_spec.artifact.build_command = "echo build"
            mock_spec.artifact.output_path = "dist"
            mock_spec.artifact.runtime_os = "linux"
            mock_spec.artifact.runtime_arch = "amd64"
            mock_spec.packaging.backend = "native-posix"
            mock_spec.packaging.image_name = "test-app-prod"
            mock_spec.packaging.package_command = "docker build -t test ."
            mock_require.return_value = mock_spec
            mock_output.return_value = output_file
            mock_versions.return_value = None
            mock_record.return_value = {"action": "build-artifact", "result": "artifact-built"}
            mock_op_id.return_value = "op-build-1"
            mock_run.return_value = mock_result

            result = build_artifact(
                contract,
                repo_root=tmp_path,
                target="prod0-main",
                image_tag="v1.0.0",
                auto_version=False,
                dry_run=False,
            )

            assert result["artifact"]["output_path"] == str(output_file)
            assert result["packaging"]["image_ref"] == "test-app-prod:v1.0.0"
            assert result["packaging"]["backend"] == "native-posix"
            mock_run.assert_called_once()
            mock_record.assert_called_once()

    def test_execute_raises_when_build_fails(self, tmp_path: Path) -> None:
        """Test that execute path raises ValueError when build command fails."""
        _, _, build_artifact, _, _ = _import_runtime_build()
        contract = {"app_id": "test-app", "_meta": {"app_root": str(tmp_path / "app")}}

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = "build failed"
        mock_result.stderr = ""

        with self._build_artifact_patches() as (
            mock_require, mock_output, mock_versions, mock_record, mock_op_id, mock_run
        ):
            mock_spec = MagicMock()
            mock_spec.artifact.build_command = "echo build"
            mock_spec.artifact.output_path = "dist"
            mock_spec.artifact.runtime_os = "linux"
            mock_spec.artifact.runtime_arch = "amd64"
            mock_spec.packaging.backend = "native-posix"
            mock_spec.packaging.image_name = "test-app-prod"
            mock_spec.packaging.package_command = "docker build -t test ."
            mock_require.return_value = mock_spec
            mock_output.return_value = tmp_path / "out"
            mock_versions.return_value = None
            mock_run.return_value = mock_result

            with pytest.raises(ValueError, match="build failed"):
                build_artifact(
                    contract,
                    repo_root=tmp_path,
                    target="prod0-main",
                    image_tag="v1.0.0",
                    auto_version=False,
                    dry_run=False,
                )

    def test_execute_raises_when_output_not_generated(self, tmp_path: Path) -> None:
        """Test that execute path raises ValueError when artifact output not generated."""
        _, _, build_artifact, _, _ = _import_runtime_build()
        contract = {"app_id": "test-app", "_meta": {"app_root": str(tmp_path / "app")}}

        mock_result = MagicMock()
        mock_result.returncode = 0

        with self._build_artifact_patches() as (
            mock_require, mock_output, mock_versions, mock_record, mock_op_id, mock_run
        ):
            mock_spec = MagicMock()
            mock_spec.artifact.build_command = "echo build"
            mock_spec.artifact.output_path = "dist"
            mock_spec.artifact.runtime_os = "linux"
            mock_spec.artifact.runtime_arch = "amd64"
            mock_spec.packaging.backend = "native-posix"
            mock_spec.packaging.image_name = "test-app-prod"
            mock_spec.packaging.package_command = "docker build -t test ."
            mock_require.return_value = mock_spec
            mock_output.return_value = tmp_path / "missing-out"
            mock_versions.return_value = None
            mock_run.return_value = mock_result

            with pytest.raises(ValueError, match="未生成预期 artifact"):
                build_artifact(
                    contract,
                    repo_root=tmp_path,
                    target="prod0-main",
                    image_tag="v1.0.0",
                    auto_version=False,
                    dry_run=False,
                )

    def test_execute_uses_auto_version_when_flag_set(self, tmp_path: Path) -> None:
        """Test that auto_version=True derives image_tag from recommended_versions."""
        _, _, build_artifact, _, _ = _import_runtime_build()
        contract = {"app_id": "test-app", "_meta": {"app_root": str(tmp_path / "app")}}
        output_file = tmp_path / "app" / "dist" / "artifact.tar"
        output_file.parent.mkdir(parents=True)
        output_file.write_bytes(b"x")

        mock_result = MagicMock()
        mock_result.returncode = 0

        with self._build_artifact_patches() as (
            mock_require, mock_output, mock_versions, mock_record, mock_op_id, mock_run
        ):
            mock_spec = MagicMock()
            mock_spec.artifact.build_command = "echo build"
            mock_spec.artifact.output_path = "dist"
            mock_spec.artifact.runtime_os = "linux"
            mock_spec.artifact.runtime_arch = "amd64"
            mock_spec.packaging.backend = "native-posix"
            mock_spec.packaging.image_name = "test-app-prod"
            mock_spec.packaging.package_command = "docker build -t test ."
            mock_require.return_value = mock_spec
            mock_output.return_value = output_file
            mock_versions.return_value = {
                "image_tag": "auto-1.2.3",
                "upstream_version": "1.2.3",
                "fork_version": "zzz.1",
                "delivery_version": "1.2.3+zzz.1",
                "build_date": "20260622",
                "fork_sequence": 1,
                "git_sha": "abc",
            }
            mock_record.return_value = {"action": "build-artifact", "result": "artifact-built"}
            mock_op_id.return_value = "op-build-auto"
            mock_run.return_value = mock_result

            result = build_artifact(
                contract,
                repo_root=tmp_path,
                target="prod0-main",
                image_tag=None,
                auto_version=True,
                dry_run=False,
            )

            assert result["packaging"]["image_ref"] == "test-app-prod:auto-1.2.3"
            assert result["recommended_versions"]["image_tag"] == "auto-1.2.3"

    def test_auto_version_raises_when_versions_unavailable(self, tmp_path: Path) -> None:
        """Test that auto_version=True raises when _maybe_recommended_versions returns None."""
        _, _, build_artifact, _, _ = _import_runtime_build()
        contract = {"app_id": "test-app", "_meta": {"app_root": str(tmp_path / "app")}}

        with self._build_artifact_patches() as (
            mock_require, mock_output, mock_versions, mock_record, mock_op_id, mock_run
        ):
            mock_spec = MagicMock()
            mock_spec.artifact.build_command = "echo build"
            mock_spec.artifact.output_path = "dist"
            mock_spec.artifact.runtime_os = "linux"
            mock_spec.artifact.runtime_arch = "amd64"
            mock_spec.packaging.backend = "native-posix"
            mock_spec.packaging.image_name = "test-app-prod"
            mock_spec.packaging.package_command = "docker build -t test ."
            mock_require.return_value = mock_spec
            mock_output.return_value = tmp_path / "out"
            mock_versions.return_value = None

            with pytest.raises(ValueError, match="无法自动生成版本号"):
                build_artifact(
                    contract,
                    repo_root=tmp_path,
                    target="prod0-main",
                    image_tag=None,
                    auto_version=True,
                    dry_run=False,
                )


class TestPackageRuntimeExecutePath:
    """Tests for package_runtime execute path (dry_run=False)."""

    @contextmanager
    def _package_runtime_patches(self):
        with (
            patch("agentplane.domain.app.runtime_build.require_artifact_first_contract") as mock_require,
            patch("agentplane.domain.app.runtime_build.artifact_output_path") as mock_output,
            patch("agentplane.domain.app.runtime_build._maybe_recommended_versions") as mock_versions,
            patch("agentplane.domain.app.runtime._record_app_operation") as mock_record,
            patch("agentplane.domain.app.runtime_build.next_operation_id") as mock_op_id,
            patch("agentplane.domain.app.runtime._run_linux_backend_command") as mock_run,
        ):
            yield (mock_require, mock_output, mock_versions, mock_record, mock_op_id, mock_run)

    def _mock_spec(self):
        mock_spec = MagicMock()
        mock_spec.artifact.build_command = "echo build"
        mock_spec.artifact.output_path = "dist"
        mock_spec.artifact.runtime_os = "linux"
        mock_spec.artifact.runtime_arch = "amd64"
        mock_spec.packaging.backend = "native-posix"
        mock_spec.packaging.image_name = "test-app-prod"
        mock_spec.packaging.package_command = "docker build -t test ."
        return mock_spec

    def test_execute_runs_package_command_and_records_operation(self, tmp_path: Path) -> None:
        """Test that execute path runs package command and records operation."""
        _, _, _, package_runtime, _ = _import_runtime_build()
        contract = {"app_id": "test-app", "_meta": {"app_root": str(tmp_path / "app")}}
        output_file = tmp_path / "app" / "dist" / "artifact.tar"
        output_file.parent.mkdir(parents=True)
        output_file.write_bytes(b"x")

        mock_result = MagicMock()
        mock_result.returncode = 0

        with self._package_runtime_patches() as (
            mock_require, mock_output, mock_versions, mock_record, mock_op_id, mock_run
        ):
            mock_require.return_value = self._mock_spec()
            mock_output.return_value = output_file
            mock_versions.return_value = None
            mock_record.return_value = {"action": "package-runtime", "result": "packaged"}
            mock_op_id.return_value = "op-package-1"
            mock_run.return_value = mock_result

            result = package_runtime(
                contract,
                repo_root=tmp_path,
                target="prod0-main",
                image_tag="v1.0.0",
                auto_version=False,
                dry_run=False,
            )

            assert result["image_ref"] == "test-app-prod:v1.0.0"
            assert "operation" in result
            mock_run.assert_called_once()
            mock_record.assert_called_once()

    def test_execute_raises_when_artifact_missing(self, tmp_path: Path) -> None:
        """Test that execute path raises ValueError when artifact not found."""
        _, _, _, package_runtime, _ = _import_runtime_build()
        contract = {"app_id": "test-app", "_meta": {"app_root": str(tmp_path / "app")}}

        with self._package_runtime_patches() as (
            mock_require, mock_output, mock_versions, mock_record, mock_op_id, mock_run
        ):
            mock_require.return_value = self._mock_spec()
            mock_output.return_value = tmp_path / "missing"
            mock_versions.return_value = None

            with pytest.raises(ValueError, match="需要现成 artifact"):
                package_runtime(
                    contract,
                    repo_root=tmp_path,
                    target="prod0-main",
                    image_tag="v1.0.0",
                    auto_version=False,
                    dry_run=False,
                )

    def test_execute_raises_when_package_fails(self, tmp_path: Path) -> None:
        """Test that execute path raises ValueError when package command fails."""
        _, _, _, package_runtime, _ = _import_runtime_build()
        contract = {"app_id": "test-app", "_meta": {"app_root": str(tmp_path / "app")}}
        output_file = tmp_path / "app" / "dist" / "artifact.tar"
        output_file.parent.mkdir(parents=True)
        output_file.write_bytes(b"x")

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = "package failed"
        mock_result.stderr = ""

        with self._package_runtime_patches() as (
            mock_require, mock_output, mock_versions, mock_record, mock_op_id, mock_run
        ):
            mock_require.return_value = self._mock_spec()
            mock_output.return_value = output_file
            mock_versions.return_value = None
            mock_run.return_value = mock_result

            with pytest.raises(ValueError, match="package failed"):
                package_runtime(
                    contract,
                    repo_root=tmp_path,
                    target="prod0-main",
                    image_tag="v1.0.0",
                    auto_version=False,
                    dry_run=False,
                )


class TestShipImageRemoteExecutePath:
    """Tests for ship_image remote execute path (target != wsl, dry_run=False)."""

    def test_remote_execute_streams_image_and_records_operation(self) -> None:
        """Test that remote execute path streams docker image and records operation."""
        _, _, _, _, ship_image = _import_runtime_build()

        contract = {
            "app_id": "test-app",
            "_meta": {"app_root": "/tmp/test-app"},
        }

        mock_stream_result = MagicMock()
        mock_stream_result.ok = True
        mock_stream_result.stderr = ""

        with (
            patch("agentplane.domain.app.runtime._record_app_operation") as mock_record,
            patch("agentplane.domain.app.runtime_build.next_operation_id") as mock_op_id,
            patch("agentplane.domain.app.runtime._target_ssh_target") as mock_ssh,
        ):
            mock_record.return_value = {"action": "ship-image", "result": "loaded"}
            mock_op_id.return_value = "op-ship-1"

            mock_ssh_target = MagicMock()
            mock_ssh_target.connection_target = "user@host"
            mock_ssh.return_value = mock_ssh_target

            result = ship_image(
                contract,
                repo_root=Path("/tmp"),
                target="prod0-main",
                image_ref="test-image:latest",
                archive_dir=Path("archives"),
                dry_run=False,
                _streamer=lambda image, ssh_target: mock_stream_result,
            )

            assert "operation" in result
            assert "commands" in result
            assert result["image_ref"] == "test-image:latest"
            mock_record.assert_called_once()

    def test_remote_execute_raises_when_stream_fails(self) -> None:
        """Test that remote execute path raises ValueError when stream fails."""
        _, _, _, _, ship_image = _import_runtime_build()

        contract = {
            "app_id": "test-app",
            "_meta": {"app_root": "/tmp/test-app"},
        }

        mock_stream_result = MagicMock()
        mock_stream_result.ok = False
        mock_stream_result.stderr = "stream failed"

        with (
            patch("agentplane.domain.app.runtime._target_ssh_target") as mock_ssh,
        ):
            mock_ssh_target = MagicMock()
            mock_ssh_target.connection_target = "user@host"
            mock_ssh.return_value = mock_ssh_target

            with pytest.raises(ValueError, match="stream failed"):
                ship_image(
                    contract,
                    repo_root=Path("/tmp"),
                    target="prod0-main",
                    image_ref="test-image:latest",
                    archive_dir=Path("archives"),
                    dry_run=False,
                    _streamer=lambda image, ssh_target: mock_stream_result,
                )
