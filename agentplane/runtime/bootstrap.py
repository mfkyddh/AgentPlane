from __future__ import annotations

import shutil
from pathlib import Path, PurePosixPath
from typing import Any

from agentplane.runtime.wsl_bridge import inspect_local_host

_PLACEHOLDER_MARKERS = (
    "REPLACE_WITH_",
    "replace-with-",
    "your-project-name",
    "your-app",
    "example.com",
)


def _normalize_text(value: str) -> str:
    return value.strip().strip('"').strip("'")


def _looks_like_placeholder(value: str | None) -> bool:
    if value is None:
        return True
    normalized = _normalize_text(value)
    if not normalized:
        return True
    lowered = normalized.lower()
    return any(marker.lower() in lowered for marker in _PLACEHOLDER_MARKERS)


def _parse_shell_assignments(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = _normalize_text(value)
    return values


def _parse_ssh_config(text: str) -> dict[str, dict[str, str]]:
    stanzas: dict[str, dict[str, str]] = {}
    active_hosts: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        keyword = parts[0].lower()
        if keyword == "host":
            active_hosts = parts[1].split() if len(parts) > 1 else []
            for alias in active_hosts:
                stanzas.setdefault(alias, {})
            continue
        if not active_hosts or len(parts) < 2:
            continue
        value = parts[1].strip()
        for alias in active_hosts:
            stanzas.setdefault(alias, {})[keyword] = value

    return stanzas


def bootstrap_target_names(repo_root: Path) -> tuple[str, ...]:
    inventory_root = repo_root / "inventory" / "servers"
    targets = sorted(
        {
            path.parent.name
            for path in inventory_root.glob("*/inventory.json")
            if path.is_file()
        },
        key=lambda value: (value != "wsl", value),
    )
    if not targets:
        return ("wsl",)
    return tuple(targets)


def bootstrap_required_truth_specs(repo_root: Path) -> list[dict[str, Any]]:
    return [
        {
            "secret_ref": "local/control-plane/ssh-config",
            "template": repo_root / "templates" / "ssh" / "config.example",
            "destination": repo_root / "secrets" / "ssh" / "config",
            "description": "Agent takeover 所需的 SSH alias 与 key 引用。",
        }
    ]


def bootstrap_projection_specs(repo_root: Path) -> list[dict[str, Any]]:
    return [
        {
            "secret_ref": "projection/control-plane/prod-jump",
            "template": repo_root / "templates" / "env" / "prod-jump.env.example",
            "destination": repo_root / "secrets" / "env" / "prod-jump.env",
            "description": "兼容旧 shell flow 的 projection 文件，不是 bootstrap truth。",
        }
    ]


def bootstrap_manual_only_specs() -> list[dict[str, str]]:
    return [
        {
            "secret_ref": "targets/<target>/onepanel-login",
            "description": "人工浏览器登录辅助材料；不参与 bootstrap readiness，也不是 host truth。",
        }
    ]


def bootstrap_directory_specs(repo_root: Path) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = [
        {
            "scope": "local/control-plane",
            "target": None,
            "template": repo_root / "templates" / "secrets" / "local" / "control-plane" / "README.md",
            "destination": repo_root / "secrets" / "local" / "control-plane" / "README.md",
        }
    ]
    for target in bootstrap_target_names(repo_root):
        specs.append(
            {
                "scope": f"targets/{target}",
                "target": target,
                "template": repo_root / "templates" / "secrets" / "targets" / "_template" / "README.md",
                "destination": repo_root / "secrets" / "targets" / target / "README.md",
            }
        )
    return specs


def _contract_payload(repo_root: Path) -> dict[str, Any]:
    return {
        "required_truths": [
            {
                "secret_ref": item["secret_ref"],
                "destination": str(item["destination"]),
                "description": item["description"],
            }
            for item in bootstrap_required_truth_specs(repo_root)
        ],
        "projection_only": [
            {
                "secret_ref": item["secret_ref"],
                "destination": str(item["destination"]),
                "description": item["description"],
            }
            for item in bootstrap_projection_specs(repo_root)
        ],
        "manual_only": bootstrap_manual_only_specs(),
    }


def _expected_legacy_control_root(inspect_payload: dict[str, Any]) -> str | None:
    workspace = inspect_payload.get("workspace", {})
    rendered = workspace.get("legacy_control_root") or workspace.get("linux_backend_root")
    if not rendered:
        return None
    return str(rendered).replace("\\", "/").rstrip("/")


def _check_required_ssh_contract(repo_root: Path, *, inspect_payload: dict[str, Any]) -> dict[str, Any]:
    spec = bootstrap_required_truth_specs(repo_root)[0]
    path = Path(spec["destination"])
    if not path.is_file():
        return {
            "path": str(path),
            "exists": False,
            "ok": False,
            "issues": ["missing"],
            "secret_ref": spec["secret_ref"],
        }

    text = path.read_text(encoding="utf-8")
    stanzas = _parse_ssh_config(text)
    tracked_targets = tuple(target for target in bootstrap_target_names(repo_root) if target != "wsl")
    issues: list[str] = []

    for target in tracked_targets:
        stanza = stanzas.get(target)
        if stanza is None:
            issues.append(f"missing-ssh-host:{target}")
            continue
        hostname = stanza.get("hostname")
        identity_file = stanza.get("identityfile")
        if _looks_like_placeholder(hostname):
            issues.append(f"placeholder-hostname:{target}")
        if _looks_like_placeholder(identity_file):
            issues.append(f"placeholder-identityfile:{target}")
            continue
        key_name = PurePosixPath(_normalize_text(identity_file)).name
        if not key_name:
            issues.append(f"missing-ssh-key:{target}")
            continue
        key_path = repo_root / "secrets" / "ssh" / "keys" / key_name
        if not key_path.is_file():
            issues.append(f"missing-ssh-key:{key_name}")

    return {
        "path": str(path),
        "exists": True,
        "ok": not issues,
        "issues": issues,
        "secret_ref": spec["secret_ref"],
    }


def verify_bootstrap_truths(repo_root: Path) -> dict[str, Any]:
    inspect_payload = inspect_local_bootstrap(repo_root)
    checks = [_check_required_ssh_contract(repo_root, inspect_payload=inspect_payload)]
    return {
        "ok": all(item["ok"] for item in checks),
        "repo_root": str(repo_root),
        "checks": checks,
    }


def inspect_bootstrap_projections(repo_root: Path, *, inspect_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = inspect_payload or inspect_local_bootstrap(repo_root)
    legacy_root = _expected_legacy_control_root(payload)
    checks: list[dict[str, Any]] = []

    for spec in bootstrap_projection_specs(repo_root):
        path = Path(spec["destination"])
        if not path.is_file():
            checks.append(
                {
                    "path": str(path),
                    "exists": False,
                    "ok": True,
                    "issues": [],
                    "secret_ref": spec["secret_ref"],
                }
            )
            continue

        values = _parse_shell_assignments(path.read_text(encoding="utf-8"))
        issues: list[str] = []
        project_ssh_config = values.get("PROJECT_SSH_CONFIG")
        if legacy_root is not None:
            expected_ssh_config = f"{legacy_root}/secrets/ssh/config"
            if project_ssh_config and project_ssh_config.replace("\\", "/") != expected_ssh_config:
                issues.append("drift:PROJECT_SSH_CONFIG")
            prod_ssh_key = values.get("PROD_SSH_KEY")
            if prod_ssh_key and not prod_ssh_key.replace("\\", "/").startswith(f"{legacy_root}/secrets/ssh/keys/"):
                issues.append("drift:PROD_SSH_KEY")
        elif project_ssh_config:
            issues.append("unbound:PROJECT_SSH_CONFIG")
            prod_ssh_key = values.get("PROD_SSH_KEY")
            if prod_ssh_key:
                issues.append("unbound:PROD_SSH_KEY")

        checks.append(
            {
                "path": str(path),
                "exists": True,
                "ok": not issues,
                "issues": issues,
                "secret_ref": spec["secret_ref"],
            }
        )

    return {
        "ok": all(item["ok"] for item in checks),
        "repo_root": str(repo_root),
        "checks": checks,
    }


def inspect_local_bootstrap(repo_root: Path) -> dict[str, Any]:
    payload = inspect_local_host(repo_root)
    payload["bootstrap_targets"] = list(bootstrap_target_names(repo_root))
    payload["contract"] = _contract_payload(repo_root)
    payload["cli_entrypoint"] = inspect_cli_entrypoint(repo_root)
    return payload


def inspect_cli_entrypoint(repo_root: Path) -> dict[str, Any]:
    executable = shutil.which("agentplane")
    fallback_commands = [
        "uv run python -m agentplane.cli",
        "python -m agentplane.cli",
    ]
    install_command = f"uv tool install -e {repo_root}"
    return {
        "command": "agentplane",
        "available": executable is not None,
        "executable": executable,
        "fallback_commands": fallback_commands,
        "install_command": install_command,
        "recommendation": (
            "`agentplane` is available on PATH."
            if executable is not None
            else "Install the editable tool or use a fallback command when PATH does not expose `agentplane`."
        ),
    }


def bootstrap_doctor_payload(repo_root: Path, *, secrets_status: dict[str, Any]) -> dict[str, Any]:
    inspect_payload = inspect_local_bootstrap(repo_root)
    projection_status = inspect_bootstrap_projections(repo_root, inspect_payload=inspect_payload)
    cli_entrypoint = inspect_payload.get("cli_entrypoint", {})
    readiness_checks = [
        {
            "name": "linux-backend-ready",
            "severity": "blocker",
            "ok": bool(inspect_payload.get("linux_backend", {}).get("available")),
            "details": "本机 formal backend 可用于后续 Agent 执行。",
        },
        {
            "name": "bootstrap-truths-ready",
            "severity": "blocker",
            "ok": bool(secrets_status.get("ok")),
            "details": "bootstrap 只校验 Agent takeover 所需的正式 truths。",
        },
        {
            "name": "projection-compat",
            "severity": "warning",
            "ok": bool(projection_status.get("ok")),
            "details": "projection/compat 文件存在漂移不会阻断 takeover，但需要在相关 flow 里显式修正。",
        },
        {
            "name": "global-cli-entrypoint",
            "severity": "warning",
            "ok": bool(cli_entrypoint.get("available")),
            "details": "`agentplane` 不在 PATH 时，可使用 `uv run python -m agentplane.cli ...` fallback。",
        },
    ]

    ok = all(check["ok"] for check in readiness_checks if check["severity"] == "blocker")
    next_steps: list[str] = []
    if not ok:
        if not bool(inspect_payload.get("linux_backend", {}).get("available")):
            next_steps.append("先修复当前宿主的 Linux backend 可用性，再继续 bootstrap。")
        if not bool(secrets_status.get("ok")):
            next_steps.append("运行 `bootstrap init-secrets` 生成 takeover truth scaffold，并补齐 SSH config/key。")
            next_steps.append("填写完成后重新运行 `bootstrap verify-secrets`。")
    else:
        next_steps.append("bootstrap truths 已就绪，可以让 Agent 接管后续 domain 动作。")
    if not bool(projection_status.get("ok")):
        next_steps.append("若后续 flow 仍依赖 projection/compat 文件，再按 doctor 的 warning 单独修正。")
    if not bool(cli_entrypoint.get("available")):
        next_steps.append("可运行 `uv tool install -e <repo-root>` 注册全局 `agentplane`，或继续使用模块 fallback。")

    return {
        "ok": ok,
        "inspect_local": inspect_payload,
        "secrets": secrets_status,
        "projections": projection_status,
        "readiness_checks": readiness_checks,
        "next_steps": next_steps,
    }
