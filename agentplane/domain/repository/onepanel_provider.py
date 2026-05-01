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
            routes.append(route)
            groups[group]["routes"] += 1

    routes = sorted(routes, key=_route_sort_key)
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

    return {
        "baseline_fingerprint": baseline.get("fingerprint"),
        "current_fingerprint": current.get("fingerprint"),
        "changed": baseline.get("fingerprint") != current.get("fingerprint"),
        "counts": {
            "added": len(added_keys),
            "removed": len(removed_keys),
            "changed": len(changed_keys),
        },
        "added": [current_routes[key] for key in added_keys],
        "removed": [baseline_routes[key] for key in removed_keys],
        "changed_routes": [
            {
                "route": key,
                "before": baseline_routes[key],
                "after": current_routes[key],
            }
            for key in changed_keys
        ],
    }
