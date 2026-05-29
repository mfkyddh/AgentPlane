"""Tests for agentplane.domain.project.onepanel_provider — pure helper functions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from agentplane.domain.project.onepanel_provider import (
    GROUP_IMPACTS,
    _fingerprint_routes,
    _impact_matrix,
    _impact_sort_key,
    _impact_summary,
    _join_route_path,
    _normalize_impact,
    _route_group,
    _route_impact,
    _route_sort_key,
    compare_route_fingerprints,
    load_route_fingerprint,
    write_route_fingerprint,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# _join_route_path
# ---------------------------------------------------------------------------


class TestJoinRoutePath:
    def test_with_route_path(self) -> None:
        assert _join_route_path("hosts", "/list") == "/hosts/list"

    def test_without_route_path(self) -> None:
        assert _join_route_path("hosts", "") == "/hosts"

    def test_route_path_without_leading_slash(self) -> None:
        assert _join_route_path("apps", "install") == "/apps/install"

    def test_strips_group_slashes(self) -> None:
        assert _join_route_path("/hosts/", "/list") == "/hosts/list"


# ---------------------------------------------------------------------------
# _route_sort_key
# ---------------------------------------------------------------------------


class TestRouteSortKey:
    def test_returns_tuple(self) -> None:
        route = {"path": "/a", "method": "GET", "handler": "handler1"}
        assert _route_sort_key(route) == ("/a", "GET", "handler1")


# ---------------------------------------------------------------------------
# _fingerprint_routes
# ---------------------------------------------------------------------------


class TestFingerprintRoutes:
    def test_deterministic(self) -> None:
        routes = [
            {"group": "a", "handler": "h1", "method": "GET", "path": "/a"},
            {"group": "b", "handler": "h2", "method": "POST", "path": "/b"},
        ]
        fp1 = _fingerprint_routes(routes)
        fp2 = _fingerprint_routes(routes)
        assert fp1 == fp2
        assert len(fp1) == 64  # sha256 hex

    def test_order_independent(self) -> None:
        r1 = {"group": "a", "handler": "h1", "method": "GET", "path": "/a"}
        r2 = {"group": "b", "handler": "h2", "method": "POST", "path": "/b"}
        assert _fingerprint_routes([r1, r2]) == _fingerprint_routes([r2, r1])

    def test_different_routes_different_fp(self) -> None:
        r1 = [{"group": "a", "handler": "h1", "method": "GET", "path": "/a"}]
        r2 = [{"group": "a", "handler": "h1", "method": "GET", "path": "/b"}]
        assert _fingerprint_routes(r1) != _fingerprint_routes(r2)

    def test_empty(self) -> None:
        fp = _fingerprint_routes([])
        assert len(fp) == 64


# ---------------------------------------------------------------------------
# _normalize_impact
# ---------------------------------------------------------------------------


class TestNormalizeImpact:
    def test_basic(self) -> None:
        impact = {"priority": "P0", "surfaces": ["b", "a"], "policy": "read-only-first", "reason": "test"}
        result = _normalize_impact(impact)
        assert result["priority"] == "P0"
        assert result["surfaces"] == ["a", "b"]  # sorted
        assert result["policy"] == "read-only-first"

    def test_missing_surfaces(self) -> None:
        impact: dict[str, Any] = {"priority": "P3", "policy": "evidence-only", "reason": "test"}
        result = _normalize_impact(impact)
        assert result["surfaces"] == []


# ---------------------------------------------------------------------------
# _route_impact
# ---------------------------------------------------------------------------


class TestRouteImpact:
    def test_known_group(self) -> None:
        route = {"group": "containers", "path": "/containers/list"}
        impact = _route_impact(route)
        assert impact["priority"] == "P0"

    def test_path_override(self) -> None:
        route = {"group": "hosts", "path": "/hosts/firewall"}
        impact = _route_impact(route)
        assert impact["priority"] == "P0"
        assert "infra.network" in impact["surfaces"]

    def test_unknown_group(self) -> None:
        route = {"group": "unknown_xyz", "path": "/unknown/list"}
        impact = _route_impact(route)
        assert impact["priority"] == "P3"
        assert impact["policy"] == "classify-before-expand"

    def test_ssh_path(self) -> None:
        route = {"group": "hosts", "path": "/hosts/ssh/config"}
        impact = _route_impact(route)
        assert impact["priority"] == "P1"


# ---------------------------------------------------------------------------
# _impact_sort_key
# ---------------------------------------------------------------------------


class TestImpactSortKey:
    def test_ordering(self) -> None:
        p0 = {"priority": "P0", "surfaces": ["a"]}
        p3 = {"priority": "P3", "surfaces": ["a"]}
        assert _impact_sort_key(p0) < _impact_sort_key(p3)


# ---------------------------------------------------------------------------
# _impact_summary
# ---------------------------------------------------------------------------


class TestImpactSummary:
    def test_basic(self) -> None:
        routes = [
            {"group": "containers", "path": "/containers/list", "impact": _route_impact({"group": "containers", "path": ""})},
            {"group": "hosts", "path": "/hosts/list", "impact": _route_impact({"group": "hosts", "path": ""})},
        ]
        summary = _impact_summary(routes)
        assert summary["route_count"] == 2
        assert summary["highest_priority"] == "P0"
        assert len(summary["groups"]) == 2

    def test_empty(self) -> None:
        summary = _impact_summary([])
        assert summary["route_count"] == 0
        assert summary["highest_priority"] is None


# ---------------------------------------------------------------------------
# _impact_matrix
# ---------------------------------------------------------------------------


class TestImpactMatrix:
    def test_returns_all_groups(self) -> None:
        matrix = _impact_matrix()
        assert len(matrix) == len(GROUP_IMPACTS)
        groups = [item["group"] for item in matrix]
        assert "containers" in groups
        assert "websites" in groups


# ---------------------------------------------------------------------------
# compare_route_fingerprints
# ---------------------------------------------------------------------------


class TestCompareRouteFingerprints:
    def test_identical(self) -> None:
        fp = {"fingerprint": "abc", "routes": [{"method": "GET", "path": "/a", "handler": "h", "group": "g"}]}
        result = compare_route_fingerprints(fp, fp)
        assert result["changed"] is False
        assert result["counts"]["added"] == 0
        assert result["counts"]["removed"] == 0

    def test_added_route(self) -> None:
        baseline = {"fingerprint": "a", "routes": []}
        current = {"fingerprint": "b", "routes": [{"method": "GET", "path": "/new", "handler": "h", "group": "g"}]}
        result = compare_route_fingerprints(current, baseline)
        assert result["changed"] is True
        assert result["counts"]["added"] == 1

    def test_removed_route(self) -> None:
        baseline = {"fingerprint": "a", "routes": [{"method": "GET", "path": "/old", "handler": "h", "group": "g"}]}
        current = {"fingerprint": "b", "routes": []}
        result = compare_route_fingerprints(current, baseline)
        assert result["counts"]["removed"] == 1

    def test_changed_handler(self) -> None:
        baseline = {"fingerprint": "a", "routes": [{"method": "GET", "path": "/a", "handler": "old", "group": "g"}]}
        current = {"fingerprint": "b", "routes": [{"method": "GET", "path": "/a", "handler": "new", "group": "g"}]}
        result = compare_route_fingerprints(current, baseline)
        assert result["counts"]["changed"] == 1


# ---------------------------------------------------------------------------
# load_route_fingerprint / write_route_fingerprint
# ---------------------------------------------------------------------------


class TestFingerprintIO:
    def test_roundtrip(self, tmp_path: Path) -> None:
        payload = {"kind": "route-fingerprint", "fingerprint": "abc", "routes": []}
        out = tmp_path / "fp.json"
        write_route_fingerprint(payload, out)
        loaded = load_route_fingerprint(out)
        assert loaded["fingerprint"] == "abc"

    def test_wrapped_payload(self, tmp_path: Path) -> None:
        wrapped = {"payload": {"kind": "route-fingerprint", "fingerprint": "xyz"}}
        out = tmp_path / "fp.json"
        out.write_text(json.dumps(wrapped), encoding="utf-8")
        loaded = load_route_fingerprint(out)
        assert loaded["fingerprint"] == "xyz"

    def test_invalid_kind(self, tmp_path: Path) -> None:
        out = tmp_path / "fp.json"
        out.write_text('{"kind": "other"}', encoding="utf-8")
        with pytest.raises(ValueError, match="unsupported"):
            load_route_fingerprint(out)

    def test_non_dict(self, tmp_path: Path) -> None:
        out = tmp_path / "fp.json"
        out.write_text('"string"', encoding="utf-8")
        with pytest.raises(ValueError, match="must be a JSON object"):
            load_route_fingerprint(out)


# ---------------------------------------------------------------------------
# _route_group
# ---------------------------------------------------------------------------


class TestRouteGroup:
    def test_from_group_annotation(self, tmp_path: Path) -> None:
        f = tmp_path / "ro_hosts.go"
        f.write_text('Group("hosts")\nGET("/list", handler)\n', encoding="utf-8")
        assert _route_group(f) == "hosts"

    def test_fallback_to_stem(self, tmp_path: Path) -> None:
        f = tmp_path / "ro_custom.go"
        f.write_text("// no group annotation\n", encoding="utf-8")
        assert _route_group(f) == "custom"


# ---------------------------------------------------------------------------
# Golden test
# ---------------------------------------------------------------------------


@pytest.mark.golden
class TestOnepanelProviderGolden:
    def test_full_impact_analysis(self) -> None:
        """Full route set with multiple groups produces correct summary."""
        routes = [
            {"group": "containers", "path": "/containers/list", "method": "GET", "handler": "h1"},
            {"group": "websites", "path": "/websites/list", "method": "GET", "handler": "h2"},
            {"group": "hosts", "path": "/hosts/firewall", "method": "GET", "handler": "h3"},
        ]
        for r in routes:
            r["impact"] = _route_impact(r)

        summary = _impact_summary(routes)
        assert summary["route_count"] == 3
        assert summary["highest_priority"] == "P0"
        groups = {g["group"]: g["routes"] for g in summary["groups"]}
        assert groups["containers"] == 1
        assert groups["websites"] == 1
