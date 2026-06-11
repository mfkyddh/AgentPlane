"""Unit tests for pure domain functions.

These tests exercise pure logic with zero I/O, zero subprocess, zero CLI.
They should run in <10ms total and are safe for `-n auto` parallel.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from agentplane.domain.app.artifacts import detect_contract_mode
from agentplane.domain.app.delivery_handlers import _delayed_cleanup_state, _rollback_state_payload
from agentplane.domain.app.models import AppCatalogEntry
from agentplane.domain.app.resource_state import (
    normalize_key_prefix,
    parse_env_text,
    validate_duplicate_ownership,
    validate_duplicate_redis_combination,
)
from agentplane.domain.app.runtime import _secrets_root
from agentplane.domain.app.truth_lifecycle import offboard_catalog_entry, onboard_catalog_entry, validate_app_id

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# validate_app_id
# ---------------------------------------------------------------------------


class TestValidateAppId:
    @pytest.mark.unit
    def test_accepts_valid_kebab_case(self) -> None:
        validate_app_id("sub2api")  # should not raise
        validate_app_id("my-app-v2")  # should not raise

    @pytest.mark.unit
    def test_rejects_empty(self) -> None:
        with pytest.raises(ValueError):
            validate_app_id("")

    @pytest.mark.unit
    def test_rejects_uppercase(self) -> None:
        with pytest.raises(ValueError):
            validate_app_id("Sub2Api")

    @pytest.mark.unit
    def test_rejects_leading_hyphen(self) -> None:
        with pytest.raises(ValueError):
            validate_app_id("-app")

    @pytest.mark.unit
    def test_rejects_double_hyphen(self) -> None:
        with pytest.raises(ValueError):
            validate_app_id("my--app")


# ---------------------------------------------------------------------------
# normalize_key_prefix
# ---------------------------------------------------------------------------


class TestNormalizeKeyPrefix:
    @pytest.mark.unit
    def test_appends_colon(self) -> None:
        assert normalize_key_prefix("sub2api") == "sub2api:"

    @pytest.mark.unit
    def test_keeps_existing_colon(self) -> None:
        assert normalize_key_prefix("sub2api:") == "sub2api:"

    @pytest.mark.unit
    def test_none_returns_none(self) -> None:
        assert normalize_key_prefix(None) is None

    @pytest.mark.unit
    def test_empty_returns_none(self) -> None:
        assert normalize_key_prefix("") is None

    @pytest.mark.unit
    def test_whitespace_only_returns_none(self) -> None:
        assert normalize_key_prefix("  ") is None

    @pytest.mark.unit
    def test_strips_whitespace(self) -> None:
        assert normalize_key_prefix("  sub2api  ") == "sub2api:"


# ---------------------------------------------------------------------------
# parse_env_text
# ---------------------------------------------------------------------------


class TestParseEnvText:
    @pytest.mark.unit
    def test_basic_key_value(self) -> None:
        assert parse_env_text("HOST=localhost\nPORT=5432") == {
            "HOST": "localhost",
            "PORT": "5432",
        }

    @pytest.mark.unit
    def test_skips_comments(self) -> None:
        result = parse_env_text("# comment\nKEY=val\n# another")
        assert result == {"KEY": "val"}

    @pytest.mark.unit
    def test_skips_empty_lines(self) -> None:
        result = parse_env_text("\n\nKEY=val\n\n")
        assert result == {"KEY": "val"}

    @pytest.mark.unit
    def test_empty_value(self) -> None:
        result = parse_env_text("EMPTY=")
        assert result == {"EMPTY": ""}

    @pytest.mark.unit
    def test_value_with_equals_sign(self) -> None:
        result = parse_env_text("CONN=host=db port=5432")
        assert result == {"CONN": "host=db port=5432"}


# ---------------------------------------------------------------------------
# detect_contract_mode
# ---------------------------------------------------------------------------


class TestDetectContractMode:
    @pytest.mark.unit
    def test_legacy_when_no_schema_version(self) -> None:
        mode, version = detect_contract_mode({})
        assert mode == "legacy"
        assert version is None

    @pytest.mark.unit
    def test_v1_when_schema_version_1(self) -> None:
        mode, version = detect_contract_mode({"schema_version": 1})
        assert mode == "v1"
        assert version == 1

    @pytest.mark.unit
    def test_v2_when_schema_version_2(self) -> None:
        mode, version = detect_contract_mode({"schema_version": 2})
        assert mode == "v2"
        assert version == 2

    @pytest.mark.unit
    def test_unsupported_schema_version_raises(self) -> None:
        with pytest.raises(ValueError, match="不受支持"):
            detect_contract_mode({"schema_version": 3})


# ---------------------------------------------------------------------------
# validate_duplicate_ownership
# ---------------------------------------------------------------------------


class TestValidateDuplicateOwnership:
    @pytest.mark.unit
    def test_no_duplicates(self) -> None:
        registry = {
            "app1": {"owner_app": "app1", "postgres": {"database": "db1", "user": "u1"}},
            "app2": {"owner_app": "app2", "postgres": {"database": "db2", "user": "u2"}},
        }
        assert validate_duplicate_ownership(registry) == []

    @pytest.mark.unit
    def test_duplicate_postgres(self) -> None:
        registry = {
            "app1": {"owner_app": "app1", "postgres": {"database": "shared_db", "user": "shared_user"}},
            "app2": {"owner_app": "app2", "postgres": {"database": "shared_db", "user": "shared_user"}},
        }
        errors = validate_duplicate_ownership(registry)
        assert len(errors) == 1
        assert errors[0]["kind"] == "postgres"
        assert errors[0]["owner_a"] != errors[0]["owner_b"]

    @pytest.mark.unit
    def test_duplicate_minio(self) -> None:
        registry = {
            "app1": {"owner_app": "app1", "minio": {"bucket": "b1", "access_key": "ak1"}},
            "app2": {"owner_app": "app2", "minio": {"bucket": "b1", "access_key": "ak1"}},
        }
        errors = validate_duplicate_ownership(registry)
        assert len(errors) == 1
        assert errors[0]["kind"] == "minio"

    @pytest.mark.unit
    def test_same_app_no_error(self) -> None:
        registry = {
            "app1": {"owner_app": "app1", "postgres": {"database": "db1", "user": "u1"}},
        }
        assert validate_duplicate_ownership(registry) == []

    @pytest.mark.unit
    def test_empty_registry(self) -> None:
        assert validate_duplicate_ownership({}) == []


# ---------------------------------------------------------------------------
# validate_duplicate_redis_combination
# ---------------------------------------------------------------------------


class TestValidateDuplicateRedisCombination:
    @pytest.mark.unit
    def test_no_duplicates(self) -> None:
        registry = {
            "app1": {"owner_app": "app1", "redis": {"db": 1, "key_prefix": "app1:"}},
            "app2": {"owner_app": "app2", "redis": {"db": 2, "key_prefix": "app2:"}},
        }
        assert validate_duplicate_redis_combination(registry) == []

    @pytest.mark.unit
    def test_duplicate_db(self) -> None:
        registry = {
            "app1": {"owner_app": "app1", "redis": {"db": 1, "key_prefix": "app1:"}},
            "app2": {"owner_app": "app2", "redis": {"db": 1, "key_prefix": "app2:"}},
        }
        errors = validate_duplicate_redis_combination(registry)
        assert len(errors) == 1
        assert "db" in errors[0]

    @pytest.mark.unit
    def test_duplicate_normalized_key_prefix(self) -> None:
        registry = {
            "app1": {"owner_app": "app1", "redis": {"db": 1, "key_prefix": "app1:"}},
            "app2": {"owner_app": "app2", "redis": {"db": 2, "key_prefix": "app1"}},
        }
        errors = validate_duplicate_redis_combination(registry)
        assert len(errors) == 1
        assert "key_prefix" in errors[0]

    @pytest.mark.unit
    def test_same_app_no_error(self) -> None:
        registry = {
            "app1": {"owner_app": "app1", "redis": {"db": 1, "key_prefix": "app1:"}},
        }
        assert validate_duplicate_redis_combination(registry) == []


# ---------------------------------------------------------------------------
# _delayed_cleanup_state
# ---------------------------------------------------------------------------


class TestDelayedCleanupState:
    @pytest.mark.unit
    def test_kind_none_returns_not_applicable(self) -> None:
        result = _delayed_cleanup_state({"kind": "none"})
        assert result["status"] == "not-applicable"
        assert result["observation_window_required"] is False

    @pytest.mark.unit
    def test_kind_systemd_returns_pending(self) -> None:
        result = _delayed_cleanup_state({"kind": "systemd", "service_name": "app"})
        assert result["status"] == "observation-window-pending"
        assert result["observation_window_required"] is True

    @pytest.mark.unit
    def test_kind_1panel_app_returns_pending(self) -> None:
        result = _delayed_cleanup_state({"kind": "1panel-app", "install_id": "123"})
        assert result["status"] == "observation-window-pending"
        assert result["observation_window_required"] is True


# ---------------------------------------------------------------------------
# _rollback_state_payload
# ---------------------------------------------------------------------------


class TestRollbackStatePayload:
    @pytest.mark.unit
    def test_assembles_all_phases(self) -> None:
        result = _rollback_state_payload(
            previous_control_plane={"kind": "systemd"},
            candidate={"status": "verified"},
            cutover={"status": "planned"},
            post_cutover_verification={"status": "planned"},
            rollback_on_failure={"status": "standby"},
            delayed_cleanup={"status": "not-applicable"},
        )
        assert result["previous_control_plane"]["kind"] == "systemd"
        assert result["candidate"]["status"] == "verified"
        assert result["cutover"]["status"] == "planned"
        assert result["post_cutover_verification"]["status"] == "planned"
        assert result["rollback_on_failure"]["status"] == "standby"
        assert result["delayed_cleanup"]["status"] == "not-applicable"


# ---------------------------------------------------------------------------
# _secrets_root
# ---------------------------------------------------------------------------


class TestSecretsRoot:
    @pytest.mark.unit
    def test_prefers_repo_local_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            secrets_dir = root / "secrets"
            secrets_dir.mkdir(parents=True, exist_ok=True)
            assert _secrets_root(root) == secrets_dir

    @pytest.mark.unit
    def test_falls_back_to_git_common_dir_for_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            main_root = tmp_root / "main"
            worktree_root = tmp_root / "worktree"
            git_worktree_dir = main_root / ".git" / "worktrees" / "demo"
            main_secrets = main_root / "secrets"

            main_secrets.mkdir(parents=True, exist_ok=True)
            git_worktree_dir.mkdir(parents=True, exist_ok=True)
            worktree_root.mkdir(parents=True, exist_ok=True)
            (worktree_root / ".git").write_text(f"gitdir: {git_worktree_dir}\n", encoding="utf-8")

            assert _secrets_root(worktree_root) == main_secrets

    @pytest.mark.unit
    def test_prefers_git_common_dir_over_worktree_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            main_root = tmp_root / "main"
            worktree_root = tmp_root / "worktree"
            git_worktree_dir = main_root / ".git" / "worktrees" / "demo"
            main_secrets = main_root / "secrets"

            main_secrets.mkdir(parents=True, exist_ok=True)
            git_worktree_dir.mkdir(parents=True, exist_ok=True)
            worktree_root.mkdir(parents=True, exist_ok=True)
            (worktree_root / ".git").write_text(f"gitdir: {git_worktree_dir}\n", encoding="utf-8")
            (worktree_root / "secrets").symlink_to(main_secrets)

            assert _secrets_root(worktree_root) == main_secrets


# ---------------------------------------------------------------------------
# Catalog lifecycle (onboard / offboard)
# ---------------------------------------------------------------------------


def _write_catalog(repo_root: Path, payload: dict) -> None:
    path = repo_root / "inventory" / "apps" / "catalog.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_catalog(repo_root: Path) -> dict:
    path = repo_root / "inventory" / "apps" / "catalog.json"
    return json.loads(path.read_text(encoding="utf-8"))


class TestCatalogLifecycle:
    @pytest.mark.unit
    def test_onboard_adds_entry_and_sorts_by_app_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            _write_catalog(
                repo_root,
                {
                    "apps": [
                        {
                            "app": "sub2api",
                            "repo_name": "sub2api",
                            "repo_root": "/work/sub2api",
                            "service_key": "sub2api",
                            "contracts": {"prod0-main": "deploy/agentplane/contract.yaml"},
                        }
                    ]
                },
            )
            entry = AppCatalogEntry(
                app="sampleapi",
                repo_name="new-api",
                repo_root=Path("/work/new-api"),
                service_key="sampleapi",
                contracts={"prod0-main": "deploy/agentplane/contract.yaml"},
            )
            result = onboard_catalog_entry(repo_root, entry, write=True)
            assert result.changed
            payload = _read_catalog(repo_root)
            apps = payload["apps"]
            assert [item["app"] for item in apps] == ["sampleapi", "sub2api"]
            assert apps[0]["service_key"] == "sampleapi"

    @pytest.mark.unit
    def test_onboard_rejects_service_key_alias(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            _write_catalog(repo_root, {"apps": []})
            entry = AppCatalogEntry(
                app="sampleapi",
                repo_name="new-api",
                repo_root=Path("/work/new-api"),
                service_key="new-api",
                contracts={"prod0-main": "deploy/agentplane/contract.yaml"},
            )
            with pytest.raises(ValueError):
                onboard_catalog_entry(repo_root, entry, write=True)

    @pytest.mark.unit
    def test_offboard_removes_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            _write_catalog(
                repo_root,
                {
                    "apps": [
                        {
                            "app": "sampleapi",
                            "repo_name": "new-api",
                            "repo_root": "/work/new-api",
                            "service_key": "sampleapi",
                            "contracts": {"prod0-main": "deploy/agentplane/contract.yaml"},
                        }
                    ]
                },
            )
            result = offboard_catalog_entry(repo_root, app_id="sampleapi", write=True)
            assert result.changed
            payload = _read_catalog(repo_root)
            assert payload["apps"] == []
