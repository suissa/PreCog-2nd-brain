from datetime import datetime, timezone

import pytest

from precog.models import Experience, Provenance
from precog.postgres import PostgresStore


NOW = datetime.now(timezone.utc)


class Cursor:
    def __init__(self, rows=()):
        self.rows = list(rows)
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query, params):
        self.executed.append((query, params))

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class Connection:
    def __init__(self, rows=()):
        self.cursor_obj = Cursor(rows)
        self.commits = 0

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.commits += 1


def experience() -> Experience:
    return Experience(
        "e1", "t1", NOW, NOW, "agent", "message",
        {"value": 1}, Provenance(("source-1",), "test"),
    )


def row(e: Experience):
    return (
        e.id, e.trajectory_id, e.occurred_at, e.recorded_at, e.actor,
        e.event_type, dict(e.payload),
        {"source_ids": list(e.provenance.source_ids),
         "derivation": e.provenance.derivation,
         "schema_version": e.provenance.schema_version},
        e.schema_version, e.intent_id, e.behavior_id, e.action, e.outcome,
    )


def test_append_experience_is_idempotent():
    e = experience()
    conn = Connection([(e.id,)])
    store = PostgresStore(conn)
    assert store.append_experience(e) is True
    assert conn.commits == 1


def test_append_rejects_same_id_with_different_content():
    e = experience()
    conn = Connection([])
    store = PostgresStore(conn)
    assert store.append_experience(e) is True

    existing = Connection([row(e)])
    existing.cursor_obj.rows = [row(e._replace())] if hasattr(e, "_replace") else [row(e)]
    # Simulate a conflicting database record returned by get_experience.
    other = Experience(
        e.id, e.trajectory_id, e.occurred_at, e.recorded_at, e.actor,
        "different", e.payload, e.provenance,
    )
    existing.cursor_obj.rows = [row(other)]
    with pytest.raises(ValueError, match="different content"):
        PostgresStore(existing).append_experience(e)


def test_experiences_filters_by_trajectory():
    e1 = experience()
    e2 = Experience("e2", "t2", NOW, NOW, "agent", "message", {}, e1.provenance)
    conn = Connection([row(e1), row(e2)])
    assert PostgresStore(conn).experiences("t1") == (e1,)

    assert "WHERE trajectory_id = %s" in conn.cursor_obj.executed[0][0]
