from __future__ import annotations

import json
import shlex
import sys
from pathlib import Path
from typing import Any

from agentplane.adapters.cloudflare import CloudflareClient, load_shell_env_file
from agentplane.adapters.service.common import run_shell_command
from agentplane.domain.service.registry import resolve_service
from agentplane.scripts.internal.ensure_cloudflare_dns_record import ensure_cloudflare_dns_record


def verify_service_public_endpoint(
    repo_root: Path,
    target: str,
    name: str,
    *,
    cloudflare_env_file: Path | None,
) -> dict[str, Any]:
    definition, declared = resolve_service(repo_root, target, name)
    endpoint = _declared_public_endpoint(name, declared)
    checks: dict[str, dict[str, Any]] = {
        "public_endpoint_declared": {"ok": True},
    }
    evidence: list[dict[str, Any]] = []

    dns_contract = endpoint.get("dns")
    if isinstance(dns_contract, dict):
        if _string_value(dns_contract.get("provider")) != "cloudflare":
            raise ValueError(f"unsupported public endpoint dns provider for {name}")
        if cloudflare_env_file is None:
            raise ValueError("service public-endpoint verify requires --cloudflare-env-file for Cloudflare-backed DNS")
        client = CloudflareClient(load_shell_env_file(cloudflare_env_file)["CLOUDFLARE_API_TOKEN"])
        zone_name = _required_str(dns_contract.get("zone_name"), field="zone_name", subject=name)
        record_name = _required_str(endpoint.get("domain"), field="domain", subject=name)
        record_type = _required_str(dns_contract.get("record_type"), field="record_type", subject=name)
        dns_record = client.find_dns_record(zone_name=zone_name, record_name=record_name, record_type=record_type)
        expected_content = _required_str(dns_contract.get("record_content"), field="record_content", subject=name)
        expected_proxied = bool(dns_contract.get("proxied"))
        checks["dns_exists"] = {"ok": isinstance(dns_record, dict)}
        checks["dns_content"] = {
            "ok": isinstance(dns_record, dict) and dns_record.get("content") == expected_content,
            "actual": dns_record.get("content") if isinstance(dns_record, dict) else None,
            "expected": expected_content,
        }
        checks["dns_proxied"] = {
            "ok": isinstance(dns_record, dict) and bool(dns_record.get("proxied")) == expected_proxied,
            "actual": bool(dns_record.get("proxied")) if isinstance(dns_record, dict) else None,
            "expected": expected_proxied,
        }
        evidence.append({"cloudflare_dns_record": dns_record or {"found": False}})

    certificate = endpoint.get("certificate")
    if isinstance(certificate, dict):
        fullchain_path = _required_str(certificate.get("fullchain_path"), field="fullchain_path", subject=name)
        privkey_path = _required_str(certificate.get("privkey_path"), field="privkey_path", subject=name)
        renew_script_path = _required_str(certificate.get("renew_script_path"), field="renew_script_path", subject=name)
        renew_cron = _required_str(certificate.get("renew_cron"), field="renew_cron", subject=name)

        fullchain_probe = run_shell_command(repo_root, target, f"test -r {shlex.quote(fullchain_path)}")
        privkey_probe = run_shell_command(repo_root, target, f"test -r {shlex.quote(privkey_path)}")
        renew_script_probe = run_shell_command(repo_root, target, f"test -x {shlex.quote(renew_script_path)}")
        renew_cron_probe = run_shell_command(repo_root, target, f"crontab -l | grep -F -- {shlex.quote(renew_cron)}")
        checks["cert_fullchain_readable"] = {"ok": bool(fullchain_probe.get("ok")), "path": fullchain_path}
        checks["cert_privkey_readable"] = {"ok": bool(privkey_probe.get("ok")), "path": privkey_path}
        checks["renew_script_executable"] = {"ok": bool(renew_script_probe.get("ok")), "path": renew_script_path}
        checks["renew_cron_present"] = {"ok": bool(renew_cron_probe.get("ok")), "expected": renew_cron}
        evidence.extend([fullchain_probe, privkey_probe, renew_script_probe, renew_cron_probe])

    failures = [name for name, item in checks.items() if not bool(item.get("ok"))]
    return {
        "ok": not failures,
        "service": {
            "name": definition.name,
            "control_plane": definition.control_plane,
            "kind": definition.runtime_kind,
        },
        "public_endpoint": endpoint,
        "checks": checks,
        "evidence": evidence,
        "failures": failures,
    }


