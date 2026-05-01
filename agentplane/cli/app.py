from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from agentplane.cli.apps import add_app_parser, handle_app_command
from agentplane.cli.bootstrap import add_bootstrap_parser, handle_bootstrap_command
from agentplane.cli.infra import add_infra_parser, handle_infra_command
from agentplane.cli.infra_onepanel import (
    add_onepanel_parser,
    handle_onepanel_command,
    onepanel_error_payload,
    render_onepanel_text,
)
from agentplane.cli.ingress import add_ingress_parser, handle_ingress_command
from agentplane.cli.projection import add_projection_parser, handle_projection_command
from agentplane.cli.repository import add_repository_parser, handle_repository_command
from agentplane.cli.service import add_service_parser, handle_service_command
from agentplane.cli.test_runner import add_test_parser, handle_test_command


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=True, indent=2))


def _split_remote_bash_remainder(argv: list[str]) -> tuple[list[str], list[str]]:
    if argv[:3] != ["infra", "remote", "bash"]:
        return argv, []
    prefix = 3
    if "--" not in argv:
        return argv, []
    separator = argv.index("--")
    if separator < prefix:
        return argv, []
    return argv[:separator], argv[separator + 1 :]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentplane.cli",
        description="Agent-first control plane CLI for AgentPlane",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_bootstrap_parser(subparsers)
    add_infra_parser(subparsers)
    add_service_parser(subparsers)
    add_ingress_parser(subparsers)
    add_app_parser(subparsers)
    add_projection_parser(subparsers)
    add_repository_parser(subparsers)
    add_onepanel_parser(subparsers)
    add_test_parser(subparsers)

    return parser


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(argv) if argv is not None else sys.argv[1:]
    parse_argv, remote_remainder = _split_remote_bash_remainder(raw_argv)
    parser = build_parser()
    args = parser.parse_args(parse_argv)
    if (
        remote_remainder
        and args.command == "infra"
        and getattr(args, "infra_action", None) == "remote"
        and getattr(args, "infra_remote_action", None) == "bash"
    ):
        args.remote_args = [*getattr(args, "remote_args", []), *remote_remainder]

    if args.command == "onepanel":
        try:
            payload = handle_onepanel_command(args)
            if getattr(args, "json", False):
                _emit(payload)
            else:
                print(render_onepanel_text(payload), end="")
            if payload.get("payload", {}).get("ok") is False:
                return 1
            return 0
        except (RuntimeError, ValueError, json.JSONDecodeError) as exc:
            payload = onepanel_error_payload(args, exc)
            if getattr(args, "json", False):
                _emit(payload)
            else:
                print(render_onepanel_text(payload), end="")
            return 1

    if args.command == "test":
        return handle_test_command(args)

    if args.command == "infra":
        try:
            payload = handle_infra_command(args)
            _emit(payload)
            if payload.get("action") == "remote.bash":
                return 0 if payload.get("payload", {}).get("ok", True) else 1
            if payload.get("action") == "network.ensure":
                return 0 if payload.get("payload", {}).get("ok", True) else 1
            if payload.get("action") == "live-gate.run":
                return 0 if payload.get("payload", {}).get("ok", True) else 1
            if payload.get("action") in {"automation.verify", "automation.apply"}:
                return 0 if payload.get("payload", {}).get("ok", True) else 1
            return 0
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1

    if args.command == "bootstrap":
        try:
            payload = handle_bootstrap_command(args)
            _emit(payload)
            return 0 if payload.get("payload", {}).get("ok", True) else 1
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1

    if args.command == "service":
        try:
            payload = handle_service_command(args)
            _emit(payload)
            if args.service_action == "verify":
                return 0 if payload.get("payload", {}).get("ok", True) else 1
            if args.service_action == "apply":
                return 0 if payload.get("payload", {}).get("ok", True) else 1
            if args.service_action == "public-endpoint" and getattr(args, "service_public_endpoint_action", None) in {
                "verify",
                "apply",
            }:
                return 0 if payload.get("payload", {}).get("ok", True) else 1
            return 0
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1

    if args.command == "ingress":
        try:
            payload = handle_ingress_command(args)
            _emit(payload)
            if args.ingress_action == "verify":
                return 0 if payload.get("payload", {}).get("ok", True) else 1
            if args.ingress_action == "apply":
                return 0 if payload.get("payload", {}).get("ok", True) else 1
            if args.ingress_action == "publish" and getattr(args, "ingress_publish_action", None) in {
                "apply",
                "verify",
            }:
                return 0 if payload.get("payload", {}).get("ok", True) else 1
            return 0
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1

    if args.command == "app":
        try:
            payload = handle_app_command(args)
            _emit(payload)
            return 0 if payload.get("payload", {}).get("ok", True) else 1
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1

    if args.command == "projection":
        try:
            payload = handle_projection_command(args)
            _emit(payload)
            return 0 if payload.get("ok", True) else 1
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1

    if args.command == "repo":
        try:
            payload = handle_repository_command(args)
            _emit(payload)
            return 0 if payload.get("ok", True) else 1
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1

    parser.error("Unsupported command")
    return 2


if __name__ == "__main__":
    sys.exit(main())
