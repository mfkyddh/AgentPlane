from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

ROUTE_FILE_PATTERN = "ro_*.go"
GROUP_RE = re.compile(r'\bGroup\("(?P<group>[^"]+)"\)')
ROUTE_RE = re.compile(r'\b(?P<method>GET|POST|PUT|DELETE|PATCH)\("(?P<path>[^"]*)"\s*,\s*(?P<handler>[A-Za-z0-9_.]+)\)')
PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "deferred": 4}

GROUP_IMPACTS: dict[str, dict[str, Any]] = {
    "ai": {
        "priority": "deferred",
        "surfaces": [],
        "policy": "defer",
        "reason": "1Panel AI routes are outside the current AgentPlane control-plane expansion path.",
    },
    "alert": {
        "priority": "P3",
        "surfaces": ["infra.audit"],
        "policy": "evidence-only",
        "reason": "Alert state can enrich health evidence after core runtime checks are stable.",
    },
    "apps": {
        "priority": "P2",
        "surfaces": ["app.object", "app.delivery"],
        "policy": "read-only-first",
        "reason": "Installed app and catalog routes can map to app catalog objects and delivery plans.",
    },
    "containers": {
        "priority": "P0",
        "surfaces": ["service", "app.delivery"],
        "policy": "read-only-first",
        "reason": "Container and compose routes back service runtime evidence and app delivery verification.",
    },
    "cronjobs": {
        "priority": "P0",
        "surfaces": ["infra.automation"],
        "policy": "read-only-first",
        "reason": "Cronjob routes back backup, renewal, and cleanup automation health checks.",
    },
    "dashboard": {
        "priority": "P3",
        "surfaces": ["infra.audit"],
        "policy": "evidence-only",
        "reason": "Dashboard metrics can become structured evidence but are not a first write surface.",
    },
    "databases": {
        "priority": "P1",
        "surfaces": ["app.resource"],
        "policy": "read-only-first",
        "reason": "Database routes can validate app resource declarations and secret projection consistency.",
    },
    "files": {
        "priority": "deferred",
        "surfaces": [],
        "policy": "defer",
        "reason": "File-manager style routes carry broad permission risk and are not part of the first expansion.",
    },
    "groups": {
        "priority": "P3",
        "surfaces": ["infra.audit"],
        "policy": "evidence-only",
        "reason": "Grouping metadata may help inventory presentation but is not a core lifecycle surface.",
    },
    "hosts": {
        "priority": "P1",
        "surfaces": ["infra"],
        "policy": "read-only-first",
        "reason": "Host routes back infrastructure inventory, firewall, SSH, monitor, and disk evidence.",
    },
    "logs": {
        "priority": "P3",
        "surfaces": ["infra.audit"],
        "policy": "evidence-only",
        "reason": "Logs are supporting evidence and should not become a broad public surface first.",
    },
    "openresty": {
        "priority": "P0",
        "surfaces": ["ingress"],
        "policy": "read-only-first",
        "reason": "OpenResty routes affect public ingress verification and reload evidence.",
    },
    "process": {
        "priority": "P3",
        "surfaces": ["infra.audit"],
        "policy": "evidence-only",
        "reason": "Process routes are useful for diagnostics after formal lifecycle checks are stable.",
    },
    "router": {
        "priority": "deferred",
        "surfaces": [],
        "policy": "provider-debug",
        "reason": "Router metadata is provider plumbing rather than a user-facing object surface.",
    },
    "runtimes": {
        "priority": "P2",
        "surfaces": ["app.delivery", "service"],
        "policy": "read-only-first",
        "reason": "Runtime routes matter when app delivery explicitly depends on PHP or Node runtime state.",
    },
    "settings": {
        "priority": "P3",
        "surfaces": ["infra"],
        "policy": "threat-model-first",
        "reason": "Panel settings, backup, and snapshot routes are high blast-radius operations.",
    },
    "toolbox": {
        "priority": "P3",
        "surfaces": ["infra.audit"],
        "policy": "evidence-only",
        "reason": "Toolbox routes are diagnostics-oriented and should follow core health checks.",
    },
    "websites": {
        "priority": "P0",
        "surfaces": ["ingress"],
        "policy": "read-only-first",
        "reason": "Website routes back public ingress objects, origin state, and publish/reconcile checks.",
    },
    "websites/acme": {
        "priority": "P1",
        "surfaces": ["ingress"],
        "policy": "read-only-first",
        "reason": "ACME account routes affect certificate issuance evidence for ingress.",
    },
    "websites/ca": {
        "priority": "P2",
        "surfaces": ["ingress"],
        "policy": "read-only-first",
        "reason": "CA routes are certificate evidence but less common than website HTTPS checks.",
    },
    "websites/dns": {
        "priority": "P1",
        "surfaces": ["ingress"],
        "policy": "read-only-first",
        "reason": "DNS account routes affect certificate and public ingress verification.",
    },
    "websites/ssl": {
        "priority": "P0",
        "surfaces": ["ingress"],
        "policy": "read-only-first",
        "reason": "SSL routes back HTTPS state and certificate evidence for public ingress.",
    },
}

