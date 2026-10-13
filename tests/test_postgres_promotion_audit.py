from datetime import datetime, timezone

import pytest

from precog.audit_integrity import (
    GENESIS_HASH,
    calculate_event_hash,
    verify_chain,
)
from precog.promotion_audit import PromotionAuditEvent
from precog.postgres_promotion_audit import PostgresPromotionAuditLog


NOW = datetime(2026, 10, 13, tzinfo=timezone.utc)


class Cursor:
    def __init__(self, rows=(), fetchone_values=()):
        self.rows = list(rows)
        self.fetchone_values = list(fetchone_values)
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query, params=()):
        self.executed.append((query, params))

    def fetchone(self):
        if self.fetchone_values:
            return self.fetchone_values.pop(0)
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class Connection:
    def __init__(self, rows=(), fetchone_values=()):
        self.cursor_obj = Cursor(rows, fetchone_values)
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def event(event_id="audit-1", reason="outcome gates passed"):
    return PromotionAuditEvent(
        id=event_id, candidate_id="candidate-1", candidate_version="v1",
        candidate_provenance=("commit:abc", "dataset:golden"),
        baseline_candidate_id="champion-0", promoted=True, reason=reason,
        candidate_quality=0.99, baseline_quality=0.9, sample_count=2,
        evaluated_experience_ids=("exp-1", "exp-2"), behavior_accuracy=1.0,
        successful_outcome_rate=1.0, brier_score=0.01, evidence_coverage=1.0,
        guardrail_failures=(), recorded_at=NOW,
    )


def row_for(item):
    return (
        item.id, item.candidate_id, item.candidate_version,
        list(item.candidate_provenance), item.baseline_candidate_id,
        item.promoted, item.reason, item.candidate_quality, item.baseline_quality,
        item.sample_count, list(item.evaluated_experience_ids),
        item.behavior_accuracy, item.successful_outcome_rate, item.brier_score,
        item.evidence_coverage, list(item.guardrail_failures), item.recorded_at,
    )


def test_postgres_audit_append_commits_hash_chained_insert():
    item = event()
    connection = Connection(fetchone_values=[(GENESIS_HASH,), None])

    assert PostgresPromotionAuditLog(connection).append(item) is True
    assert connection.commits == 1
    assert connection.rollbacks == 0
    assert "FOR UPDATE" in connection.cursor_obj.executed[0][0]
    insert_query, params = connection.cursor_obj.executed[2]
    assert "INSERT INTO promotion_audit" in insert_query
    assert "previous_hash, event_hash" in insert_query
    assert params[-2] == GENESIS_HASH
    assert params[-1] == calculate_event_hash(item, GENESIS_HASH)


def test_postgres_audit_append_is_idempotent_on_identical_replay():
    item = event()
    connection = Connection(fetchone_values=[("a" * 64,), row_for(item)])

    assert PostgresPromotionAuditLog(connection).append(item) is False
    assert connection.commits == 1
    assert connection.rollbacks == 0
    assert len(connection.cursor_obj.executed) == 2


def test_postgres_audit_rejects_conflicting_event_id_replay():
    item = event()
    connection = Connection(fetchone_values=[("a" * 64,), row_for(event(reason="different reason"))])

    with pytest.raises(ValueError, match="conflicting content"):
        PostgresPromotionAuditLog(connection).append(item)
    assert connection.rollbacks == 1


def test_postgres_audit_lists_and_decodes_json_fields():
    item = event()
    connection = Connection(rows=[row_for(item)])

    assert PostgresPromotionAuditLog(connection).list_events() == (item,)
    query, params = connection.cursor_obj.executed[0]
    assert "ORDER BY audit_sequence" in query
    assert params == (1000,)
    assert connection.commits == 1


def test_postgres_audit_rejects_negative_limit():
    with pytest.raises(ValueError, match="non-negative"):
        PostgresPromotionAuditLog(Connection()).list_events(limit=-1)


def test_hash_chain_verifies_content_and_previous_hash():
    first = event("audit-1")
    first_hash = calculate_event_hash(first, GENESIS_HASH)
    second = event("audit-2")
    second_hash = calculate_event_hash(second, first_hash)

    report = verify_chain(
        ((first, GENESIS_HASH, first_hash), (second, first_hash, second_hash)),
        expected_head_hash=second_hash,
    )

    assert report.valid
    assert report.checked_events == 2
    assert report.legacy_unhashed_events == 0
    assert report.verified_head_hash == second_hash


def test_hash_chain_detects_changed_content_and_broken_link():
    first = event("audit-1")
    first_hash = calculate_event_hash(first, GENESIS_HASH)
    second = event("audit-2")
    second_hash = calculate_event_hash(second, first_hash)

    report = verify_chain(
        ((first, GENESIS_HASH, first_hash), (second, "b" * 64, second_hash)),
        expected_head_hash=second_hash,
    )

    assert not report.valid
    assert any("previous hash" in error for error in report.errors)


def test_hash_chain_reports_legacy_rows_without_claiming_full_coverage():
    item = event()
    report = verify_chain(((item, None, None),), expected_head_hash=GENESIS_HASH)

    assert report.valid
    assert report.legacy_unhashed_events == 1
    assert report.checked_events == 0
