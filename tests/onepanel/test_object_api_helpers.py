"""Tests for agentplane.scripts.onepanel.object_api — pure helper functions."""

from __future__ import annotations

from typing import Any

import pytest
from agentplane.scripts.onepanel.object_api import (
    _coerce_app_param,
    _default_install_params_for_app,
    _parse_app_params,
    build_app_install_params,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# _coerce_app_param
# ---------------------------------------------------------------------------


class TestCoerceAppParam:
    def test_integer(self) -> None:
        assert _coerce_app_param("42") == 42

    def test_true(self) -> None:
        assert _coerce_app_param("true") is True

    def test_false(self) -> None:
        assert _coerce_app_param("false") is False

    def test_case_insensitive_bool(self) -> None:
        assert _coerce_app_param("TRUE") is True
        assert _coerce_app_param("False") is False

    def test_string(self) -> None:
        assert _coerce_app_param("hello") == "hello"

    def test_empty_string(self) -> None:
        assert _coerce_app_param("") == ""


# ---------------------------------------------------------------------------
# _parse_app_params
# ---------------------------------------------------------------------------


class TestParseAppParams:
    def test_basic(self) -> None:
        result = _parse_app_params(["key1=val1", "key2=42"])
        assert result == {"key1": "val1", "key2": 42}

    def test_empty(self) -> None:
        assert _parse_app_params([]) == {}

    def test_invalid_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid"):
            _parse_app_params(["no-equals"])

    def test_value_with_equals(self) -> None:
        result = _parse_app_params(["key=a=b"])
        assert result["key"] == "a=b"


# ---------------------------------------------------------------------------
# _default_install_params_for_app
# ---------------------------------------------------------------------------


class TestDefaultInstallParamsForApp:
    def test_openresty(self) -> None:
        result = _default_install_params_for_app("openresty")
        assert result["PANEL_APP_PORT_HTTP"] == 80
        assert result["PANEL_APP_PORT_HTTPS"] == 443

    def test_unknown_app(self) -> None:
        assert _default_install_params_for_app("unknown") == {}


# ---------------------------------------------------------------------------
# build_app_install_params
# ---------------------------------------------------------------------------


class TestBuildAppInstallParams:
    def test_with_form_fields(self) -> None:
        detail: dict[str, Any] = {
            "params": {
                "formFields": [
                    {"envKey": "DB_HOST", "default": "localhost"},
                    {"envKey": "DB_PORT", "default": "5432"},
                ],
            },
        }
        result = build_app_install_params("myapp", detail)
        assert result["DB_HOST"] == "localhost"
        assert result["DB_PORT"] == "5432"

    def test_with_raw_overrides(self) -> None:
        detail: dict[str, Any] = {}
        result = build_app_install_params("myapp", detail, raw_items=["DB_HOST=remote"])
        assert result["DB_HOST"] == "remote"

    def test_openresty_defaults(self) -> None:
        detail: dict[str, Any] = {}
        result = build_app_install_params("openresty", detail)
        assert result["PANEL_APP_PORT_HTTP"] == 80

    def test_empty_detail(self) -> None:
        result = build_app_install_params("myapp", {})
        assert isinstance(result, dict)

    def test_non_dict_params(self) -> None:
        detail: dict[str, Any] = {"params": "bad"}
        result = build_app_install_params("myapp", detail)
        assert isinstance(result, dict)

    def test_non_list_form_fields(self) -> None:
        detail: dict[str, Any] = {"params": {"formFields": "bad"}}
        result = build_app_install_params("myapp", detail)
        assert isinstance(result, dict)

    def test_field_without_env_key(self) -> None:
        detail: dict[str, Any] = {
            "params": {"formFields": [{"default": "val"}]},
        }
        result = build_app_install_params("myapp", detail)
        # Field without envKey should be skipped
        assert len(result) == 0


# ---------------------------------------------------------------------------
# Golden test
# ---------------------------------------------------------------------------


@pytest.mark.golden
class TestObjectApiHelpersGolden:
    def test_full_install_params_roundtrip(self) -> None:
        """Build install params with form fields, defaults, and overrides."""
        detail: dict[str, Any] = {
            "params": {
                "formFields": [
                    {"envKey": "DB_HOST", "default": "localhost"},
                ],
            },
        }
        result = build_app_install_params("openresty", detail, raw_items=["CUSTOM=val"])
        assert result["DB_HOST"] == "localhost"
        assert result["PANEL_APP_PORT_HTTP"] == 80
        assert result["CUSTOM"] == "val"
