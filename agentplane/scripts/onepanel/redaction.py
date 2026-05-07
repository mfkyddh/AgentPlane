#!/usr/bin/env python3
"""Redaction helpers for persisted onepanel artifacts.

Core logic is in agentplane.runtime.redaction.
This module re-exports from there and adds onepanel-specific key detection.
"""

from __future__ import annotations

from typing import Any

from agentplane.runtime.redaction import REDACTED, scrub_persisted_payload

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
    """Stricter key detection for 1Panel API payloads.

    Uses exact match + suffix match instead of substring match.
    """
    normalized = _normalize_key(key)
    if not normalized:
        return False
    if normalized in _SENSITIVE_KEYS:
        return True
    if normalized.endswith(_SENSITIVE_SUFFIXES):
        return True
    return normalized.endswith("secret") and not normalized.endswith("secretfile")


__all__ = ["REDACTED", "is_sensitive_key", "scrub_persisted_payload"]
