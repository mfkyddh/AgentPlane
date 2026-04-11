from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class WebsiteDefinition:
    alias: str
    primary_domain: str
    public_url: str
    proxy: str
    status: str = ""
    config_file: str = ""
    ssl_id: int | None = None
    certificate_mode: str = ""
    control_plane: str = "onepanel"


@dataclass(frozen=True)
class WebsiteFollowThrough:
    owner_surface: str
    source_surface: str
    verification_profile: str
    verification_command: str
    ledger_refresh_command: str
    notes: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "owner_surface": self.owner_surface,
            "source_surface": self.source_surface,
            "verification_profile": self.verification_profile,
            "commands": {
                "verification": self.verification_command,
                "ledger_refresh": self.ledger_refresh_command,
            },
            "notes": list(self.notes),
        }