PATH_IMPACT_RULES: tuple[tuple[str, dict[str, Any]], ...] = (
    (
        "/hosts/firewall",
        {
            "priority": "P0",
            "surfaces": ["infra.network"],
            "policy": "read-only-first",
            "reason": "Firewall routes directly affect exposed-port drift checks.",
        },
    ),
    (
        "/hosts/ssh",
        {
            "priority": "P1",
            "surfaces": ["infra.remote", "infra.audit"],
            "policy": "read-only-first",
            "reason": "SSH routes affect host access posture and remote execution readiness.",
        },
    ),
    (
        "/hosts/monitor",
        {
            "priority": "P2",
            "surfaces": ["infra.audit"],
            "policy": "evidence-only",
            "reason": "Monitor routes can enrich host health evidence after P0 checks.",
        },
    ),
    (
        "/hosts/disks",
        {
            "priority": "P2",
            "surfaces": ["infra.audit"],
            "policy": "evidence-only",
            "reason": "Disk routes can enrich host inventory and capacity checks.",
        },
    ),
)


def _git_value(source_root: Path, *args: str) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(source_root), *args],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None


def _git_snapshot(source_root: Path) -> dict[str, str | None]:
    return {
        "branch": _git_value(source_root, "branch", "--show-current"),
        "head": _git_value(source_root, "rev-parse", "HEAD"),
        "commit_time": _git_value(source_root, "log", "-1", "--format=%cI"),
        "subject": _git_value(source_root, "log", "-1", "--format=%s"),
    }


def _route_group(route_file: Path) -> str:
    text = route_file.read_text(encoding="utf-8")
    match = GROUP_RE.search(text)
    if match:
        return match.group("group")
    return route_file.stem.removeprefix("ro_")


def _join_route_path(group: str, route_path: str) -> str:
    prefix = "/" + group.strip("/")
    if not route_path:
        return prefix
    suffix = route_path if route_path.startswith("/") else f"/{route_path}"
    return f"{prefix}{suffix}"


def _route_sort_key(route: dict[str, str]) -> tuple[str, str, str]:
    return (route["path"], route["method"], route["handler"])


