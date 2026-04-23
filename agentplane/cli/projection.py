from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from agentplane.domain.app.projection.runtime_env import (
    SUPPORTED_RUNTIME_ENV_TARGETS,
    apply_runtime_env_projection,
    plan_runtime_env_projection,
    verify_runtime_env_projection,
)
from agentplane.providers.onepanel_fixtures import (
    apply_fixture,
    cleanup_fixture,
    plan_fixture,
    resolve_fixture_spec,
    run_onepanel_verification_suite,
)
from agentplane.providers.onepanel_ledgers import refresh_onepanel_ledgers
from agentplane.providers.onepanel_objects import onepanel_target_executor, supported_onepanel_targets
from agentplane.runtime.redaction import redact_sensitive_value
from agentplane.runtime.wsl_bridge import normalize_repo_root_for_current_host

FORMAL_PROJECTION_SURFACES = ("runtime-env", "verification", "fixture", "ledger")
FORMAL_RUNTIME_ENV_ACTIONS = ("plan", "apply", "verify")
FORMAL_VERIFICATION_ACTIONS = ("run",)
FORMAL_FIXTURE_ACTIONS = ("plan", "apply", "cleanup")
FORMAL_LEDGER_ACTIONS = ("refresh",)
PROJECTION_SURFACE_CONTRACTS = {
    "runtime-env": "projection",
    "verification": "observation",
    "fixture": "projection",
    "ledger": "projection",
}


def add_projection_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    projection_parser = subparsers.add_parser("projection", help="正式派生任务入口")
    projection_subparsers = projection_parser.add_subparsers(dest="projection_surface", required=True)

    runtime_env = projection_subparsers.add_parser("runtime-env", help="Runtime env projection tasks")
    runtime_env_subparsers = runtime_env.add_subparsers(dest="projection_action", required=True)

    for action in ("plan", "apply", "verify"):
        parser = runtime_env_subparsers.add_parser(action, help=f"{action} runtime env projection")
        parser.add_argument("--target", required=True, choices=SUPPORTED_RUNTIME_ENV_TARGETS, help="Target environment")
        parser.add_argument("--app", required=True, help="Application id")
        parser.add_argument("--repo-root", default=".", help="Repository root")
        parser.add_argument("--reveal-secrets", action="store_true", help="Include unredacted env content in output")

    verification = projection_subparsers.add_parser("verification", help="Verification observation surface")
    verification_subparsers = verification.add_subparsers(dest="projection_verification_action", required=True)
    run = verification_subparsers.add_parser("run", help="Run verification suite")
    run.add_argument("--target", required=True, choices=supported_onepanel_targets(), help="Target environment")
    run.add_argument("--profile", required=True, choices=("wsl-fixture", "prod2-readonly", "prod0-readonly"), help="Verification profile")
    run.add_argument("--repo-root", default=".", help="Repository root")
    run.add_argument("--write-report", action="store_true", help="Write verification report")
    run.add_argument("--website-alias", default="", help="Website alias selector")
    run.add_argument("--container-name", default="", help="Container selector")
    run.add_argument("--project-name", default="", help="Compose project selector")
    run.add_argument("--cronjob-id", type=int, default=None, help="Cronjob id selector")
    run.add_argument("--cronjob-name", default="", help="Cronjob name selector")
    run.add_argument("--app-name", default="", help="Installed app selector")
    run.add_argument("--firewall-tab", default="port", choices=("port", "address", "forward"), help="Firewall tab selector")

    fixture = projection_subparsers.add_parser("fixture", help="Fixture task surface")
    fixture_subparsers = fixture.add_subparsers(dest="projection_fixture_action", required=True)
    for action in ("plan", "apply", "cleanup"):
        parser = fixture_subparsers.add_parser(action, help=f"{action} fixture profile")
        parser.add_argument("--target", required=True, choices=supported_onepanel_targets(), help="Target environment")
        parser.add_argument("--profile", required=True, choices=("wsl-fixture",), help="Fixture profile")
        parser.add_argument("--repo-root", default=".", help="Repository root")
        parser.add_argument("--website-alias", default="", help="Website alias override")
        parser.add_argument("--container-name", default="", help="Container name override")
        parser.add_argument("--project-name", default="", help="Compose project override")
        parser.add_argument("--cronjob-name", default="", help="Cronjob name override")
        parser.add_argument("--firewall-tab", default="", help="Firewall tab override")
        if action in {"apply", "cleanup"}:
            parser.add_argument("--execute", action="store_true", help="Execute write operation")

    ledger = projection_subparsers.add_parser("ledger", help="Projection-only ledger task surface")
    ledger_subparsers = ledger.add_subparsers(dest="projection_ledger_action", required=True)
    refresh = ledger_subparsers.add_parser("refresh", help="Refresh tracked ledgers")
    refresh.add_argument("--target", required=True, choices=supported_onepanel_targets(), help="Target environment")
    refresh.add_argument("--repo-root", default=".", help="Repository root")
    refresh.add_argument("--write", action="store_true", help="Write tracked artifacts")


