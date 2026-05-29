"""Tests for agentplane.domain.infra.secrets — pure helper functions."""

from __future__ import annotations

from pathlib import Path

import pytest
from agentplane.domain.infra.secrets import (
    _canonical_backup_source_dir,
    _enforce_env_value,
    _host_infra_secret_file,
    _host_truth_root,
    _legacy_backup_env_path,
    _legacy_minio_secret_file,
    _legacy_onepanel_env_path,
    _legacy_postgres_secret_file,
    _legacy_redis_secret_file,
    _legacy_runtime_env_path,
    _normalize_backup_env_text,
    _target_alias,
    _write_secret_file,
    copy_template_file,
    summarize_secret_file,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# _target_alias
# ---------------------------------------------------------------------------


class TestTargetAlias:
    def test_wsl(self) -> None:
        assert _target_alias("wsl") == "wsl"

    def test_prod0(self) -> None:
        assert _target_alias("prod0-main") == "prod0"


# ---------------------------------------------------------------------------
# _enforce_env_value
# ---------------------------------------------------------------------------


class TestEnforceEnvValue:
    def test_updates_existing(self) -> None:
        content = "KEY=old\nOTHER=val\n"
        result = _enforce_env_value(content, "KEY", "new")
        assert "KEY=new" in result
        assert "KEY=old" not in result

    def test_appends_missing(self) -> None:
        content = "OTHER=val\n"
        result = _enforce_env_value(content, "KEY", "new")
        assert "KEY=new" in result

    def test_trailing_newline(self) -> None:
        result = _enforce_env_value("A=1\n", "B", "2")
        assert result.endswith("\n")


# ---------------------------------------------------------------------------
# _normalize_backup_env_text
# ---------------------------------------------------------------------------


class TestNormalizeBackupEnvText:
    def test_sets_source_dir(self, tmp_path: Path) -> None:
        content = "OTHER=val\n"
        result = _normalize_backup_env_text(content, tmp_path, "wsl")
        expected_dir = _canonical_backup_source_dir(tmp_path, "wsl")
        assert f"SECRETS_BACKUP_SOURCE_DIR={expected_dir}" in result


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


class TestPathHelpers:
    def test_host_truth_root(self, tmp_path: Path) -> None:
        assert _host_truth_root(tmp_path, "wsl") == tmp_path / "secrets" / "hosts" / "wsl"

    def test_host_infra_secret_file(self, tmp_path: Path) -> None:
        result = _host_infra_secret_file(tmp_path, "wsl", "postgres", "admin.env")
        assert result == tmp_path / "secrets" / "hosts" / "wsl" / "infra" / "postgres" / "admin.env"

    def test_legacy_postgres(self, tmp_path: Path) -> None:
        result = _legacy_postgres_secret_file(tmp_path, "wsl")
        assert result.name == "admin.wsl.env"
        assert "postgres" in result.parts

    def test_legacy_redis(self, tmp_path: Path) -> None:
        result = _legacy_redis_secret_file(tmp_path, "wsl")
        assert result.name == "admin.wsl.conf"

    def test_legacy_minio(self, tmp_path: Path) -> None:
        result = _legacy_minio_secret_file(tmp_path, "wsl")
        assert result.name == "admin.wsl.env"
        assert "minio" in result.parts

    def test_legacy_runtime_env_wsl(self, tmp_path: Path) -> None:
        result = _legacy_runtime_env_path(tmp_path, "wsl", "myapp")
        assert result.name == "myapp.wsl.env"

    def test_legacy_runtime_env_prod0(self, tmp_path: Path) -> None:
        result = _legacy_runtime_env_path(tmp_path, "prod0-main", "myapp")
        assert result.name == "myapp.prod0.env"

    def test_legacy_onepanel_env_wsl(self, tmp_path: Path) -> None:
        result = _legacy_onepanel_env_path(tmp_path, "wsl")
        assert result.name == "onepanel-api.wsl.env"

    def test_legacy_onepanel_env_prod0(self, tmp_path: Path) -> None:
        result = _legacy_onepanel_env_path(tmp_path, "prod0-main")
        assert result.name == "onepanel-api.env"

    def test_legacy_backup_env(self, tmp_path: Path) -> None:
        result = _legacy_backup_env_path(tmp_path, "wsl")
        assert "backup" in result.name
        assert "r2" in result.name


# ---------------------------------------------------------------------------
# _write_secret_file
# ---------------------------------------------------------------------------


class TestWriteSecretFile:
    def test_creates_new(self, tmp_path: Path) -> None:
        f = tmp_path / "secret.env"
        result = _write_secret_file(f, "content", force=False)
        assert result["status"] == "created"
        assert f.read_text(encoding="utf-8") == "content"

    def test_keeps_existing(self, tmp_path: Path) -> None:
        f = tmp_path / "secret.env"
        f.write_text("original", encoding="utf-8")
        result = _write_secret_file(f, "new", force=False)
        assert result["status"] == "kept"
        assert f.read_text(encoding="utf-8") == "original"

    def test_force_overwrites(self, tmp_path: Path) -> None:
        f = tmp_path / "secret.env"
        f.write_text("original", encoding="utf-8")
        result = _write_secret_file(f, "new", force=True)
        assert result["status"] == "written"
        assert f.read_text(encoding="utf-8") == "new"

    def test_with_role(self, tmp_path: Path) -> None:
        f = tmp_path / "secret.env"
        result = _write_secret_file(f, "content", force=False, role="projection")
        assert result["role"] == "projection"


# ---------------------------------------------------------------------------
# copy_template_file
# ---------------------------------------------------------------------------


class TestCopyTemplateFile:
    def test_creates(self, tmp_path: Path) -> None:
        src = tmp_path / "template.txt"
        src.write_text("hello", encoding="utf-8")
        dst = tmp_path / "out" / "dest.txt"
        result = copy_template_file(src, dst)
        assert result["status"] == "created"
        assert dst.read_text(encoding="utf-8") == "hello"

    def test_keeps_existing(self, tmp_path: Path) -> None:
        src = tmp_path / "template.txt"
        src.write_text("new", encoding="utf-8")
        dst = tmp_path / "dest.txt"
        dst.write_text("old", encoding="utf-8")
        result = copy_template_file(src, dst)
        assert result["status"] == "kept"
        assert dst.read_text(encoding="utf-8") == "old"

    def test_with_transform(self, tmp_path: Path) -> None:
        src = tmp_path / "template.txt"
        src.write_text("hello", encoding="utf-8")
        dst = tmp_path / "dest.txt"
        copy_template_file(src, dst, transform=lambda s: s.upper())
        assert dst.read_text(encoding="utf-8") == "HELLO"

    def test_force_overwrites(self, tmp_path: Path) -> None:
        src = tmp_path / "template.txt"
        src.write_text("new", encoding="utf-8")
        dst = tmp_path / "dest.txt"
        dst.write_text("old", encoding="utf-8")
        result = copy_template_file(src, dst, force=True)
        assert result["status"] == "written"
        assert dst.read_text(encoding="utf-8") == "new"


# ---------------------------------------------------------------------------
# summarize_secret_file
# ---------------------------------------------------------------------------


class TestSummarizeSecretFile:
    def test_missing_file(self, tmp_path: Path) -> None:
        result = summarize_secret_file(tmp_path / "nope.env")
        assert result["exists"] is False
        assert result["ok"] is False

    def test_ok_file(self, tmp_path: Path) -> None:
        f = tmp_path / "secret.env"
        f.write_text("KEY=value\n", encoding="utf-8")
        result = summarize_secret_file(f)
        assert result["exists"] is True
        assert result["ok"] is True
        assert result["issues"] == []

    def test_placeholder_detected(self, tmp_path: Path) -> None:
        f = tmp_path / "secret.env"
        f.write_text("KEY=CHANGEME\n", encoding="utf-8")
        result = summarize_secret_file(f, placeholder_markers=("CHANGEME",))
        assert "placeholder-values" in result["issues"]

    def test_missing_fragment(self, tmp_path: Path) -> None:
        f = tmp_path / "secret.env"
        f.write_text("KEY=value\n", encoding="utf-8")
        result = summarize_secret_file(f, required_fragments=("REQUIRED_KEY",))
        assert any("REQUIRED_KEY" in i for i in result["issues"])


# ---------------------------------------------------------------------------
# Golden test
# ---------------------------------------------------------------------------


@pytest.mark.golden
class TestSecretsGolden:
    def test_full_init_roundtrip(self, tmp_path: Path) -> None:
        """_write_secret_file + copy_template_file + summarize roundtrip."""
        # Write a secret
        secret_path = tmp_path / "services" / "postgres" / "admin.wsl.env"
        content = "POSTGRES_USER=admin\nPOSTGRES_PASSWORD=secret123\n"
        write_result = _write_secret_file(secret_path, content, force=False, role="truth")
        assert write_result["status"] == "created"

        # Copy as template
        projection = tmp_path / "legacy" / "admin.wsl.env"
        copy_result = copy_template_file(secret_path, projection)
        assert copy_result["status"] == "created"
        assert projection.read_text(encoding="utf-8") == content

        # Summarize
        summary = summarize_secret_file(secret_path, required_fragments=("POSTGRES_PASSWORD",))
        assert summary["ok"] is True
