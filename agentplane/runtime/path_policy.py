from __future__ import annotations

import re

HOST_PATH_PREFIXES = (
    "D:/",
    "C:/",
    "/root/",
    "/mnt/",
    r"\\wsl.localhost\\",
    r"\\wsl$\\",
)
_CANONICAL_SEGMENT = r"[a-z0-9][a-z0-9_-]*"
_CANONICAL_REF_PATTERN = re.compile(rf"^{_CANONICAL_SEGMENT}(?:/{_CANONICAL_SEGMENT})+$")


def normalize_path_value(value: str) -> str:
    return value.replace("\\", "/").strip()


def is_host_specific_path(value: str) -> bool:
    normalized = normalize_path_value(value)
    if normalized.startswith(("D:/", "C:/", "/root/", "/mnt/")):
        return True
    lowered = value.replace("/", "\\").lower()
    return lowered.startswith("\\\\wsl.localhost\\") or lowered.startswith("\\\\wsl$\\")


def is_canonical_ref(value: str) -> bool:
    if not isinstance(value, str):
        return False
    candidate = value.strip()
    if not candidate or is_host_specific_path(candidate):
        return False
    if candidate.startswith("/") or candidate.startswith("\\") or ".." in candidate.split("/"):
        return False
    return bool(_CANONICAL_REF_PATTERN.fullmatch(candidate))


def assert_canonical_ref(value: str) -> str:
    candidate = value.strip()
    if not is_canonical_ref(candidate):
        raise ValueError(f"host-specific path is not allowed in canonical truth: {value}")
    return candidate
