#!/usr/bin/env python3
"""Shared helpers for signed 1Panel API requests."""

from __future__ import annotations

import hashlib
import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class OnePanelConfig:
    base_url: str
    connect_base_url: str
    api_key: str
    security_entrance: str | None
    timeout_seconds: float
    skip_tls_verify: bool


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def normalize_entrance(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip().strip("/")
    return stripped or None


def load_config(env_file: Path) -> OnePanelConfig:
    env = load_env_file(env_file)
    base_url = env["ONEPANEL_BASE_URL"].rstrip("/")
    connect_base_url = env.get("ONEPANEL_CONNECT_BASE_URL", base_url).rstrip("/")
    timeout_seconds = int(env.get("ONEPANEL_TIMEOUT_MS", "30000")) / 1000.0
    skip_tls_verify = env.get("ONEPANEL_SKIP_TLS_VERIFY", "").lower() in {"1", "true", "yes"}
    return OnePanelConfig(
        base_url=base_url,
        connect_base_url=connect_base_url,
        api_key=env["ONEPANEL_API_KEY"],
        security_entrance=normalize_entrance(env.get("ONEPANEL_SECURITY_ENTRANCE")),
        timeout_seconds=timeout_seconds,
        skip_tls_verify=skip_tls_verify,
    )


def build_headers(
    base_url: str,
    api_key: str,
    security_entrance: str | None,
    body: bytes | None,
) -> dict[str, str]:
    timestamp = str(int(time.time()))
    token = hashlib.md5(f"1panel{api_key}{timestamp}".encode("utf-8")).hexdigest()
    base_uri = urllib.parse.urlparse(base_url)
    origin = f"{base_uri.scheme}://{base_uri.netloc}"
    headers = {
        "Accept": "application/json, text/plain, text/event-stream",
        "Content-Type": "application/json",
        "1Panel-Token": token,
        "1Panel-Timestamp": timestamp,
        "Content-Length": str(len(body or b"")),
        "Host": base_uri.netloc,
    }
    if security_entrance:
        headers["Origin"] = origin
        headers["Referer"] = f"{origin}/{security_entrance}/"
    return headers


def try_parse_json(body: str) -> Any:
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return body


def send_signed_request(
    config: OnePanelConfig,
    method: str,
    path: str,
    body_bytes: bytes | None = None,
    query: dict[str, Any] | None = None,
) -> dict[str, Any]:
    request_url = urllib.parse.urljoin(f"{config.connect_base_url}/", path.lstrip("/"))
    if query:
        encoded_query = urllib.parse.urlencode(
            {key: str(value) for key, value in query.items() if value is not None and value != ""}
        )
        separator = "&" if urllib.parse.urlparse(request_url).query else "?"
        request_url = f"{request_url}{separator}{encoded_query}"

    request = urllib.request.Request(
        request_url,
        data=body_bytes,
        method=method.upper(),
        headers=build_headers(config.base_url, config.api_key, config.security_entrance, body_bytes),
    )
    context = None
    if request_url.startswith("https://") and config.skip_tls_verify:
        context = ssl._create_unverified_context()
    try:
        with urllib.request.urlopen(request, timeout=config.timeout_seconds, context=context) as response:
            body = response.read().decode("utf-8")
            return {"status": response.status, "body": try_parse_json(body)}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return {"status": exc.code, "body": try_parse_json(body)}