def _fingerprint_routes(routes: list[dict[str, str]]) -> str:
    canonical = [
        {
            "group": route["group"],
            "handler": route["handler"],
            "method": route["method"],
            "path": route["path"],
        }
        for route in sorted(routes, key=_route_sort_key)
    ]
    body = json.dumps(canonical, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def _normalize_impact(impact: dict[str, Any]) -> dict[str, Any]:
    return {
        "priority": str(impact["priority"]),
        "surfaces": sorted(str(surface) for surface in impact.get("surfaces", [])),
        "policy": str(impact["policy"]),
        "reason": str(impact["reason"]),
    }


def _route_impact(route: dict[str, Any]) -> dict[str, Any]:
    route_path = str(route.get("path", ""))
    for prefix, impact in PATH_IMPACT_RULES:
        if route_path.startswith(prefix):
            return _normalize_impact(impact)
    group = str(route.get("group", ""))
    return _normalize_impact(
        GROUP_IMPACTS.get(
            group,
            {
                "priority": "P3",
                "surfaces": ["infra.audit"],
                "policy": "classify-before-expand",
                "reason": "Unclassified 1Panel route group; inspect before wiring to a formal surface.",
            },
        )
    )


def _impact_sort_key(impact: dict[str, Any]) -> tuple[int, str]:
    return (PRIORITY_ORDER.get(str(impact["priority"]), 99), ",".join(impact.get("surfaces", [])))


def _impact_summary(routes: list[dict[str, Any]]) -> dict[str, Any]:
    route_count = len(routes)
    groups: dict[str, int] = {}
    priorities: dict[str, int] = {}
    surfaces: dict[str, int] = {}
    policies: dict[str, int] = {}
    highest_priority = "deferred"

    for route in routes:
        group = str(route.get("group", "unknown"))
        groups[group] = groups.get(group, 0) + 1
        impact = route.get("impact") if isinstance(route.get("impact"), dict) else _route_impact(route)
        priority = str(impact["priority"])
        priorities[priority] = priorities.get(priority, 0) + 1
        if PRIORITY_ORDER.get(priority, 99) < PRIORITY_ORDER.get(highest_priority, 99):
            highest_priority = priority
        policy = str(impact["policy"])
        policies[policy] = policies.get(policy, 0) + 1
        for surface in impact.get("surfaces", []):
            surface_name = str(surface)
            surfaces[surface_name] = surfaces.get(surface_name, 0) + 1

    return {
        "route_count": route_count,
        "highest_priority": highest_priority if route_count else None,
        "groups": [{"group": key, "routes": groups[key]} for key in sorted(groups)],
        "priorities": [
            {"priority": key, "routes": priorities[key]}
            for key in sorted(priorities, key=lambda item: PRIORITY_ORDER.get(item, 99))
        ],
        "surfaces": [{"surface": key, "routes": surfaces[key]} for key in sorted(surfaces)],
        "policies": [{"policy": key, "routes": policies[key]} for key in sorted(policies)],
    }


def _impact_matrix() -> list[dict[str, Any]]:
    return [
        {
            "group": group,
            **_normalize_impact(impact),
        }
        for group, impact in sorted(GROUP_IMPACTS.items(), key=lambda item: item[0])
    ]


def build_onepanel_route_fingerprint(source_root: Path) -> dict[str, Any]:
    resolved_source = source_root.resolve()
    router_root = resolved_source / "agent" / "router"
    if not router_root.is_dir():
        raise ValueError(f"1Panel router directory not found: {router_root}")

    routes: list[dict[str, str]] = []
    groups: dict[str, dict[str, Any]] = {}
    route_files = sorted(router_root.glob(ROUTE_FILE_PATTERN))
    for route_file in route_files:
        group = _route_group(route_file)
        rel_file = route_file.relative_to(resolved_source).as_posix()
        groups.setdefault(group, {"group": group, "file": rel_file, "routes": 0})
        text = route_file.read_text(encoding="utf-8")
        for match in ROUTE_RE.finditer(text):
            route = {
                "file": rel_file,
                "group": group,
                "handler": match.group("handler"),
                "method": match.group("method"),
                "path": _join_route_path(group, match.group("path")),
            }
            route["impact"] = _route_impact(route)
            routes.append(route)
            groups[group]["routes"] += 1

    routes = sorted(routes, key=_route_sort_key)
    for group_item in groups.values():
        group_routes = [route for route in routes if route["group"] == group_item["group"]]
        group_item["impact"] = min(
            (route["impact"] for route in group_routes),
            key=_impact_sort_key,
            default=_route_impact({"group": group_item["group"], "path": ""}),
        )
    group_items = sorted(groups.values(), key=lambda item: (-int(item["routes"]), str(item["group"])))
    return {
        "schema_version": 1,
        "provider": "onepanel",
        "kind": "route-fingerprint",
        "source_root": str(resolved_source),
        "router_root": str(router_root),
        "git": _git_snapshot(resolved_source),
        "fingerprint": _fingerprint_routes(routes),
        "route_count": len(routes),
        "group_count": len(group_items),
        "groups": group_items,
        "impact_matrix": _impact_matrix(),
        "impact_summary": _impact_summary(routes),
        "routes": routes,
    }


def load_route_fingerprint(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("payload"), dict):
        payload = data["payload"]
    else:
        payload = data
    if not isinstance(payload, dict):
        raise ValueError(f"route fingerprint must be a JSON object: {path}")
    if payload.get("kind") != "route-fingerprint":
        raise ValueError(f"unsupported provider fingerprint kind in {path}")
    return payload


def write_route_fingerprint(payload: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def compare_route_fingerprints(current: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    current_routes = {f"{item['method']} {item['path']}": item for item in current.get("routes", [])}
    baseline_routes = {f"{item['method']} {item['path']}": item for item in baseline.get("routes", [])}

    added_keys = sorted(set(current_routes) - set(baseline_routes))
    removed_keys = sorted(set(baseline_routes) - set(current_routes))
    common_keys = sorted(set(current_routes) & set(baseline_routes))
    changed_keys = [
        key
        for key in common_keys
        if current_routes[key].get("handler") != baseline_routes[key].get("handler")
        or current_routes[key].get("group") != baseline_routes[key].get("group")
    ]
    added_routes = [current_routes[key] for key in added_keys]
    removed_routes = [baseline_routes[key] for key in removed_keys]
    changed_routes = [current_routes[key] for key in changed_keys]

    return {
        "baseline_fingerprint": baseline.get("fingerprint"),
        "current_fingerprint": current.get("fingerprint"),
        "changed": baseline.get("fingerprint") != current.get("fingerprint"),
        "counts": {
            "added": len(added_keys),
            "removed": len(removed_keys),
            "changed": len(changed_keys),
        },
        "impact": _impact_summary([*added_routes, *removed_routes, *changed_routes]),
        "added": added_routes,
        "removed": removed_routes,
        "changed_routes": [
            {
                "route": key,
                "before": baseline_routes[key],
                "after": current_routes[key],
            }
            for key in changed_keys
        ],
    }
