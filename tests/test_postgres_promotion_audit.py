from datetime import datetime, timezone

import pytest

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


def event(event_id="audit-1"):
    return PromotionAuditEvent(
        id=event_id,
        candidate_id="candidate-1",
        candidate_version="v1",
        candidate_provenance=("commit:abc", "dataset:golden"),
        baseline_candidate_id="champion-0",
        promoted=True,
        reason="outcome gates passed",
        candidate_quality=0.99,
        baseline_quality=0.9,
        sample_count=2,
        evaluated_experience_ids=("exp-1", "exp-2"),
        behavior_accuracy=1.0,
        successful_outcome_rate=1.0,
        brier_score=0.01,
        evidence_coverage=1.0,
        guardrail_failures=(),
        recorded_at=NOW,
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


def test_postgres_audit_append_commits_insert():
    item = event()
    connection = Connection(fetchone_values=[(item.id,)])

    assert PostgresPromotionAuditLog(connection).append(item) is True
    assert connection.commits == 1
    query, params = connection.cursor_obj.executed[0]
    assert "INSERT INTO promotion_audit" in query
    assert "ON CONFLICT (event_id) DO NOTHING" in query
    assert params[0] == item.id


def test_postgres_audit_append_is_idempotent_on_identical_replay():
    item = event()
    connection = Connection(fetchone_values=[None, row_for(item)])

    assert PostgresPromotionAuditLog(connection).append(item) is False
    assert connection.commits == 1
    assert connection.rollbacks == 0
    assert len(connection.cursor_obj.executed) == 2


def test_postgres_audit_rejects_conflicting_event_id_replay():
    item = event()
    conflicting = event()
    row = list(row_for(conflicting))
    row[6] = "different reason"
    connection = Connection(fetchone_values=[None, tuple(row)])

    with pytest.raises(ValueError, match="conflicting content"):
        PostgresPromotionAuditLog(connection).append(item)
    assert connection.rollbacks == 1


def test_postgres_audit_lists_and_decodes_json_fields():
    item = event()
    connection = Connection(rows=[row_for(item)])

    assert PostgresPromotionAuditLog(connection).list_events() == (item,)
    query, params = connection.cursor_obj.executed[0]
    assert "ORDER BY recorded_at, event_id" in query
    assert params == (1000,)
    assert connection.commits == 1


def test_postgres_audit_rejects_negative_limit():
    with pytest.raises(ValueError, match="non-negative"):
        PostgresPromotionAuditLog(Connection()).list_events(limit=-1)
