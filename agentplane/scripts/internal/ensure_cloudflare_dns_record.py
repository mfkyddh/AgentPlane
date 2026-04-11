#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from agentplane.adapters.cloudflare import CloudflareClient, load_shell_env_file, parse_bool


def ensure_cloudflare_dns_record(
    *,
    cloudflare_env_file: Path,
    zone_name: str,
    record_name: str,
    record_type: str,
    record_content: str,
    proxied: bool,
) -> dict[str, Any]:
    env = load_shell_env_file(cloudflare_env_file)
    client = CloudflareClient(env["CLOUDFLARE_API_TOKEN"])
    result = client.ensure_dns_record(
        zone_name=zone_name,
        record_name=record_name,
        record_type=record_type,
        content=record_content,
        proxied=proxied,
    )
    return {
        "ok": True,
        "zone_name": zone_name,
        "record_name": record_name,
        "record_type": record_type,
        "record_content": record_content,
        "proxied": proxied,
        "action": result["action"],
        "changed": result["changed"],
        "record": result["record"],
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ensure Cloudflare DNS record.")
    parser.add_argument("--cloudflare-env-file", required=True, help="Shell env file with CLOUDFLARE_API_TOKEN")
    parser.add_argument("--zone-name", required=True, help="Cloudflare zone name")
    parser.add_argument("--record-name", required=True, help="DNS record name")
    parser.add_argument("--record-type", default="A", help="DNS record type")
    parser.add_argument("--record-content", required=True, help="DNS record content")
    parser.add_argument("--proxied", default="false", help="Whether DNS record is proxied (true/false)")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    payload = ensure_cloudflare_dns_record(
        cloudflare_env_file=Path(args.cloudflare_env_file),
        zone_name=args.zone_name,
        record_name=args.record_name,
        record_type=args.record_type,
        record_content=args.record_content,
        proxied=parse_bool(args.proxied, default=False),
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
