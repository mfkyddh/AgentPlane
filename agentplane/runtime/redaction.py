from __future__ import annotations

import json
from typing import Any

SENSITIVE_KEY_MARKERS = (
    "KEY",
    "PASSWORD",
    "PASSWD",
    "SECRET",
    "TOKEN",
    "DSN",
    "DATABASE_URL",
    "REDIS_URL",
    "ACCESS",
    "PRIVATE",
)


def is_sensitive_key(key: str) -> bool:
    normalized = key.upper()
    return any(marker in normalized for marker in SENSITIVE_KEY_MARKERS)


def redact_env_text(text: str) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            lines.append(line)
            continue
        key, _value = line.split("=", 1)
        if is_sensitive_key(key.strip()):
            lines.append(f"{key}=<redacted>")
        else:
            lines.append(line)
    if text.endswith("\n"):
        return "\n".join(lines) + "\n"
    return "\n".join(lines)


def _redact_value(value: Any, *, key_hint: str | None = None) -> Any:
    if key_hint and is_sensitive_key(key_hint):
        if isinstance(value, str) and "=" in value:
            return redact_env_text(value)
        if isinstance(value, (str, int, float, bool)) or value is None:
            return "<redacted>"
    if isinstance(value, dict):
        return {str(key): _redact_value(item, key_hint=str(key)) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, str):
        return redact_env_text(value)
    return value


def redact_output_text(text: str) -> str:
    if not text:
        return text
    stripped = text.lstrip()
    if stripped.startswith(("{", "[")):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return redact_env_text(text)
        redacted = _redact_value(parsed)
        if redacted == parsed:
            return text
        return json.dumps(redacted, ensure_ascii=False, indent=2)
    return redact_env_text(text)


def redact_sensitive_value(value: Any) -> Any:
    return _redact_value(value)


def redact_execution_payload(payload: dict[str, Any]) -> dict[str, Any]:
    redacted = dict(payload)
    for key in ("stdout", "stderr"):
        value = redacted.get(key)
        if isinstance(value, str):
            redacted[key] = redact_output_text(value)
    return redacted


REDACTED = "[REDACTED]"


def scrub_persisted_payload(value: Any) -> Any:
    """Recursively scrub sensitive keys from a payload dict.

    Replaces values of sensitive keys with "[REDACTED]".
    Used for persisted artifacts like ledgers and verification reports.
    """
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
