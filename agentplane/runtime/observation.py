from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

OBSERVATION_ONLY_KEYS = frozenset(
    {
        "resolved_path",
        "contract_file",
        "path",
        "verification_fields",
        "observation",
        "observed_at",
    }
)


def _copy_mapping(value: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(value) if value is not None else {}


def observation_timestamp() -> str:
    return datetime.now(UTC).isoformat()


def tracked_ledger_fields(value: Mapping[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in dict(value).items() if key not in OBSERVATION_ONLY_KEYS}


def extract_ledger_fields(payload: Mapping[str, Any]) -> dict[str, Any]:
    nested = payload.get("ledger_fields")
    if isinstance(nested, Mapping):
        return tracked_ledger_fields(nested)
    return tracked_ledger_fields(payload)


@dataclass(frozen=True)
class ObservationRecord:
    canonical_ref: str
    evidence: Mapping[str, Any]
    resolved_path: str | None = None
    observed_at: str | None = None

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "canonical_ref": self.canonical_ref,
            "observed_at": self.observed_at or observation_timestamp(),
            "evidence": dict(self.evidence),
        }
        if self.resolved_path is not None:
            payload["resolved_path"] = self.resolved_path
        return payload


def build_verification_payload(
    *,
    canonical_ref: str,
    ledger_fields: Mapping[str, Any],
    verification_fields: Mapping[str, Any] | None = None,
    resolved_path: str | None = None,
    evidence: Mapping[str, Any] | None = None,
    checks: Mapping[str, Any] | None = None,
    failures: list[str] | tuple[str, ...] | None = None,
    ok: bool | None = None,
) -> dict[str, Any]:
    ledger_payload = tracked_ledger_fields(ledger_fields)
    ledger_payload["canonical_ref"] = canonical_ref

    verification_payload = _copy_mapping(verification_fields)
    if resolved_path is not None:
        verification_payload.setdefault("resolved_path", resolved_path)

    observation_evidence = _copy_mapping(evidence) or dict(verification_payload)
    observation = ObservationRecord(
        canonical_ref=canonical_ref,
        evidence=observation_evidence,
        resolved_path=resolved_path or verification_payload.get("resolved_path"),
    ).to_payload()

    payload: dict[str, Any] = {
        "canonical_ref": canonical_ref,
        "ledger_fields": ledger_payload,
        "verification_fields": verification_payload,
        "observation": observation,
    }
    if checks is not None:
        payload["checks"] = dict(checks)
    if failures is not None:
        payload["failures"] = list(failures)
    payload["ok"] = bool(ok) if ok is not None else not bool(payload.get("failures"))
    return payload
