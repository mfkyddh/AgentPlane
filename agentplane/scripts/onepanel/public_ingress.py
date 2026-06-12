#!/usr/bin/env python3
"""Automate Cloudflare DNS + 1Panel website/certificate public ingress setup."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from agentplane.adapters.cloudflare import CloudflareClient, load_shell_env_file
from agentplane.scripts.onepanel.env_targets import get_target
from agentplane.scripts.onepanel.public_ingress_config import OnePanelExecutor, PublicIngressConfig
from agentplane.scripts.onepanel.public_ingress_manager import PublicIngressManager


def _build_manager(
    env: str, config_file: Path, cloudflare_env_file: Path, *, env_file: str | None = None
) -> tuple[PublicIngressConfig, dict[str, str], CloudflareClient, PublicIngressManager]:
    ingress_config = PublicIngressConfig.from_env_file(config_file)
    cloudflare_env = load_shell_env_file(cloudflare_env_file)
    panel = OnePanelExecutor(get_target(env, env_file), env_file_override=env_file)
    cloudflare = CloudflareClient(cloudflare_env["CLOUDFLARE_API_TOKEN"])
    manager = PublicIngressManager(panel=panel, cloudflare=cloudflare, config=ingress_config)
    return ingress_config, cloudflare_env, cloudflare, manager


def plan_public_ingress(
    env: str, config_file: Path, cloudflare_env_file: Path, *, env_file: str | None = None
) -> dict[str, Any]:
    ingress_config, cloudflare_env, _cloudflare, _manager = _build_manager(
        env,
        config_file,
        cloudflare_env_file,
        env_file=env_file,
    )
    return {
        "ok": True,
        "env": env,
        "domain": ingress_config.domain,
        "zone": ingress_config.zone_name,
        "website_alias": ingress_config.website_alias,
        "config_file": str(config_file.resolve()),
        "cloudflare_env_file": str(cloudflare_env_file.resolve()),
        "cloudflare_account_id": cloudflare_env.get("CLOUDFLARE_ACCOUNT_ID", ""),
        "execute_required": True,
        "steps": [
            {
                "kind": "cloudflare_dns",
                "action": "ensure",
                "record_name": ingress_config.domain,
                "record_type": ingress_config.record_type,
                "record_content": ingress_config.record_content,
                "proxied": ingress_config.record_proxied,
            },
            {
                "kind": "onepanel_acme",
                "action": "ensure",
                "email": ingress_config.acme_email,
                "type": ingress_config.acme_type,
            },
            {
                "kind": "onepanel_dns_account",
                "action": "ensure",
                "name": ingress_config.dns_account_name,
                "type": ingress_config.dns_account_provider,
            },
            {"kind": "onepanel_ssl", "action": "ensure", "primary_domain": ingress_config.cert_primary_domain},
            {
                "kind": "onepanel_website",
                "action": "ensure",
                "alias": ingress_config.website_alias,
                "proxy": ingress_config.website_proxy,
            },
            {"kind": "onepanel_https", "action": "ensure", "https_ports": ingress_config.https_ports},
        ],
    }


def verify_public_ingress(
    env: str, config_file: Path, cloudflare_env_file: Path, *, env_file: str | None = None
) -> dict[str, Any]:
    ingress_config, cloudflare_env, cloudflare, manager = _build_manager(
        env,
        config_file,
        cloudflare_env_file,
        env_file=env_file,
    )
    cloudflare.verify_account_token(cloudflare_env["CLOUDFLARE_ACCOUNT_ID"])
    payload = manager.verify()
    return {
        "command": "onepanel public-ingress verify",
        "env": env,
        "domain": ingress_config.domain,
        "zone": ingress_config.zone_name,
        "payload": payload,
    }


def ensure_public_ingress(
    env: str, config_file: Path, cloudflare_env_file: Path, *, env_file: str | None = None
) -> dict[str, Any]:
    ingress_config, cloudflare_env, cloudflare, manager = _build_manager(
        env,
        config_file,
        cloudflare_env_file,
        env_file=env_file,
    )
    cloudflare.verify_account_token(cloudflare_env["CLOUDFLARE_ACCOUNT_ID"])
    payload = manager.ensure()
    return {
        "command": "onepanel public-ingress ensure",
        "env": env,
        "domain": ingress_config.domain,
        "zone": ingress_config.zone_name,
        "payload": payload,
    }


def command_ensure_public_ingress(args: argparse.Namespace) -> dict[str, Any]:
    return ensure_public_ingress(
        args.env,
        Path(args.config_file),
        Path(args.cloudflare_env_file),
        env_file=args.env_file,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ensure public ingress through Cloudflare and 1Panel.")
    parser.add_argument("--env", required=True, help="1Panel target environment")
    parser.add_argument("--env-file", help="Override 1Panel API env file")
    parser.add_argument("--config-file", required=True, help="Public ingress env-style config file")
    parser.add_argument("--cloudflare-env-file", required=True, help="Shell env file with Cloudflare token")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    result = command_ensure_public_ingress(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
