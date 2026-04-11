from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class LifecycleIntent(Enum):
    ONBOARDING = "onboarding"
    OFFBOARDING = "offboarding"


class LifecycleLayer(Enum):
    PROJECTION = 0
    RUNTIME_ENV = 1
    LEDGER = 2
    DOC_SYNC = 3

    def label(self) -> str:
        return self.name.lower().replace("_", "-")


@dataclass(frozen=True)
class ProjectionLifecycleStage:
    layer: LifecycleLayer
    name: str
    description: str
    write_mode: bool
    expectations: dict[str, str] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "layer": self.layer.label(),
            "name": self.name,
            "description": self.description,
            "write_mode": self.write_mode,
        }
        if self.expectations:
            payload["expectations"] = dict(self.expectations)
        return payload


class ProjectionLifecyclePlan:
    def __init__(self, intent: LifecycleIntent, *, dry_run: bool = False) -> None:
        self.intent = intent
        self.dry_run = dry_run
        self._stages: list[ProjectionLifecycleStage] = []
        self._doc_sync_index: int | None = None

    @property
    def stages(self) -> tuple[ProjectionLifecycleStage, ...]:
        return tuple(self._stages)

    def add_stage(self, stage: ProjectionLifecycleStage) -> None:
        if self.dry_run and stage.write_mode:
            raise ValueError("dry-run plans may not include write-mode stages")
        if self._doc_sync_index is not None and stage.layer != LifecycleLayer.DOC_SYNC:
            raise ValueError("no additional stages may be appended after doc-sync")
        if self._stages:
            last_layer = self._stages[-1].layer
            if stage.layer.value < last_layer.value:
                raise ValueError("layers must be added in monotonic order")
        if stage.layer == LifecycleLayer.DOC_SYNC:
            if self._doc_sync_index is not None:
                raise ValueError("doc-sync stage is already recorded")
            self._doc_sync_index = len(self._stages)
        self._stages.append(stage)

    def validate(self) -> None:
        if not self._stages:
            raise ValueError("no stages recorded for lifecycle plan")
        if self._doc_sync_index is None:
            raise ValueError("projection lifecycle must include a doc-sync stage")

    def summary(self) -> dict[str, Any]:
        return {
            "intent": self.intent.value,
            "dry_run": self.dry_run,
            "write_expected": any(stage.write_mode for stage in self._stages),
            "sequence": [stage.name for stage in self._stages],
            "layers": [stage.layer.label() for stage in self._stages],
            "stages": [stage.to_dict() for stage in self._stages],
        }


def _doc_sync_stage(*, expectations: dict[str, str] | None = None) -> ProjectionLifecycleStage:
    return ProjectionLifecycleStage(
        layer=LifecycleLayer.DOC_SYNC,
        name="doc sync confirmation",
        description="Surface documentation updates after projection, runtime, and ledger changes.",
        write_mode=False,
        expectations=expectations,
    )


def default_onboarding_plan(*, dry_run: bool = False) -> ProjectionLifecyclePlan:
    plan = ProjectionLifecyclePlan(LifecycleIntent.ONBOARDING, dry_run=dry_run)
    plan.add_stage(
        ProjectionLifecycleStage(
            layer=LifecycleLayer.PROJECTION,
            name="inventory projection",
            description="Stage the projection inventory for the new project.",
            write_mode=not dry_run,
            expectations={
                "inventory": "project entry",
                "projection": "app should appear in inventory apps",
            },
        )
    )
    plan.add_stage(
        ProjectionLifecycleStage(
            layer=LifecycleLayer.RUNTIME_ENV,
            name="runtime environment sync",
            description="Capture runtime-env records and validate no drift before finalizing.",
            write_mode=not dry_run,
            expectations={
                "runtime_env": "declare necessary runtime files",
            },
        )
    )
    plan.add_stage(
        ProjectionLifecycleStage(
            layer=LifecycleLayer.LEDGER,
            name="ledger refresh",
            description="Refresh ledger entries so the project appears in onepanel ledgers.",
            write_mode=not dry_run,
            expectations={
                "ledger": "apps/app_resources/app entries updated",
            },
        )
    )
    plan.add_stage(
        _doc_sync_stage(
            expectations={
                "docs": "onboarding runbook includes new projection expectation",
            }
        )
    )
    return plan


def default_offboarding_plan(*, dry_run: bool = False) -> ProjectionLifecyclePlan:
    plan = ProjectionLifecyclePlan(LifecycleIntent.OFFBOARDING, dry_run=dry_run)
    plan.add_stage(
        ProjectionLifecycleStage(
            layer=LifecycleLayer.PROJECTION,
            name="projection retirement",
            description="Mark inventory projection for removal during offboarding.",
            write_mode=not dry_run,
            expectations={
                "inventory": "app marked for removal",
            },
        )
    )
    plan.add_stage(
        ProjectionLifecycleStage(
            layer=LifecycleLayer.RUNTIME_ENV,
            name="runtime environment cleanup",
            description="Ensure runtime env artifacts and docker state are captured before deletion.",
            write_mode=not dry_run,
            expectations={
                "runtime_env": "clean runtime artifacts",
            },
        )
    )
    plan.add_stage(
        ProjectionLifecycleStage(
            layer=LifecycleLayer.LEDGER,
            name="ledger retirement",
            description="Prune ledger entries so the project disappears from active ledgers.",
            write_mode=not dry_run,
            expectations={
                "ledger": "app/app_resource entries removed",
            },
        )
    )
    plan.add_stage(
        _doc_sync_stage(
            expectations={
                "docs": "offboarding gating section is updated",
            }
        )
    )
    return plan


__all__ = [
    "LifecycleIntent",
    "LifecycleLayer",
    "ProjectionLifecycleStage",
    "ProjectionLifecyclePlan",
    "default_onboarding_plan",
    "default_offboarding_plan",
]
