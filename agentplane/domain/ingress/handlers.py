from __future__ import annotations

from pathlib import Path
from typing import Any

from agentplane.domain.ingress.lifecycle import build_ingress_follow_through, summarize_ingress
from agentplane.domain.ingress.registry import available_ingresses, resolve_ingress
from agentplane.providers.gateway import default_provider_gateway


def _executor_for_target(target: str) -> object:
    return default_provider_gateway().onepanel_target_executor(target)

def _find_live_ingress(executor: object, alias: str) -> dict[str, Any] | None:
    provider = default_provider_gateway()
    payload = provider.search_onepanel_websites(executor, name=alias)
    items = payload.get("items")
    if not isinstance(items, list):
        raise RuntimeError("ingress search returned no items")
    for item in items:
        if isinstance(item, dict) and item.get("alias") == alias and "id" in item:
            return provider.get_onepanel_website(executor, website_id=int(item["id"]))
    return None


def search_ingresses(repo_root: Path, target: str) -> dict[str, Any]:
    items = [summarize_ingress(item) for item in available_ingresses(Path(repo_root).resolve(), target)]
    return {"items": items}


def get_ingress(repo_root: Path, target: str, alias: str) -> dict[str, Any]:
    definition = resolve_ingress(Path(repo_root).resolve(), target, alias)
    live = _find_live_ingress(_executor_for_target(target), alias)
    return {"ingress": summarize_ingress(definition), "live": live or {"found": False}}


def verify_ingress(repo_root: Path, target: str, alias: str) -> dict[str, Any]:
    definition = resolve_ingress(Path(repo_root).resolve(), target, alias)
    ingress = summarize_ingress(definition)
    live = _find_live_ingress(_executor_for_target(target), alias)
    if live is None:
        return {
            "ok": False,
            "ingress": ingress,
            "live": {"found": False},
            "checks": {"exists": {"ok": False}},
            "failures": ["missing"],
            "evidence": [{"kind": "declared", "value": ingress}],
        }

    live_ingress = live.get("ingress", {})
    live_https = live.get("https", {})
    actual_ssl = live_https.get("SSL", {}) if isinstance(live_https, dict) else {}
    checks: dict[str, dict[str, Any]] = {
        "alias": {"ok": live_ingress.get("alias") == definition.alias, "actual": live_ingress.get("alias"), "expected": definition.alias},
        "domain": {
            "ok": live_ingress.get("primaryDomain") == definition.primary_domain,
            "actual": live_ingress.get("primaryDomain"),
            "expected": definition.primary_domain,
        },
        "proxy": {"ok": live_ingress.get("proxy") == definition.proxy, "actual": live_ingress.get("proxy"), "expected": definition.proxy},
        "https": {"ok": bool(live_https.get("enable")), "actual": bool(live_https.get("enable")), "expected": True},
    }
    if definition.ssl_id is not None:
        checks["ssl_id"] = {
            "ok": actual_ssl.get("id") == definition.ssl_id,
            "actual": actual_ssl.get("id"),
            "expected": definition.ssl_id,
        }
    if definition.status:
        checks["status"] = {
            "ok": live_ingress.get("status") == definition.status,
            "actual": live_ingress.get("status"),
            "expected": definition.status,
        }
    failures = [name for name, item in checks.items() if not bool(item.get("ok"))]
    return {
        "ok": not failures,
        "ingress": ingress,
        "live": live,
        "checks": checks,
        "failures": failures,
        "evidence": [{"kind": "declared", "value": ingress}, {"kind": "live", "value": live}],
    }


def plan_ingress_operation(repo_root: Path, target: str, alias: str, operation: str) -> dict[str, Any]:
    if operation != "reconcile":
        raise ValueError(f"unsupported ingress operation: {operation}")

    definition = resolve_ingress(Path(repo_root).resolve(), target, alias)
    ingress = summarize_ingress(definition)
    verification = verify_ingress(repo_root, target, alias)
    if verification["ok"]:
        drift = {"status": "matched", "failures": []}
        steps: list[dict[str, Any]] = []
        warnings: list[str] = []
    elif verification["failures"] == ["missing"]:
        create_plan = default_provider_gateway().plan_onepanel_website_create(
            alias=definition.alias,
            domain=definition.primary_domain,
            proxy=definition.proxy,
            remark=f"{target} {definition.alias} public ingress",
            ipv6=True,
        )
        drift = {"status": "missing", "failures": ["missing"]}
        steps = [
            {
                "kind": "create",
                "path": create_plan.path,
                "body": {
                    "website_alias": definition.alias,
                    "domain": definition.primary_domain,
                    "proxy": definition.proxy,
                },
                "request": {"path": create_plan.path, "body": create_plan.body},
            }
        ]
        warnings = []
    else:
        drift = {"status": "drift", "failures": verification["failures"]}
        steps = []
        warnings = ["ingress reconcile execute only supports create or noop in v1"]
    return {
        "ingress": ingress,
        "operation": operation,
        "preflight": {"target": target, "alias": alias},
        "drift": drift,
        "warnings": warnings,
        "steps": steps,
        "verify_after_apply": {"alias": alias, "action": "verify"},
    }


def apply_ingress_operation(repo_root: Path, target: str, alias: str, operation: str, *, execute: bool) -> dict[str, Any]:
    if not execute:
        raise ValueError("ingress apply requires --execute")

    plan = plan_ingress_operation(repo_root, target, alias, operation)
    drift_status = plan["drift"]["status"]
    if drift_status == "matched":
        verified = verify_ingress(repo_root, target, alias)
        return {
            "ok": bool(verified.get("ok")),
            "ingress": plan["ingress"],
            "operation": operation,
            "result": {"action": "noop"},
            "verified": verified,
            "follow_through": build_ingress_follow_through(target, source_surface="ingress", alias=alias),
        }
    if drift_status == "drift":
        verified = verify_ingress(repo_root, target, alias)
        return {
            "ok": False,
            "ingress": plan["ingress"],
            "operation": operation,
            "result": {"action": "unsupported_drift"},
            "warnings": plan["warnings"],
            "verified": verified,
            "follow_through": build_ingress_follow_through(target, source_surface="ingress", alias=alias),
        }

    executor = _executor_for_target(target)
    step = plan["steps"][0]
    request = step["request"]
    response = executor.api_request("POST", request["path"], request["body"])
    verified = verify_ingress(repo_root, target, alias)
    return {
        "ok": bool(verified.get("ok")),
        "ingress": plan["ingress"],
        "operation": operation,
        "result": {"action": "created", "response": response},
        "verified": verified,
        "follow_through": build_ingress_follow_through(target, source_surface="ingress", alias=alias),
    }


def refresh_ingress_ledger(repo_root: Path, target: str, *, write: bool = False) -> dict[str, Any]:
    return default_provider_gateway().refresh_onepanel_ledgers(Path(repo_root).resolve(), target, write=write)
