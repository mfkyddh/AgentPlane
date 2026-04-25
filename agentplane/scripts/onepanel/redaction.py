#!/usr/bin/env python3
"""Redaction helpers for persisted onepanel artifacts."""

from __future__ import annotations

from typing import Any

REDACTED = "[REDACTED]"
_SENSITIVE_KEYS = {
    "apikey",
    "authorization",
    "clientsecret",
    "mfasecret",
    "passkey",
    "password",
    "passwd",
    "privatekey",
    "proxypasswd",
    "proxypasswdkeep",
    "refreshtoken",
    "secret",
    "secretkey",
    "token",
}
_SENSITIVE_SUFFIXES = (
    "apikey",
    "token",
    "password",
    "passwd",
    "privatekey",
    "secretkey",
)


def _normalize_key(key: Any) -> str:
    return "".join(ch for ch in str(key).lower() if ch.isalnum())


def is_sensitive_key(key: Any) -> bool:
    normalized = _normalize_key(key)
    if not normalized:
        return False
    if normalized in _SENSITIVE_KEYS:
        return True
    if normalized.endswith(_SENSITIVE_SUFFIXES):
        return True
    return normalized.endswith("secret") and not normalized.endswith("secretfile")


def scrub_persisted_payload(value: Any) -> Any:
    if isinstance(value, dict):
        scrubbed: dict[str, Any] = {}
        for key, item in value.items():
            if is_sensitive_key(key):
                scrubbed[key] = REDACTED
            else:
                scrubbed[key] = scrub_persisted_payload(item)
        return scrubbed
    if isinstance(value, list):
        return [scrub_persisted_payload(item) for item in value]
    return value
