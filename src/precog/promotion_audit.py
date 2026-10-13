from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class PromotionAuditEvent:
    """Immutable audit evidence for an offline promotion decision."""

    id: str
    candidate_id: str
    candidate_version: str
    promoted: bool
    reason: str
    sample_count: int
    evaluated_experience_ids: tuple[str, ...]
    behavior_accuracy: float
    successful_outcome_rate: float
    brier_score: float
    evidence_coverage: float
    recorded_at: datetime

    def __post_init__(self) -> None:
        if not self.id or not self.candidate_id or not self.candidate_version or not self.reason:
            raise ValueError("audit identity and reason fields must be non-empty")
        if self.recorded_at.tzinfo is None:
            raise ValueError("recorded_at must be timezone-aware")
        if self.sample_count < 0:
            raise ValueError("sample_count must be non-negative")
        for name, value in (("behavior_accuracy", self.behavior_accuracy), ("successful_outcome_rate", self.successful_outcome_rate), ("brier_score", self.brier_score), ("evidence_coverage", self.evidence_coverage)):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.promoted and not self.evaluated_experience_ids:
            raise ValueError("a promoted candidate requires evaluated experience evidence")
