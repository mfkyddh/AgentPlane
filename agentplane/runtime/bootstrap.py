from __future__ import annotations

from pathlib import Path
from typing import Any

from agentplane.runtime.wsl_bridge import inspect_local_host


BOOTSTRAP_TARGETS = ("wsl", "prod0-main", "prod2-main")


def bootstrap_template_specs(repo_root: Path) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = [
        {
            "secret_ref": "local/control-plane/prod-jump",
            "template": repo_root / "templates" / "env" / "prod-jump.env.example",
            "destination": repo_root / "secrets" / "env" / "prod-jump.env",
            "placeholder_markers": ("REPLACE_WITH_", "replace-with-"),
            "required_fragments": ("CLOUDFLARE_API_TOKEN=",),
        },
        {
            "secret_ref": "local/control-plane/ssh-config",
            "template": repo_root / "templates" / "ssh" / "config.example",
            "destination": repo_root / "secrets" / "ssh" / "config",
            "placeholder_markers": ("REPLACE_WITH_",),
            "required_fragments": ("Host prod0-main",),
        },
    ]
    for target in BOOTSTRAP_TARGETS:
        specs.append(
            {
                "secret_ref": f"targets/{target}/onepanel-login",
                "template": repo_root / "templates" / "services" / "onepanel-login.env.example",
                "destination": repo_root / "secrets" / "services" / f"onepanel-login.{target}.env",
                "placeholder_markers": ("replace-with-",),
                "required_fragments": ("ONEPANEL_USERNAME=", "ONEPANEL_PASSWORD="),
            }
        )
    return specs


def bootstrap_directory_specs(repo_root: Path) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = [
        {
            "scope": "local/control-plane",
            "target": None,
            "template": repo_root / "templates" / "secrets" / "local" / "control-plane" / "README.md",
            "destination": repo_root / "secrets" / "local" / "control-plane" / "README.md",
        }
    ]
    for target in BOOTSTRAP_TARGETS:
        specs.append(
            {
                "scope": f"targets/{target}",
                "target": target,
                "template": repo_root / "templates" / "secrets" / "targets" / "_template" / "README.md",
                "destination": repo_root / "secrets" / "targets" / target / "README.md",
            }
        )
    return specs


def inspect_local_bootstrap(repo_root: Path) -> dict[str, Any]:
    payload = inspect_local_host(repo_root)
    payload["bootstrap_targets"] = list(BOOTSTRAP_TARGETS)
    payload["secret_templates"] = [
        {
            "secret_ref": item["secret_ref"],
            "destination": str(item["destination"]),
        }
        for item in bootstrap_template_specs(repo_root)
    ]
    return payload


def bootstrap_doctor_payload(repo_root: Path, *, secrets_status: dict[str, Any]) -> dict[str, Any]:
    inspect_payload = inspect_local_bootstrap(repo_root)
    ok = bool(secrets_status.get("ok"))
    next_steps = []
    if not ok:
        next_steps.append("运行 `bootstrap init-secrets` 生成空壳，并填写缺失的 secrets。")
        next_steps.append("填写完成后重新运行 `bootstrap verify-secrets`。")
    else:
        next_steps.append("bootstrap 已完成，可以让 Agent 接管后续 domain 动作。")
    return {
        "ok": ok,
        "inspect_local": inspect_payload,
        "secrets": secrets_status,
        "next_steps": next_steps,
    }