def _wrap(surface: str, action: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "command": "projection",
        "surface_contract": PROJECTION_SURFACE_CONTRACTS[surface],
        "action": action,
        **payload,
    }


def _normalize_repo_root(path: Path | str) -> Path:
    return normalize_repo_root_for_current_host(path)


def _executor_for_target(target: str) -> object:
    return onepanel_target_executor(target)


def _require_formal_surface(surface: str) -> None:
    if surface not in FORMAL_PROJECTION_SURFACES:
        raise ValueError(f"Unsupported projection surface: {surface}")


def _require_formal_action(surface: str, action: str, allowed: tuple[str, ...]) -> None:
    if action not in allowed:
        raise ValueError(f"Unsupported projection action: {surface}.{action}")


def handle_projection_command(args: argparse.Namespace) -> dict[str, Any]:
    _require_formal_surface(args.projection_surface)
    repo_root = _normalize_repo_root(args.repo_root)
    if args.projection_surface == "runtime-env" and args.projection_action == "plan":
        _require_formal_action(args.projection_surface, args.projection_action, FORMAL_RUNTIME_ENV_ACTIONS)
        return _wrap(
            "runtime-env",
            "runtime-env.plan",
            plan_runtime_env_projection(repo_root, args.target, args.app, reveal_secrets=args.reveal_secrets),
        )
    if args.projection_surface == "runtime-env" and args.projection_action == "apply":
        _require_formal_action(args.projection_surface, args.projection_action, FORMAL_RUNTIME_ENV_ACTIONS)
        return _wrap(
            "runtime-env",
            "runtime-env.apply",
            apply_runtime_env_projection(repo_root, args.target, args.app, reveal_secrets=args.reveal_secrets),
        )
    if args.projection_surface == "runtime-env" and args.projection_action == "verify":
        _require_formal_action(args.projection_surface, args.projection_action, FORMAL_RUNTIME_ENV_ACTIONS)
        return _wrap(
            "runtime-env",
            "runtime-env.verify",
            verify_runtime_env_projection(repo_root, args.target, args.app, reveal_secrets=args.reveal_secrets),
        )
    if args.projection_surface == "verification" and args.projection_verification_action == "run":
        _require_formal_action(
            args.projection_surface,
            args.projection_verification_action,
            FORMAL_VERIFICATION_ACTIONS,
        )
        payload = run_onepanel_verification_suite(
            _executor_for_target(args.target),
            profile=args.profile,
            env=args.target,
            repo_root=repo_root,
            write_report=bool(args.write_report),
            website_alias=args.website_alias,
            container_name=args.container_name,
            project_name=args.project_name,
            cronjob_id=args.cronjob_id,
            cronjob_name=args.cronjob_name,
            app_name=args.app_name,
            firewall_tab=args.firewall_tab,
        )
        return _wrap(
            "verification",
            "verification.run",
            redact_sensitive_value(payload),
        )
    if args.projection_surface == "fixture":
        _require_formal_action(args.projection_surface, args.projection_fixture_action, FORMAL_FIXTURE_ACTIONS)
        if args.projection_fixture_action in {"apply", "cleanup"} and not bool(args.execute):
            raise ValueError(f"projection fixture {args.projection_fixture_action} requires --execute")
        spec = resolve_fixture_spec(
            args.profile,
            env=args.target,
            website_alias=args.website_alias,
            container_name=args.container_name,
            project_name=args.project_name,
            cronjob_name=args.cronjob_name,
            firewall_tab=args.firewall_tab,
        )
        executor = _executor_for_target(args.target)
        if args.projection_fixture_action == "plan":
            payload = plan_fixture(executor, spec)
        elif args.projection_fixture_action == "apply":
            payload = apply_fixture(executor, spec, execute=True)
        else:
            payload = cleanup_fixture(executor, spec, execute=True)
        return _wrap("fixture", f"fixture.{args.projection_fixture_action}", payload)
    if args.projection_surface == "ledger" and args.projection_ledger_action == "refresh":
        _require_formal_action(args.projection_surface, args.projection_ledger_action, FORMAL_LEDGER_ACTIONS)
        return _wrap("ledger", "ledger.refresh", refresh_onepanel_ledgers(repo_root, args.target, write=bool(args.write)))
    action = (
        getattr(args, "projection_action", None)
        or getattr(args, "projection_verification_action", None)
        or getattr(args, "projection_fixture_action", None)
        or getattr(args, "projection_ledger_action", None)
        or "unknown"
    )
    raise ValueError(f"Unsupported projection action: {args.projection_surface}.{action}")
