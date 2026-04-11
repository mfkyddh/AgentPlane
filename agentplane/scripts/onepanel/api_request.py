#!/usr/bin/env python3
"""Compatibility entrypoint for signed 1Panel API requests.

Prefer `python -m agentplane.cli onepanel ...` for formal control-plane flows.
This file remains for remote path compatibility and targeted recovery.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from client import load_config, send_signed_request


def main() -> int:
    parser = argparse.ArgumentParser(description="Send a signed 1Panel API request.")
    parser.add_argument("method", help="HTTP method, for example GET or POST")
    parser.add_argument("path", help="API path such as /api/v2/core/settings/interface")
    parser.add_argument("--env-file", default="secrets/services/onepanel-api.env", help="dotenv file with 1Panel settings")
    parser.add_argument("--body-json", help="JSON request body")
    parser.add_argument("--body-file", help="Path to a JSON file used as the request body")
    parser.add_argument("--query-json", help="JSON object merged into the query string")
    parser.add_argument("--status-only", action="store_true", help="Print only the HTTP status code")
    args = parser.parse_args()

    config = load_config(Path(args.env_file))

    if args.body_json and args.body_file:
        raise SystemExit("Use only one of --body-json or --body-file")

    body_bytes = None
    if args.body_json:
        body_bytes = args.body_json.encode("utf-8")
    elif args.body_file:
        body_bytes = Path(args.body_file).read_bytes()

    query = None
    if args.query_json:
        query = json.loads(args.query_json)
        if not isinstance(query, dict):
            raise SystemExit("--query-json must decode to a JSON object")

    response = send_signed_request(config, args.method, args.path, body_bytes=body_bytes, query=query)
    if args.status_only:
        print(response["status"])
    else:
        print(json.dumps(response, ensure_ascii=False, indent=2))
    return 0 if response["status"] < 400 else 1


if __name__ == "__main__":
    sys.exit(main())
