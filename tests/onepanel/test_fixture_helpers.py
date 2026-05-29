"""Tests for agentplane.scripts.onepanel.fixture_manager — pure helper functions."""

from __future__ import annotations

import pytest
from agentplane.scripts.onepanel.fixture_manager import (
    _fixture_compose,
    resolve_fixture_spec,
    resolve_suite_targets,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# resolve_fixture_spec
# ---------------------------------------------------------------------------


class TestResolveFixtureSpec:
    def test_defaults(self) -> None:
        spec = resolve_fixture_spec("wsl-fixture", env="wsl")
        assert spec.profile == "wsl-fixture"
        assert spec.env == "wsl"
        assert spec.website_alias == "oplinux-fixture"
        assert spec.project_name == "oplinux-fixture"
        assert spec.cronjob_name == "oplinux-fixture"

    def test_custom_values(self) -> None:
        spec = resolve_fixture_spec(
            "wsl-fixture", env="wsl",
            website_alias="my-site", container_name="my-ctr",
            project_name="my-proj", cronjob_name="my-cron",
            firewall_tab="ip",
        )
        assert spec.website_alias == "my-site"
        assert spec.project_container_name == "my-ctr"
        assert spec.project_name == "my-proj"
        assert spec.cronjob_name == "my-cron"
        assert spec.firewall_tab == "ip"

    def test_unsupported_profile_raises(self) -> None:
        with pytest.raises(ValueError, match="unsupported"):
            resolve_fixture_spec("bad-profile", env="wsl")

    def test_unsupported_env_raises(self) -> None:
        with pytest.raises(ValueError, match="env=wsl"):
            resolve_fixture_spec("wsl-fixture", env="prod0-main")


# ---------------------------------------------------------------------------
# resolve_suite_targets
# ---------------------------------------------------------------------------


class TestResolveSuiteTargets:
    def test_wsl_fixture_profile(self) -> None:
        result = resolve_suite_targets(profile="wsl-fixture", env="wsl")
        assert result["website_alias"] == "oplinux-fixture"
        assert result["project_name"] == "oplinux-fixture"

    def test_non_wsl_fixture_profile_passthrough(self) -> None:
        result = resolve_suite_targets(
            profile="other", env="wsl",
            website_alias="a", container_name="b",
            project_name="c", cronjob_id=1, cronjob_name="d",
            app_name="e", firewall_tab="f",
        )
        assert result["website_alias"] == "a"
        assert result["container_name"] == "b"
        assert result["cronjob_id"] == 1

    def test_custom_overrides(self) -> None:
        result = resolve_suite_targets(
            profile="wsl-fixture", env="wsl",
            website_alias="custom",
        )
        assert result["website_alias"] == "custom"


# ---------------------------------------------------------------------------
# _fixture_compose
# ---------------------------------------------------------------------------


class TestFixtureCompose:
    def test_generates_valid_yaml(self) -> None:
        spec = resolve_fixture_spec("wsl-fixture", env="wsl")
        compose = _fixture_compose(spec)
        assert "services:" in compose
        assert spec.project_image in compose
        assert spec.project_container_name in compose
        assert str(spec.project_host_port) in compose


# ---------------------------------------------------------------------------
# Golden test
# ---------------------------------------------------------------------------


@pytest.mark.golden
class TestFixtureManagerGolden:
    def test_full_spec_roundtrip(self) -> None:
        """Resolve spec → compose → suite targets all consistent."""
        spec = resolve_fixture_spec("wsl-fixture", env="wsl")
        compose = _fixture_compose(spec)
        assert spec.project_image in compose

        targets = resolve_suite_targets(profile="wsl-fixture", env="wsl")
        assert targets["website_alias"] == spec.website_alias
