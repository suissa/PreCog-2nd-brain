from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from .continual import ModelCandidate, OutcomePromotionDecision
from .models import stable_id
from .outcome_evaluation import OutcomeEvaluationReport


@dataclass(frozen=True, slots=True)
class PromotionAuditEvent:
    """Immutable audit evidence for an offline promotion decision."""

    id: str
    candidate_id: str
    candidate_version: str
    candidate_provenance: tuple[str, ...]
    baseline_candidate_id: str | None
    promoted: bool
    reason: str
    candidate_quality: float
    baseline_quality: float | None
    sample_count: int
    evaluated_experience_ids: tuple[str, ...]
    behavior_accuracy: float
    successful_outcome_rate: float
    brier_score: float
    evidence_coverage: float
    guardrail_failures: tuple[str, ...]
    recorded_at: datetime

    def __post_init__(self) -> None:
        for value, name in (
            (self.id, "id"),
            (self.candidate_id, "candidate_id"),
            (self.candidate_version, "candidate_version"),
            (self.reason, "reason"),
        ):
            if not value:
                raise ValueError(f"{name} must be non-empty")
        if self.recorded_at.tzinfo is None:
            raise ValueError("recorded_at must be timezone-aware")
        if self.sample_count < 0:
            raise ValueError("sample_count must be non-negative")
        for name, value in (
            ("candidate_quality", self.candidate_quality),
            ("behavior_accuracy", self.behavior_accuracy),
            ("successful_outcome_rate", self.successful_outcome_rate),
            ("brier_score", self.brier_score),
            ("evidence_coverage", self.evidence_coverage),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.baseline_quality is not None and not 0.0 <= self.baseline_quality <= 1.0:
            raise ValueError("baseline_quality must be between 0 and 1")
        if self.promoted and not self.evaluated_experience_ids:
            raise ValueError("a promoted candidate requires evaluated experience evidence")


class PromotionAuditWriter(Protocol):
    """Append-only sink contract for in-memory or persistent audit stores."""

    def append(self, event: PromotionAuditEvent) -> bool: ...


class InMemoryPromotionAuditLog:
    """Append-only reference log with idempotent replay and conflict detection."""

    def __init__(self) -> None:
        self._events: dict[str, PromotionAuditEvent] = {}

    def append(self, event: PromotionAuditEvent) -> bool:
        existing = self._events.get(event.id)
        if existing is not None:
            if existing != event:
                raise ValueError("promotion audit event ID reused with conflicting content")
            return False
        self._events[event.id] = event
        return True

    def list_events(self) -> tuple[PromotionAuditEvent, ...]:
        return tuple(self._events.values())


class PromotionAuditRecorder:
    """Records decisions and their evaluation evidence; it never deploys candidates."""

    def __init__(self, writer: PromotionAuditWriter) -> None:
        self._writer = writer

    def record(
        self,
        *,
        candidate: ModelCandidate,
        decision: OutcomePromotionDecision,
        report: OutcomeEvaluationReport,
        baseline_candidate: ModelCandidate | None = None,
        recorded_at: datetime | None = None,
    ) -> PromotionAuditEvent:
        timestamp = recorded_at or datetime.now(timezone.utc)
        if timestamp.tzinfo is None:
            raise ValueError("recorded_at must be timezone-aware")
        event = PromotionAuditEvent(
            id=stable_id(
                "promotion-audit",
                candidate.id,
                candidate.version,
                decision.reason,
                str(decision.promoted),
                "|".join(report.evaluated_experience_ids),
                timestamp.isoformat(),
            ),
            candidate_id=candidate.id,
            candidate_version=candidate.version,
            candidate_provenance=candidate.provenance,
            baseline_candidate_id=baseline_candidate.id if baseline_candidate else None,
            promoted=decision.promoted,
            reason=decision.reason,
            candidate_quality=decision.candidate_quality,
            baseline_quality=decision.baseline_quality,
            sample_count=report.sample_count,
            evaluated_experience_ids=report.evaluated_experience_ids,
            behavior_accuracy=report.behavior_accuracy,
            successful_outcome_rate=report.successful_outcome_rate,
            brier_score=report.brier_score,
            evidence_coverage=report.evidence_coverage,
            guardrail_failures=decision.guardrail_failures,
            recorded_at=timestamp,
        )
        self._writer.append(event)
        return event
