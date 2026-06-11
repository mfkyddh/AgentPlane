from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from agentplane.domain.service.materialize import (
    ARTIFACT_CLASH_LOCAL_PROFILE,
    _effective_rules,
    _new_trojan_node,
    _resolve_required_port,
    _resolve_required_str,
    materialize_service_artifact,
)
from agentplane.domain.service.models import ServiceDefinition

pytestmark = pytest.mark.unit

_SERVICE = ServiceDefinition(
    name="test-svc",
    runtime_kind="docker",
    control_plane="1panel",
    supported_operations=(),
    supported_targets=(),
)


# ── _new_trojan_node ────────────────────────────────────────────────


class TestNewTrojanNode:
    def test_returns_expected_structure(self) -> None:
        node = _new_trojan_node(
            node_name="my-node",
            server="relay.example.org",
            port=443,
            password="secret",
            sni="relay.example.org",
        )
        assert node == {
            "name": "my-node",
            "type": "trojan",
            "server": "relay.example.org",
            "port": 443,
            "password": "secret",
            "sni": "relay.example.org",
            "udp": True,
            "skip-cert-verify": False,
        }

    def test_port_accepts_non_standard_value(self) -> None:
        node = _new_trojan_node(
            node_name="n", server="s", port=24443, password="p", sni="s",
        )
        assert node["port"] == 24443


# ── _effective_rules ────────────────────────────────────────────────


class TestEffectiveRules:
    def test_no_merge_returns_source_rules(self) -> None:
        rules = ["MATCH,DIRECT"]
        assert _effective_rules(rules, None) == ["MATCH,DIRECT"]

    def test_non_list_source_returns_empty(self) -> None:
        assert _effective_rules("not-a-list", None) == []

    def test_non_dict_merge_returns_source(self) -> None:
        assert _effective_rules(["r1"], "bad") == ["r1"]

    def test_prepend_rules(self) -> None:
        result = _effective_rules(
            ["base"],
            {"prepend__rules": ["pre1", "pre2"]},
        )
        assert result == ["pre1", "pre2", "base"]

    def test_append_rules(self) -> None:
        result = _effective_rules(
            ["base"],
            {"append__rules": ["post1"]},
        )
        assert result == ["base", "post1"]

    def test_prepend_and_append_combined(self) -> None:
        result = _effective_rules(
            ["mid"],
            {"prepend__rules": ["pre"], "append__rules": ["post"]},
        )
        assert result == ["pre", "mid", "post"]

    def test_empty_source_with_prepend(self) -> None:
        result = _effective_rules([], {"prepend__rules": ["only"]})
        assert result == ["only"]

    def test_non_list_prepend_is_ignored(self) -> None:
        result = _effective_rules(["base"], {"prepend__rules": "bad"})
        assert result == ["base"]

    def test_non_list_append_is_ignored(self) -> None:
        result = _effective_rules(["base"], {"append__rules": 42})
        assert result == ["base"]


# ── _resolve_required_str ───────────────────────────────────────────


class TestResolveRequiredStr:
    def test_valid_value(self) -> None:
        assert _resolve_required_str("hello", field="f", service_name="s") == "hello"

    def test_strips_whitespace(self) -> None:
        assert _resolve_required_str("  val  ", field="f", service_name="s") == "val"

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="non-empty f"):
            _resolve_required_str("", field="f", service_name="s")

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(ValueError, match="non-empty f"):
            _resolve_required_str("   ", field="f", service_name="s")


# ── _resolve_required_port ──────────────────────────────────────────


class TestResolveRequiredPort:
    def test_valid_int(self) -> None:
        assert _resolve_required_port(443, service_name="s") == 443

    def test_valid_string(self) -> None:
        assert _resolve_required_port("8080", service_name="s") == 8080

    def test_string_with_whitespace(self) -> None:
        assert _resolve_required_port("  443  ", service_name="s") == 443

    def test_none_raises(self) -> None:
        with pytest.raises(ValueError, match="valid port"):
            _resolve_required_port(None, service_name="s")

    def test_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="valid port"):
            _resolve_required_port(-1, service_name="s")

    def test_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="valid port"):
            _resolve_required_port(0, service_name="s")

    def test_non_digit_string_raises(self) -> None:
        with pytest.raises(ValueError, match="valid port"):
            _resolve_required_port("abc", service_name="s")

    def test_float_raises(self) -> None:
        with pytest.raises(ValueError, match="valid port"):
            _resolve_required_port(443.0, service_name="s")


# ── materialize_service_artifact ────────────────────────────────────


def _minimal_declared(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "public_endpoint": {"domain": "relay.example.org", "port": 443},
        "client_profile": {
            "server": "relay.example.org",
            "port": 443,
            "sni": "relay.example.org",
        },
    }
    base.update(overrides)
    return base


def _make_source_yaml() -> str:
    return yaml.safe_dump({
        "proxies": [{"name": "old", "type": "ss", "server": "s", "port": 1}],
        "proxy-groups": [{"name": "G", "type": "select", "proxies": ["old", "DIRECT"]}],
        "rules": ["MATCH,G"],
    })


