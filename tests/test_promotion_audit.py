from datetime import datetime, timezone

import pytest

from precog.continual import ChampionChallenger, ModelCandidate
from precog.outcome_evaluation import OutcomeEvaluationReport
from precog.promotion_audit import (
    InMemoryPromotionAuditLog,
    PromotionAuditEvent,
    PromotionAuditRecorder,
)


def report() -> OutcomeEvaluationReport:
    return OutcomeEvaluationReport(
        sample_count=2,
        behavior_accuracy=1.0,
        successful_outcome_rate=1.0,
        mean_confidence=0.9,
        brier_score=0.01,
        evidence_coverage=1.0,
        evaluated_experience_ids=("exp-1", "exp-2"),
        passed=True,
        reasons=(),
    )


def candidate(name: str) -> ModelCandidate:
    return ModelCandidate(name, "v1", 0.9, ("commit:abc", "dataset:golden"))


def test_audit_recorder_preserves_decision_metrics_and_provenance() -> None:
    log = InMemoryPromotionAuditLog()
    recorder = PromotionAuditRecorder(log)
    challenger = candidate("challenger")
    decision = ChampionChallenger().evaluate_outcomes(challenger, report())
    timestamp = datetime(2026, 10, 13, tzinfo=timezone.utc)

    event = recorder.record(
        candidate=challenger, decision=decision, report=report(), recorded_at=timestamp
    )

    assert event.promoted
    assert event.candidate_provenance == challenger.provenance
    assert event.evaluated_experience_ids == ("exp-1", "exp-2")
    assert event.recorded_at == timestamp
    assert log.list_events() == (event,)


def test_audit_log_is_idempotent_and_rejects_conflicting_replay() -> None:
    log = InMemoryPromotionAuditLog()
    event = PromotionAuditEvent(
        id="audit-1",
        candidate_id="candidate-1",
        candidate_version="v1",
        candidate_provenance=("commit:abc",),
        baseline_candidate_id=None,
        promoted=True,
        reason="outcome gates passed",
        candidate_quality=0.99,
        baseline_quality=None,
        sample_count=2,
        evaluated_experience_ids=("exp-1", "exp-2"),
        behavior_accuracy=1.0,
        successful_outcome_rate=1.0,
        brier_score=0.01,
        evidence_coverage=1.0,
        guardrail_failures=(),
        recorded_at=datetime(2026, 10, 13, tzinfo=timezone.utc),
    )

    assert log.append(event) is True
    assert log.append(event) is False
    assert len(log.list_events()) == 1

    with pytest.raises(ValueError, match="conflicting content"):
        log.append(
            PromotionAuditEvent(
                id=event.id,
                candidate_id=event.candidate_id,
                candidate_version=event.candidate_version,
                candidate_provenance=event.candidate_provenance,
                baseline_candidate_id=None,
                promoted=False,
                reason="different decision",
                candidate_quality=event.candidate_quality,
                baseline_quality=None,
                sample_count=event.sample_count,
                evaluated_experience_ids=event.evaluated_experience_ids,
                behavior_accuracy=event.behavior_accuracy,
                successful_outcome_rate=event.successful_outcome_rate,
                brier_score=event.brier_score,
                evidence_coverage=event.evidence_coverage,
                guardrail_failures=("regression",),
                recorded_at=event.recorded_at,
            )
        )


def test_audit_event_rejects_naive_timestamps() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        PromotionAuditEvent(
            id="audit-1",
            candidate_id="candidate-1",
            candidate_version="v1",
            candidate_provenance=("commit:abc",),
            baseline_candidate_id=None,
            promoted=False,
            reason="blocked",
            candidate_quality=0.5,
            baseline_quality=None,
            sample_count=0,
            evaluated_experience_ids=(),
            behavior_accuracy=0.0,
            successful_outcome_rate=0.0,
            brier_score=1.0,
            evidence_coverage=0.0,
            guardrail_failures=("no evidence",),
            recorded_at=datetime(2026, 10, 13),
        )
