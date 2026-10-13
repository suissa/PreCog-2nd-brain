from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True, slots=True)
class PredictionObservation:
    """A prediction captured before execution and its later observed outcome."""

    prediction_id: str
    predicted_behavior_id: str
    confidence: float
    actual_behavior_id: str
    outcome: str
    evidence_ids: tuple[str, ...]
    experience_id: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.prediction_id, "prediction_id"),
            (self.predicted_behavior_id, "predicted_behavior_id"),
            (self.actual_behavior_id, "actual_behavior_id"),
            (self.outcome, "outcome"),
            (self.experience_id, "experience_id"),
        ):
            if not value:
                raise ValueError(f"{name} must be non-empty")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if not self.evidence_ids:
            raise ValueError("prediction observation requires evidence_ids")


@dataclass(frozen=True, slots=True)
class OutcomeEvaluationReport:
    sample_count: int
    behavior_accuracy: float
    successful_outcome_rate: float
    mean_confidence: float
    brier_score: float
    evidence_coverage: float
    evaluated_experience_ids: tuple[str, ...]
    passed: bool
    reasons: tuple[str, ...]


class OutcomeEvaluator:
    """Deterministic offline evaluator; it never deploys or promotes candidates."""

    def evaluate(
        self,
        observations: Iterable[PredictionObservation],
        *,
        successful_outcomes: frozenset[str] = frozenset({"succeeded", "success", "completed"}),
        min_samples: int = 20,
        min_behavior_accuracy: float = 0.8,
        min_success_rate: float = 0.8,
        max_brier_score: float = 0.2,
        min_evidence_coverage: float = 1.0,
    ) -> OutcomeEvaluationReport:
        items = tuple(observations)
        n = len(items)
        if n == 0:
            return OutcomeEvaluationReport(
                0, 0.0, 0.0, 0.0, 1.0, 0.0, (), False,
                ("no observations",),
            )

        accuracy = sum(
            item.predicted_behavior_id == item.actual_behavior_id for item in items
        ) / n
        success_rate = sum(item.outcome in successful_outcomes for item in items) / n
        mean_confidence = sum(item.confidence for item in items) / n
        # Confidence estimates the probability that the predicted Behavior is correct.
        brier = sum(
            (item.confidence - float(item.predicted_behavior_id == item.actual_behavior_id)) ** 2
            for item in items
        ) / n
        evidence_coverage = sum(bool(item.evidence_ids) for item in items) / n

        reasons: list[str] = []
        if n < min_samples:
            reasons.append(f"insufficient sample count: {n} < {min_samples}")
        if accuracy < min_behavior_accuracy:
            reasons.append(f"behavior accuracy below threshold: {accuracy:.3f}")
        if success_rate < min_success_rate:
            reasons.append(f"successful outcome rate below threshold: {success_rate:.3f}")
        if brier > max_brier_score:
            reasons.append(f"Brier score above threshold: {brier:.3f}")
        if evidence_coverage < min_evidence_coverage:
            reasons.append(f"evidence coverage below threshold: {evidence_coverage:.3f}")

        return OutcomeEvaluationReport(
            sample_count=n,
            behavior_accuracy=accuracy,
            successful_outcome_rate=success_rate,
            mean_confidence=mean_confidence,
            brier_score=brier,
            evidence_coverage=evidence_coverage,
            evaluated_experience_ids=tuple(dict.fromkeys(item.experience_id for item in items)),
            passed=not reasons,
            reasons=tuple(reasons),
        )