class TestMaterializeServiceArtifact:
    def test_unsupported_artifact_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="unsupported service artifact"):
            materialize_service_artifact(
                _SERVICE,
                _minimal_declared(),
                artifact="unknown",
                source=tmp_path / "src.yml",
                merge_template=None,
                output=tmp_path / "out.yml",
                password="pw",
            )

    def test_non_dict_declared_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="does not expose tracked artifact metadata"):
            materialize_service_artifact(
                _SERVICE,
                None,
                artifact=ARTIFACT_CLASH_LOCAL_PROFILE,
                source=tmp_path / "src.yml",
                merge_template=None,
                output=tmp_path / "out.yml",
                password="pw",
            )

    def test_non_dict_client_profile_raises(self, tmp_path: Path) -> None:
        declared = _minimal_declared(client_profile="bad")
        with pytest.raises(ValueError, match="client_profile must be an object"):
            materialize_service_artifact(
                _SERVICE,
                declared,
                artifact=ARTIFACT_CLASH_LOCAL_PROFILE,
                source=tmp_path / "src.yml",
                merge_template=None,
                output=tmp_path / "out.yml",
                password="pw",
            )

    def test_format_mismatch_raises(self, tmp_path: Path) -> None:
        declared = _minimal_declared(
            client_profile={"format": "other-format", "server": "s", "port": 443, "sni": "s"},
        )
        with pytest.raises(ValueError, match="does not support artifact"):
            materialize_service_artifact(
                _SERVICE,
                declared,
                artifact=ARTIFACT_CLASH_LOCAL_PROFILE,
                source=tmp_path / "src.yml",
                merge_template=None,
                output=tmp_path / "out.yml",
                password="pw",
            )

    def test_success_path(self, tmp_path: Path) -> None:
        src = tmp_path / "source.yml"
        src.write_text(_make_source_yaml(), encoding="utf-8")
        out = tmp_path / "out.yml"

        result = materialize_service_artifact(
            _SERVICE,
            _minimal_declared(),
            artifact=ARTIFACT_CLASH_LOCAL_PROFILE,
            source=src,
            merge_template=None,
            output=out,
            password="pw",
            node_name="my-node",
        )

        assert result["ok"] is True
        assert result["artifact"] == ARTIFACT_CLASH_LOCAL_PROFILE
        assert result["output"] == str(out)
        assert result["resolved"]["node_name"] == "my-node"
        assert result["resolved"]["server"] == "relay.example.org"
        assert result["resolved"]["port"] == 443
        assert result["resolved"]["sni"] == "relay.example.org"
        assert out.exists()

    def test_success_with_merge_template(self, tmp_path: Path) -> None:
        src = tmp_path / "source.yml"
        src.write_text(_make_source_yaml(), encoding="utf-8")
        merge = tmp_path / "merge.yml"
        merge.write_text(
            yaml.safe_dump({"prepend__rules": ["DOMAIN-SUFFIX,example.org,DIRECT"]}),
            encoding="utf-8",
        )
        out = tmp_path / "out.yml"

        result = materialize_service_artifact(
            _SERVICE,
            _minimal_declared(),
            artifact=ARTIFACT_CLASH_LOCAL_PROFILE,
            source=src,
            merge_template=merge,
            output=out,
            password="pw",
        )

        assert result["ok"] is True
        rendered = yaml.safe_load(out.read_text(encoding="utf-8"))
        assert rendered["rules"][0] == "DOMAIN-SUFFIX,example.org,DIRECT"

    def test_source_not_yaml_dict_raises(self, tmp_path: Path) -> None:
        src = tmp_path / "bad.yml"
        src.write_text("- just\n- a list\n", encoding="utf-8")
        out = tmp_path / "out.yml"

        with pytest.raises(ValueError, match="artifact source must be a YAML object"):
            materialize_service_artifact(
                _SERVICE,
                _minimal_declared(),
                artifact=ARTIFACT_CLASH_LOCAL_PROFILE,
                source=src,
                merge_template=None,
                output=out,
                password="pw",
            )

    def test_merge_template_not_yaml_dict_raises(self, tmp_path: Path) -> None:
        src = tmp_path / "source.yml"
        src.write_text(_make_source_yaml(), encoding="utf-8")
        merge = tmp_path / "bad_merge.yml"
        merge.write_text("- not\n- a dict\n", encoding="utf-8")
        out = tmp_path / "out.yml"

        with pytest.raises(ValueError, match="artifact merge template must be a YAML object"):
            materialize_service_artifact(
                _SERVICE,
                _minimal_declared(),
                artifact=ARTIFACT_CLASH_LOCAL_PROFILE,
                source=src,
                merge_template=merge,
                output=out,
                password="pw",
            )

    def test_resolves_server_from_public_endpoint(self, tmp_path: Path) -> None:
        src = tmp_path / "source.yml"
        src.write_text(_make_source_yaml(), encoding="utf-8")
        out = tmp_path / "out.yml"
        declared: dict[str, Any] = {
            "public_endpoint": {"domain": "ep.example.org", "port": 8443},
            "client_profile": {"port": 8443, "sni": "ep.example.org"},
        }

        result = materialize_service_artifact(
            _SERVICE,
            declared,
            artifact=ARTIFACT_CLASH_LOCAL_PROFILE,
            source=src,
            merge_template=None,
            output=out,
            password="pw",
        )

        assert result["resolved"]["server"] == "ep.example.org"
        assert result["resolved"]["port"] == 8443

    def test_explicit_args_override_contract(self, tmp_path: Path) -> None:
        src = tmp_path / "source.yml"
        src.write_text(_make_source_yaml(), encoding="utf-8")
        out = tmp_path / "out.yml"

        result = materialize_service_artifact(
            _SERVICE,
            _minimal_declared(),
            artifact=ARTIFACT_CLASH_LOCAL_PROFILE,
            source=src,
            merge_template=None,
            output=out,
            password="pw",
            server="override.example.org",
            port=9443,
            sni="override.example.org",
        )

        assert result["resolved"]["server"] == "override.example.org"
        assert result["resolved"]["port"] == 9443
        assert result["resolved"]["sni"] == "override.example.org"