def plan_service_public_endpoint(
    repo_root: Path,
    target: str,
    name: str,
    *,
    cloudflare_env_file: Path,
) -> dict[str, Any]:
    definition, declared = resolve_service(repo_root, target, name)
    endpoint = _declared_public_endpoint(name, declared)
    dns_contract = _declared_cloudflare_dns(name, endpoint)
    script_path = repo_root / "agentplane" / "scripts" / "internal" / "ensure_cloudflare_dns_record.py"
    zone_name = _required_str(dns_contract.get("zone_name"), field="zone_name", subject=name)
    record_name = _required_str(endpoint.get("domain"), field="domain", subject=name)
    record_type = _required_str(dns_contract.get("record_type"), field="record_type", subject=name)
    record_content = _required_str(dns_contract.get("record_content"), field="record_content", subject=name)
    proxied = bool(dns_contract.get("proxied"))
    argv = [
        sys.executable,
        str(script_path),
        "--cloudflare-env-file",
        str(cloudflare_env_file),
        "--zone-name",
        zone_name,
        "--record-name",
        record_name,
        "--record-type",
        record_type,
        "--record-content",
        record_content,
        "--proxied",
        "true" if proxied else "false",
    ]
    display = " ".join(shlex.quote(part) for part in argv)
    return {
        "service": {
            "name": definition.name,
            "control_plane": definition.control_plane,
            "kind": definition.runtime_kind,
        },
        "public_endpoint": endpoint,
        "operation": "reconcile",
        "steps": [
            {
                "argv": argv,
                "display": display,
                "inputs": {
                    "zone_name": zone_name,
                    "record_name": record_name,
                    "record_type": record_type,
                    "record_content": record_content,
                    "proxied": proxied,
                },
            }
        ],
        "verify_after_apply": {
            "command": "service public-endpoint verify",
            "args": {
                "target": target,
                "name": name,
                "cloudflare_env_file": str(cloudflare_env_file),
            },
        },
    }


def apply_service_public_endpoint(
    repo_root: Path,
    target: str,
    name: str,
    *,
    cloudflare_env_file: Path,
    execute: bool,
) -> dict[str, Any]:
    if not execute:
        raise ValueError("service public-endpoint apply requires --execute")
    plan = plan_service_public_endpoint(repo_root, target, name, cloudflare_env_file=cloudflare_env_file)
    results: list[dict[str, Any]] = []
    ok = True
    for step in plan["steps"]:
        try:
            parsed = ensure_cloudflare_dns_record(
                cloudflare_env_file=cloudflare_env_file,
                zone_name=step["inputs"]["zone_name"],
                record_name=step["inputs"]["record_name"],
                record_type=step["inputs"]["record_type"],
                record_content=step["inputs"]["record_content"],
                proxied=bool(step["inputs"]["proxied"]),
            )
            results.append(
                {
                    "argv": list(step["argv"]),
                    "display": str(step["display"]),
                    "returncode": 0,
                    "stdout": json.dumps(parsed, ensure_ascii=False, indent=2),
                    "stderr": "",
                    "ok": True,
                    "parsed": parsed,
                }
            )
        except Exception as exc:
            results.append(
                {
                    "argv": list(step["argv"]),
                    "display": str(step["display"]),
                    "returncode": 1,
                    "stdout": "",
                    "stderr": str(exc),
                    "ok": False,
                    "parsed": None,
                }
            )
            ok = False
            break

    verified = (
        verify_service_public_endpoint(repo_root, target, name, cloudflare_env_file=cloudflare_env_file)
        if ok
        else {"ok": False, "failures": ["apply_failed"]}
    )
    return {
        "ok": ok and bool(verified.get("ok")),
        "operation": "reconcile",
        "service": plan["service"],
        "public_endpoint": plan["public_endpoint"],
        "results": results,
        "verified": verified,
    }


def _declared_public_endpoint(service_name: str, declared: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(declared, dict):
        raise ValueError(f"service {service_name} does not exist in inventory")
    endpoint = declared.get("public_endpoint")
    if not isinstance(endpoint, dict):
        raise ValueError(f"service {service_name} has no public_endpoint contract")
    return endpoint


def _declared_cloudflare_dns(service_name: str, endpoint: dict[str, Any]) -> dict[str, Any]:
    dns_contract = endpoint.get("dns")
    if not isinstance(dns_contract, dict):
        raise ValueError(f"service {service_name} has no public_endpoint.dns contract")
    if _string_value(dns_contract.get("provider")) != "cloudflare":
        raise ValueError(f"service {service_name} requires public_endpoint.dns.provider=cloudflare")
    return dns_contract


def _string_value(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _required_str(value: Any, *, field: str, subject: str) -> str:
    resolved = _string_value(value)
    if not resolved:
        raise ValueError(f"service {subject} requires public endpoint field {field}")
    return resolved
