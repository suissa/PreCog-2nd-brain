from precog.audit_integrity import GENESIS_HASH, calculate_event_hash, verify_chain
from precog.promotion_audit import PromotionAuditEvent
from datetime import datetime, timezone


def event(event_id: str, reason: str = "pass") -> PromotionAuditEvent:
    return PromotionAuditEvent(
        id=event_id, candidate_id="candidate", candidate_version="v1",
        candidate_provenance=("commit:abc",), baseline_candidate_id=None,
        promoted=True, reason=reason, candidate_quality=0.9, baseline_quality=None,
        sample_count=1, evaluated_experience_ids=("exp-1",), behavior_accuracy=1.0,
        successful_outcome_rate=1.0, brier_score=0.0, evidence_coverage=1.0,
        guardrail_failures=(), recorded_at=datetime(2026, 10, 13, tzinfo=timezone.utc),
    )


def test_chain_verifies_two_events():
    first, second = event("one"), event("two")
    h1 = calculate_event_hash(first, GENESIS_HASH)
    h2 = calculate_event_hash(second, h1)
    report = verify_chain(((first, GENESIS_HASH, h1), (second, h1, h2)), expected_head_hash=h2)
    assert report.valid
    assert report.checked_events == 2


def test_chain_detects_content_tampering():
    original = event("one")
    changed = event("one", reason="altered")
    digest = calculate_event_hash(original, GENESIS_HASH)
    report = verify_chain(((changed, GENESIS_HASH, digest),), expected_head_hash=digest)
    assert not report.valid
    assert any("content" in error for error in report.errors)


def test_legacy_rows_are_counted_as_unhashed():
    report = verify_chain(((event("legacy"), None, None),), expected_head_hash=GENESIS_HASH)
    assert report.valid
    assert report.legacy_unhashed_events == 1
    assert report.checked_events == 0
