#!/usr/bin/env python3
"""Compatibility entrypoint for historical 1Panel compose project flows.

Formal AgentPlane runbooks should route through `uv run python -m agentplane.cli onepanel ...`.
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import yaml

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from compose_policy import enforce_zqf_network
from env_targets import TargetConfig, build_api_request_command, get_target, supported_targets

COMPOSE_PROJECT_DIR = "/data/1panel/docker/compose"


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


def search_compose(executor: TargetExecutor, info: str = "") -> list[dict[str, Any]]:
    data = executor.api_request("POST", "/api/v2/containers/compose/search", {"page": 1, "pageSize": 100, "info": info})
    items = data.get("items", [])
    return items if isinstance(items, list) else []


def find_compose(executor: TargetExecutor, name: str) -> dict[str, Any] | None:
    for item in search_compose(executor, name):
        if item.get("name") == name:
            return item
    return None


def create_compose(executor: TargetExecutor, *, name: str, content: str, env: str = "", force_pull: bool = False, test_only: bool = False) -> dict[str, Any]:
    payload = {
        "taskID": "",
        "name": name,
        "from": "edit",
        "file": content,
        "env": env,
        "forcePull": force_pull,
    }
    endpoint = "/api/v2/containers/compose/test" if test_only else "/api/v2/containers/compose"
    return executor.api_request("POST", endpoint, payload)


def update_compose(executor: TargetExecutor, *, name: str, detail_path: str, content: str, env: str = "", force_pull: bool = False) -> dict[str, Any]:
    project_path = f"{COMPOSE_PROJECT_DIR}/{name}/docker-compose.yml"
    payload = {
        "taskID": "",
        "name": name,
        "path": project_path,
        "detailPath": detail_path,
        "content": content,
        "env": env,
        "forcePull": force_pull,
    }
    return executor.api_request("POST", "/api/v2/containers/compose/update", payload)


def operate_compose(executor: TargetExecutor, *, name: str, operation: str, with_file: bool = False, force: bool = False) -> dict[str, Any]:
    project_path = f"{COMPOSE_PROJECT_DIR}/{name}/docker-compose.yml"
    payload = {
        "name": name,
        "path": project_path,
        "operation": operation,
        "withFile": with_file,
        "force": force,
    }
    return executor.api_request("POST", "/api/v2/containers/compose/operate", payload)


def wait_for_compose(executor: TargetExecutor, name: str, timeout_seconds: int = 120) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        item = find_compose(executor, name)
        if item and item.get("runningCount", 0) >= 1:
            return item
        time.sleep(2)
    raise TimeoutError(f"Timed out waiting for compose {name} to become running")


def load_inventory(repo_root: Path) -> dict[str, Any]:
    inventory_file = repo_root / "inventory" / "servers" / "prod0-main" / "inventory.json"
    return json.loads(inventory_file.read_text(encoding="utf-8"))


def _replace_sub2apipay_paths(compose_data: dict[str, Any], inventory: dict[str, Any]) -> dict[str, Any]:
    services = compose_data.get("services")
    if not isinstance(services, dict) or "app" not in services or not isinstance(services["app"], dict):
        raise ValueError("sub2apipay compose must contain services.app")
    app = services["app"]
    runtime = inventory["services"]["sub2apipay"]
    app["container_name"] = runtime["container_name"]
    app["env_file"] = runtime["config_files"]
    app["ports"] = [f"{runtime['host_binding']}:{runtime['container_port']}"]
    app["networks"] = ["zqf_network"]
    compose_data["services"] = services
    return compose_data


def render_sub2apipay_compose(repo_root: Path, raw_compose: str) -> str:
    inventory = load_inventory(repo_root)
    compose_data = yaml.safe_load(raw_compose)
    if not isinstance(compose_data, dict):
        raise ValueError("compose content must decode to a mapping")
    compose_data = _replace_sub2apipay_paths(compose_data, inventory)
    rendered = yaml.safe_dump(compose_data, sort_keys=False, allow_unicode=False)
    return enforce_zqf_network(rendered)


def load_sub2apipay_project_env(repo_root: Path, executor: TargetExecutor) -> str:
    inventory = load_inventory(repo_root)
    config_files = inventory["services"]["sub2apipay"]["config_files"]
    for path in config_files:
        if str(path).endswith(".env.runtime"):
            return fetch_remote_file(executor, path)
    return ""


def fetch_remote_file(executor: TargetExecutor, path: str) -> str:
    return executor.shell(f"cat {shlex.quote(path)}")


def disable_systemd_unit(executor: TargetExecutor, unit_name: str) -> dict[str, Any]:
    stdout = executor.shell(f"systemctl disable {shlex.quote(unit_name)} && systemctl is-enabled {shlex.quote(unit_name)} || true")
    return {"unit": unit_name, "result": stdout}


def command_search(args: argparse.Namespace) -> dict[str, Any]:
    executor = TargetExecutor(get_target(args.env, args.env_file))
    return {"items": search_compose(executor, args.info)}


def command_operate(args: argparse.Namespace) -> dict[str, Any]:
    executor = TargetExecutor(get_target(args.env, args.env_file))
    payload = {
        "name": args.name,
        "operation": args.operation,
        "result": operate_compose(
            executor,
            name=args.name,
            operation=args.operation,
            with_file=bool(args.with_file),
            force=bool(args.force),
        ),
    }
    if bool(args.wait_running) and args.operation in {"up", "restart"}:
        payload["statusAfterWait"] = wait_for_compose(executor, args.name)
    return payload


def command_render_sub2apipay(args: argparse.Namespace) -> dict[str, Any]:
    executor = TargetExecutor(get_target(args.env, args.env_file))
    repo_root = Path(args.repo_root).resolve()
    inventory = load_inventory(repo_root)
    raw_compose = fetch_remote_file(executor, inventory["services"]["sub2apipay"]["compose_file"])
    rendered = render_sub2apipay_compose(repo_root, raw_compose)
    return {"name": inventory["services"]["sub2apipay"]["container_name"], "content": rendered}


def command_test_sub2apipay(args: argparse.Namespace) -> dict[str, Any]:
    executor = TargetExecutor(get_target(args.env, args.env_file))
    repo_root = Path(args.repo_root).resolve()
    payload = command_render_sub2apipay(args)
    env_content = load_sub2apipay_project_env(repo_root, executor)
    result = create_compose(executor, name=payload["name"], content=payload["content"], env=env_content, test_only=True)
    return {"name": payload["name"], "ok": result, "content": payload["content"], "env": env_content}


def command_sync_sub2apipay(args: argparse.Namespace) -> dict[str, Any]:
    executor = TargetExecutor(get_target(args.env, args.env_file))
    repo_root = Path(args.repo_root).resolve()
    inventory = load_inventory(repo_root)
    runtime = inventory["services"]["sub2apipay"]
    name = runtime["container_name"]
    raw_compose = fetch_remote_file(executor, runtime["compose_file"])
    rendered = render_sub2apipay_compose(repo_root, raw_compose)
    env_content = load_sub2apipay_project_env(repo_root, executor)
    current = find_compose(executor, name)
    if current and current.get("createdBy") == "1Panel":
        detail_path = current.get("configFile") or f"{COMPOSE_PROJECT_DIR}/{name}/docker-compose.yml"
        result = update_compose(executor, name=name, detail_path=detail_path, content=rendered, env=env_content)
        action = "update"
    else:
        result = create_compose(executor, name=name, content=rendered, env=env_content)
        action = "create"
    operate_compose(executor, name=name, operation="up")
    status_after_wait = wait_for_compose(executor, name)
    disable_result = None
    if args.disable_systemd:
        disable_result = disable_systemd_unit(executor, runtime["service_name"])
    return {
        "action": action,
        "result": result,
        "statusAfterWait": status_after_wait,
        "disabledSystemd": disable_result,
        "projectPath": f"{COMPOSE_PROJECT_DIR}/{name}/docker-compose.yml",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage 1Panel compose projects from the repository.")
    parser.add_argument("--env", choices=supported_targets(), required=True, help="Target environment")
    parser.add_argument("--env-file", help="Override the default 1Panel env file for the selected target")
    subparsers = parser.add_subparsers(dest="command", required=True)

    search = subparsers.add_parser("search", help="Search compose projects visible to 1Panel")
    search.add_argument("--info", default="", help="Search keyword")
    search.set_defaults(func=command_search)

    operate = subparsers.add_parser("operate", help="Operate a visible 1Panel compose project")
    operate.add_argument("--name", required=True, help="Project name")
    operate.add_argument("--operation", required=True, choices=("up", "down", "restart", "stop"), help="Project operation")
    operate.add_argument("--with-file", action="store_true", help="Delete compose file together when supported")
    operate.add_argument("--force", action="store_true", help="Force execution when supported")
    operate.add_argument("--wait-running", action="store_true", help="Wait for running status after up/restart")
    operate.set_defaults(func=command_operate)

    render = subparsers.add_parser("render-sub2apipay", help="Render normalized sub2apipay compose content")
    render.add_argument("--repo-root", default=".", help="Repository root")
    render.set_defaults(func=command_render_sub2apipay)

    test = subparsers.add_parser("test-sub2apipay", help="Test normalized sub2apipay compose through 1Panel")
    test.add_argument("--repo-root", default=".", help="Repository root")
    test.set_defaults(func=command_test_sub2apipay)

    sync = subparsers.add_parser("sync-sub2apipay", help="Create or update a 1Panel compose project for sub2apipay")
    sync.add_argument("--repo-root", default=".", help="Repository root")
    sync.add_argument("--disable-systemd", action="store_true", help="Disable the legacy systemd unit after successful sync")
    sync.set_defaults(func=command_sync_sub2apipay)
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
