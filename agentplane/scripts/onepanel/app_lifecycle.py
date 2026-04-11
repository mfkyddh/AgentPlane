#!/usr/bin/env python3
"""Compatibility entrypoint for historical 1Panel app lifecycle flows.

Formal AgentPlane runbooks should route through `uv run python -m agentplane.cli ...`.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from compose_policy import normalize_compose_for_app, requires_host_network
from env_targets import TargetConfig, build_api_request_command, get_target, supported_targets


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, capture_output=True, check=False)


class TargetExecutor:
    def __init__(self, target: TargetConfig) -> None:
        self.target = target

    def api_request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        command = build_api_request_command(self.target, method, path, body=body)
        if self.target.mode == "local":
            result = run_command(command)
        else:
            result = run_command(self.target.build_ssh_target().ssh_args_for_argv(command))
        if result.returncode != 0:
            raise RuntimeError(result.stdout.strip() or result.stderr.strip() or f"API command failed: {method} {path}")
        payload = json.loads(result.stdout)
        body_payload = payload["body"]
        if not isinstance(body_payload, dict) or body_payload.get("code") != 200:
            raise RuntimeError(json.dumps(payload, ensure_ascii=False))
        return body_payload["data"]

    def shell(self, command: str) -> str:
        if self.target.mode == "local":
            result = run_command(["bash", "-lc", command])
        else:
            result = run_command(self.target.build_ssh_target().ssh_args_for_shell(command))
        if result.returncode != 0:
            raise RuntimeError(result.stdout.strip() or result.stderr.strip() or f"Shell command failed: {command}")
        return result.stdout.strip()


def coerce_scalar(value: str) -> Any:
    if value.isdigit():
        return int(value)
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    return value


def parse_params(raw_items: list[str]) -> dict[str, Any]:
    params: dict[str, Any] = {}
    for item in raw_items:
        if "=" not in item:
            raise ValueError(f"Invalid --param value: {item}")
        key, value = item.split("=", 1)
        params[key] = coerce_scalar(value)
    return params


def app_meta(executor: TargetExecutor, app_key: str) -> dict[str, Any]:
    return executor.api_request("GET", f"/api/v2/apps/{app_key}")


def app_detail(executor: TargetExecutor, app_id: int, version: str, app_type: str) -> dict[str, Any]:
    return executor.api_request("GET", f"/api/v2/apps/detail/{app_id}/{version}/{app_type}")


def installed_apps(executor: TargetExecutor) -> list[dict[str, Any]]:
    return executor.api_request("GET", "/api/v2/apps/installed/list")


def find_install_id(executor: TargetExecutor, app_key: str, name: str | None) -> int:
    target_name = name or app_key
    for item in installed_apps(executor):
        if item.get("key") == app_key and item.get("name") == target_name:
            return int(item["id"])
    raise RuntimeError(f"Installed app not found for key={app_key} name={target_name}")


def installed_info(executor: TargetExecutor, install_id: int) -> dict[str, Any]:
    return executor.api_request("GET", f"/api/v2/apps/installed/info/{install_id}")


def installed_params(executor: TargetExecutor, install_id: int) -> dict[str, Any]:
    return executor.api_request("GET", f"/api/v2/apps/installed/params/{install_id}")


def build_default_params(detail: dict[str, Any]) -> dict[str, Any]:
    detail_params = detail.get("params")
    if not isinstance(detail_params, dict):
        return {}

    params = {}
    for field in detail_params.get("formFields", []):
        params[field["envKey"]] = field.get("default")
    return params


def build_params_from_installed(data: dict[str, Any]) -> dict[str, Any]:
    params = {}
    for field in data.get("params", []):
        params[field["key"]] = field.get("value")
    return params


def operation_payload(install_id: int, operate: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = {
        "installId": install_id,
        "operate": operate,
        "forceDelete": False,
        "deleteBackup": False,
        "deleteDB": False,
        "deleteImage": False,
        "backup": False,
        "pullImage": False,
        "dockerCompose": "",
        "favorite": False,
    }
    if extra:
        payload.update(extra)
    return payload


def wait_for_running(executor: TargetExecutor, install_id: int, timeout_seconds: int = 240) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        info = installed_info(executor, install_id)
        if info.get("status") == "Running":
            return info
        if info.get("status") in {"InstallErr", "UpErr", "Error"}:
            raise RuntimeError(json.dumps(info, ensure_ascii=False))
        time.sleep(2)
    raise TimeoutError(f"Timed out waiting for install {install_id} to reach Running")


def render_status(executor: TargetExecutor, install_id: int) -> dict[str, Any]:
    info = installed_info(executor, install_id)
    container_name = info.get("container")
    networks = None
    health = None
    if container_name:
        networks_raw = executor.shell(f"docker inspect {shlex.quote(container_name)} --format '{{{{json .NetworkSettings.Networks}}}}'")
        networks = json.loads(networks_raw)
        health = executor.shell(
            f"docker inspect {shlex.quote(container_name)} --format '{{{{if .State.Health}}}}{{{{.State.Health.Status}}}}{{{{else}}}}none{{{{end}}}}'"
        )
    return {"target": executor.target.name, "install": info, "networks": networks, "health": health}


def command_catalog_get(args: argparse.Namespace) -> dict[str, Any]:
    executor = TargetExecutor(get_target(args.env, args.env_file))
    meta = app_meta(executor, args.app)
    result = {"app": meta}
    if args.version:
        result["detail"] = app_detail(executor, int(meta["id"]), args.version, meta["type"])
    return result


def command_install(args: argparse.Namespace) -> dict[str, Any]:
    executor = TargetExecutor(get_target(args.env, args.env_file))
    meta = app_meta(executor, args.app)
    detail = app_detail(executor, int(meta["id"]), args.version, meta["type"])
    params = build_default_params(detail)
    params.update(parse_params(args.param))
    compose = normalize_compose_for_app(args.app, detail["dockerCompose"])
    host_mode = requires_host_network(args.app) or detail.get("hostMode", False)
    payload = {
        "appDetailId": detail["id"],
        "name": args.name or args.app,
        "params": params,
        "advanced": True,
        "cpuQuota": 0,
        "memoryLimit": 0,
        "memoryUnit": "M",
        "containerName": args.container or "",
        "allowPort": True,
        "editCompose": True,
        "dockerCompose": compose,
        "hostMode": host_mode,
        "pullImage": args.pull_image,
        "gpuConfig": False,
        "webUI": "",
        "type": meta["type"],
        "specifyIP": args.specify_ip or "",
        "restartPolicy": args.restart_policy,
    }
    install = executor.api_request("POST", "/api/v2/apps/install", payload)
    if args.wait:
        install["statusAfterWait"] = wait_for_running(executor, int(install["id"]))
    return install


def command_upgrade(args: argparse.Namespace) -> dict[str, Any]:
    executor = TargetExecutor(get_target(args.env, args.env_file))
    install_id = args.install_id or find_install_id(executor, args.app, args.name)
    info = installed_info(executor, install_id)
    meta = app_meta(executor, info["appKey"])
    detail = app_detail(executor, int(meta["id"]), args.to_version, meta["type"])
    payload = operation_payload(
        install_id,
        "upgrade",
        {
            "detailId": detail["id"],
            "pullImage": args.pull_image,
            "dockerCompose": normalize_compose_for_app(info["appKey"], detail["dockerCompose"]),
        },
    )
    executor.api_request("POST", "/api/v2/apps/installed/op", payload)
    result = {"installId": install_id, "detailId": detail["id"], "targetVersion": args.to_version}
    if args.wait:
        result["statusAfterWait"] = wait_for_running(executor, install_id)
    return result


def command_uninstall(args: argparse.Namespace) -> dict[str, Any]:
    executor = TargetExecutor(get_target(args.env, args.env_file))
    install_id = args.install_id or find_install_id(executor, args.app, args.name)
    payload = operation_payload(
        install_id,
        "delete",
        {
            "deleteBackup": args.delete_backup,
            "deleteDB": args.delete_db,
            "deleteImage": args.delete_image,
            "forceDelete": args.force_delete,
        },
    )
    executor.api_request("POST", "/api/v2/apps/installed/op", payload)
    return {"installId": install_id, "operate": "delete"}


def command_operate(args: argparse.Namespace) -> dict[str, Any]:
    executor = TargetExecutor(get_target(args.env, args.env_file))
    install_id = args.install_id or find_install_id(executor, args.app, args.name)
    executor.api_request("POST", "/api/v2/apps/installed/op", operation_payload(install_id, args.operate))
    return {"installId": install_id, "operate": args.operate}


def command_reinstall(args: argparse.Namespace) -> dict[str, Any]:
    executor = TargetExecutor(get_target(args.env, args.env_file))
    install_id = args.install_id or find_install_id(executor, args.app, args.name)
    info = installed_info(executor, install_id)
    params_data = installed_params(executor, install_id)
    meta = app_meta(executor, info["appKey"])
    detail = app_detail(executor, int(meta["id"]), info["version"], meta["type"])
    backup_path = None
    compose_path = info.get("composePath", "")
    app_dir = str(Path(compose_path).parent) if compose_path else ""
    if args.backup and app_dir:
        backup_dir = args.backup_dir or "/data/backups/manual/1panel-reinstall"
        backup_file = f"{backup_dir}/{info['appKey']}-{int(time.time())}.tgz"
        executor.shell(f"mkdir -p {shlex.quote(backup_dir)} && tar -C {shlex.quote(app_dir)} -czf {shlex.quote(backup_file)} .")
        backup_path = backup_file
    command_uninstall(
        argparse.Namespace(
            env=args.env,
            env_file=args.env_file,
            install_id=install_id,
            app=info["appKey"],
            name=info["name"],
            delete_backup=False,
            delete_db=False,
            delete_image=False,
            force_delete=False,
        )
    )
    params = build_params_from_installed(params_data)
    params.update(parse_params(args.param))
    payload = {
        "appDetailId": detail["id"],
        "name": info["name"],
        "params": params,
        "advanced": True,
        "cpuQuota": params_data.get("cpuQuota", 0),
        "memoryLimit": params_data.get("memoryLimit", 0),
        "memoryUnit": params_data.get("memoryUnit") or "M",
        "containerName": params_data.get("containerName") or info.get("container") or "",
        "allowPort": params_data.get("allowPort", True),
        "editCompose": True,
        "dockerCompose": normalize_compose_for_app(info["appKey"], params_data.get("dockerCompose") or detail["dockerCompose"]),
        "hostMode": requires_host_network(info["appKey"]) or params_data.get("hostMode", False),
        "pullImage": args.pull_image,
        "gpuConfig": params_data.get("gpuConfig", False),
        "webUI": params_data.get("webUI", ""),
        "type": meta["type"],
        "specifyIP": params_data.get("specifyIP", ""),
        "restartPolicy": params_data.get("restartPolicy", "always"),
    }
    install = executor.api_request("POST", "/api/v2/apps/install", payload)
    result = {"install": install, "backupPath": backup_path}
    if args.wait:
        result["statusAfterWait"] = wait_for_running(executor, int(install["id"]))
    return result


def command_status(args: argparse.Namespace) -> dict[str, Any]:
    executor = TargetExecutor(get_target(args.env, args.env_file))
    install_id = args.install_id or find_install_id(executor, args.app, args.name)
    return render_status(executor, install_id)


def command_audit_network(args: argparse.Namespace) -> dict[str, Any]:
    executor = TargetExecutor(get_target(args.env, args.env_file))
    rows = []
    violations = []
    for item in installed_apps(executor):
        install_id = int(item["id"])
        row = render_status(executor, install_id)
        rows.append(row)
        network_names = sorted((row.get("networks") or {}).keys())
        app_key = row["install"].get("appKey")
        if requires_host_network(app_key):
            if network_names != ["host"]:
                violations.append(
                    {
                        "installId": install_id,
                        "appKey": app_key,
                        "container": row["install"].get("container"),
                        "networks": network_names,
                        "expected": ["host"],
                    }
                )
            continue
        if "zqf_network" not in network_names:
            violations.append(
                {
                    "installId": install_id,
                    "appKey": app_key,
                    "container": row["install"].get("container"),
                    "networks": network_names,
                    "expected": ["zqf_network"],
                }
            )
    return {"target": executor.target.name, "rows": rows, "violations": violations}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage 1Panel apps with enforced zqf_network policy.")
    parser.add_argument("--env", choices=supported_targets(), required=True, help="Target environment")
    parser.add_argument("--env-file", help="Override the default 1Panel env file for the selected target")
    subparsers = parser.add_subparsers(dest="command", required=True)

    catalog = subparsers.add_parser("catalog", help="Read app catalog data")
    catalog_sub = catalog.add_subparsers(dest="catalog_command", required=True)
    catalog_get = catalog_sub.add_parser("get", help="Read app metadata and optional version detail")
    catalog_get.add_argument("--app", required=True, help="1Panel app key, for example new-api")
    catalog_get.add_argument("--version", help="Optional app version to resolve detail")
    catalog_get.set_defaults(func=command_catalog_get)

    install = subparsers.add_parser("install", help="Install a 1Panel app with normalized Compose")
    install.add_argument("--app", required=True)
    install.add_argument("--version", required=True)
    install.add_argument("--name", help="Installed app name, defaults to app key")
    install.add_argument("--container", help="Explicit container name")
    install.add_argument("--param", action="append", default=[], help="Repeatable KEY=VALUE install parameter")
    install.add_argument("--pull-image", action="store_true", help="Pull images during install")
    install.add_argument("--specify-ip", help="Optional host bind IP override")
    install.add_argument("--restart-policy", default="always", choices=("always", "unless-stopped", "no", "on-failure"))
    install.add_argument("--wait", action="store_true", help="Wait until install reaches Running")
    install.set_defaults(func=command_install)

    reinstall = subparsers.add_parser("reinstall", help="Uninstall and reinstall an existing 1Panel app")
    reinstall.add_argument("--install-id", type=int)
    reinstall.add_argument("--app", help="App key when install id is omitted")
    reinstall.add_argument("--name", help="Installed app name when install id is omitted")
    reinstall.add_argument("--param", action="append", default=[], help="Repeatable KEY=VALUE param override")
    reinstall.add_argument("--backup", action="store_true", help="Create a tar backup of the app directory before reinstall")
    reinstall.add_argument("--backup-dir", help="Target directory for reinstall backups")
    reinstall.add_argument("--pull-image", action="store_true", help="Pull images during reinstall")
    reinstall.add_argument("--wait", action="store_true", help="Wait until reinstall reaches Running")
    reinstall.set_defaults(func=command_reinstall)

    upgrade = subparsers.add_parser("upgrade", help="Upgrade an installed app with normalized Compose")
    upgrade.add_argument("--install-id", type=int)
    upgrade.add_argument("--app", help="App key when install id is omitted")
    upgrade.add_argument("--name", help="Installed app name when install id is omitted")
    upgrade.add_argument("--to-version", required=True, help="Target version")
    upgrade.add_argument("--pull-image", action="store_true", help="Pull images during upgrade")
    upgrade.add_argument("--wait", action="store_true", help="Wait until upgrade returns to Running")
    upgrade.set_defaults(func=command_upgrade)

    uninstall = subparsers.add_parser("uninstall", help="Uninstall an installed app")
    uninstall.add_argument("--install-id", type=int)
    uninstall.add_argument("--app", help="App key when install id is omitted")
    uninstall.add_argument("--name", help="Installed app name when install id is omitted")
    uninstall.add_argument("--delete-backup", action="store_true")
    uninstall.add_argument("--delete-db", action="store_true")
    uninstall.add_argument("--delete-image", action="store_true")
    uninstall.add_argument("--force-delete", action="store_true")
    uninstall.set_defaults(func=command_uninstall)

    for operate in ("start", "stop", "restart"):
        operate_parser = subparsers.add_parser(operate, help=f"{operate.title()} an installed app")
        operate_parser.add_argument("--install-id", type=int)
        operate_parser.add_argument("--app", help="App key when install id is omitted")
        operate_parser.add_argument("--name", help="Installed app name when install id is omitted")
        operate_parser.set_defaults(func=command_operate, operate=operate)

    status = subparsers.add_parser("status", help="Read installed app status and container network state")
    status.add_argument("--install-id", type=int)
    status.add_argument("--app", help="App key when install id is omitted")
    status.add_argument("--name", help="Installed app name when install id is omitted")
    status.set_defaults(func=command_status)

    audit = subparsers.add_parser("audit-network", help="Audit installed app containers for zqf_network membership")
    audit.set_defaults(func=command_audit_network)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        result = args.func(args)
    except Exception as exc:  # pragma: no cover
        print(json.dumps({"error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
