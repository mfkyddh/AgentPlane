from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from agentplane.scripts.onepanel.env_targets import get_target
from agentplane.scripts.onepanel.executor import TargetExecutor
from agentplane.scripts.onepanel.object_api import (
    plan_compose_project_operation,
    plan_installed_app_operation,
    search_installed_apps,
)


def _find_installed_app_id(executor: TargetExecutor, *, install_id: int | None, name: str) -> int:
    if install_id is not None:
        return install_id
    if not name:
        raise ValueError("app transition requires --install-id or --name")
    payload = search_installed_apps(executor, name=name)
    items = payload.get("items", []) if isinstance(payload, dict) else []
    for item in items:
        if isinstance(item, dict) and item.get("name") == name and item.get("id") is not None:
            return int(item["id"])
    raise ValueError(f"installed app not found: {name}")


def _handle_app(args: argparse.Namespace) -> dict[str, Any]:
    executor = TargetExecutor(get_target(args.target))
    install_id = _find_installed_app_id(executor, install_id=args.install_id, name=args.name)
    plan = plan_installed_app_operation(install_id=install_id, operate=args.operate)
    result = executor.api_request("POST", plan.path, plan.body)
    return {"scope": "app", "action": args.operate, "install_id": install_id, "result": result}


def _handle_project(args: argparse.Namespace) -> dict[str, Any]:
    executor = TargetExecutor(get_target(args.target))
    plan = plan_compose_project_operation(name=args.name, operation=args.operate)
    result = executor.api_request("POST", plan.path, plan.body)
    return {"scope": "project", "action": args.operate, "name": args.name, "result": result}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agentplane.providers.onepanel_transition")
    parser.add_argument("--target", required=True, help="AgentPlane target")
    subparsers = parser.add_subparsers(dest="scope", required=True)

    app = subparsers.add_parser("app", help="internal installed app transition")
    app.add_argument("--operate", required=True, choices=("start", "stop", "restart"))
    app.add_argument("--install-id", type=int)
    app.add_argument("--name", default="")
    app.set_defaults(handler=_handle_app)

    project = subparsers.add_parser("project", help="internal compose project transition")
    project.add_argument("--operate", required=True, choices=("up", "down", "restart", "stop"))
    project.add_argument("--name", required=True)
    project.set_defaults(handler=_handle_project)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = args.handler(args)
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
