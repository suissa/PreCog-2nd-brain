from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Protocol

from .models import Experience, Provenance, stable_id


class ExperienceWriter(Protocol):
    """Minimal persistence contract implemented by PreCog stores."""

    def append_experience(self, experience: Experience) -> bool: ...


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """An outcome reported by the authoritative runtime after execution."""

    event_id: str
    trajectory_id: str
    actor: str
    behavior_id: str
    action: str
    outcome: str
    occurred_at: datetime
    recorded_at: datetime
    payload: Mapping[str, Any]
    intent_id: str | None = None
    source_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for value, name in (
            (self.event_id, "event_id"),
            (self.trajectory_id, "trajectory_id"),
            (self.actor, "actor"),
            (self.behavior_id, "behavior_id"),
            (self.action, "action"),
            (self.outcome, "outcome"),
        ):
            if not value:
                raise ValueError(f"{name} must be non-empty")
        if self.occurred_at.tzinfo is None or self.recorded_at.tzinfo is None:
            raise ValueError("execution result timestamps must be timezone-aware")


@dataclass(frozen=True, slots=True)
class RecordedExecution:
    experience: Experience
    inserted: bool


class ExecutionFeedbackRecorder:
    """Persists runtime-reported outcomes as immutable, idempotent Experiences.

    This component records results only. It does not execute actions, authorize
    a proposal, or infer success from a prediction.
    """

    def __init__(self, writer: ExperienceWriter) -> None:
        self._writer = writer

    def record(self, result: ExecutionResult) -> RecordedExecution:
        source_ids = tuple(dict.fromkeys(result.source_ids or (result.event_id,)))
        experience = Experience(
            id=stable_id("experience", result.event_id),
            trajectory_id=result.trajectory_id,
            occurred_at=result.occurred_at,
            recorded_at=result.recorded_at,
            actor=result.actor,
            event_type="execution_result",
            payload={
                **dict(result.payload),
                "event_id": result.event_id,
                "behavior_id": result.behavior_id,
                "action": result.action,
                "outcome": result.outcome,
            },
            provenance=Provenance(source_ids, "runtime-execution-feedback"),
            intent_id=result.intent_id,
            behavior_id=result.behavior_id,
            action=result.action,
            outcome=result.outcome,
        )
        inserted = self._writer.append_experience(experience)
        return RecordedExecution(experience=experience, inserted=inserted)
