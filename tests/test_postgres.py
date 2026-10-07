from datetime import datetime, timezone

import pytest

from precog.models import (
    Experience, Knowledge, Memory, MemoryLifecycle, MemoryType, Provenance,
    Relation, RelationType, Trajectory,
)
from precog.postgres import PostgresStore

NOW = datetime.now(timezone.utc)


class Cursor:
    def __init__(self, rows=(), fetchone_values=None):
        self.rows = list(rows)
        self.fetchone_values = list(fetchone_values or [])
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
    def __init__(self, rows=(), fetchone_values=None):
        self.cursor_obj = Cursor(rows, fetchone_values)
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def exp(i="e1", t="t1"):
    return Experience(i, t, NOW, NOW, "agent", "message", {"value": 1},
                      Provenance(("source-1",), "test"))


def prow(e):
    return (e.id, e.trajectory_id, e.occurred_at, e.recorded_at, e.actor, e.event_type,
            dict(e.payload), {"source_ids": list(e.provenance.source_ids),
            "derivation": e.provenance.derivation, "schema_version": 1}, e.schema_version,
            e.intent_id, e.behavior_id, e.action, e.outcome)


def test_append_experience_is_idempotent():
    conn = Connection([( "e1",)])
    assert PostgresStore(conn).append_experience(exp()) is True
    assert conn.commits == 1


def test_append_rejects_same_id_with_different_content():
    e = exp()
    other = Experience(e.id, e.trajectory_id, e.occurred_at, e.recorded_at, e.actor,
                        "different", e.payload, e.provenance)
    conn = Connection(fetchone_values=[None, prow(other)])
    with pytest.raises(ValueError, match="different content"):
        PostgresStore(conn).append_experience(e)


def test_derived_state_persistence_validates_provenance():
    class SourceConnection(Connection):
        def __init__(self):
            super().__init__([("e1",)])
    conn = SourceConnection()
    store = PostgresStore(conn)
    memory = Memory("m1", MemoryType.EPISODIC, "remember", ("e1",), NOW)
    store.put_memory(memory)
    assert conn.commits == 1
    assert "INSERT INTO memory" in conn.cursor_obj.executed[-1][0]


def test_memory_read_excludes_archived_by_default():
    provenance = Provenance(("e1",), "x")
    active = Memory("m1", MemoryType.SEMANTIC, "a", ("e1",), NOW, provenance=provenance)
    archived = Memory("m2", MemoryType.SEMANTIC, "b", ("e1",), NOW,
                      lifecycle=MemoryLifecycle.ARCHIVED)
    rows = [
        (active.id, active.memory_type.value, active.content, ["e1"], NOW, None, None,
         active.confidence, active.salience, active.lifecycle.value,
         {"source_ids":["e1"],"derivation":"x","schema_version":1}, {}, 1, 1)
    ]
    conn = Connection(rows)
    result = PostgresStore(conn).memories()
    assert result == (active,)
    assert "lifecycle <> %s" in conn.cursor_obj.executed[0][0]


def test_knowledge_and_relation_roundtrip_decoders():
    provenance = Provenance(("e1",), "x")
    knowledge = Knowledge("k1", "statement", "scope", ("e1",), .8, "active", 1, NOW,
                          provenance=provenance)
    relation = Relation("r1", "e1", "k1", RelationType.SUPPORTS, .9, NOW,
                        provenance=provenance)
    krow = (knowledge.id, knowledge.statement, knowledge.scope, ["e1"], knowledge.confidence,
            knowledge.status, knowledge.version, knowledge.created_at, None, None,
            {"source_ids":["e1"],"derivation":"x","schema_version":1})
    rrow = (relation.id, relation.source_id, relation.target_id, relation.relation_type.value,
            relation.confidence, relation.created_at, None, None,
            {"source_ids":["e1"],"derivation":"x","schema_version":1})
    conn_k = Connection([krow])
    conn_r = Connection([rrow])
    assert PostgresStore(conn_k).knowledge() == (knowledge,)
    assert PostgresStore(conn_r).relations() == (relation,)


def test_experiences_filters_by_trajectory():
    e1 = exp()
    conn = Connection([prow(e1)])
    assert PostgresStore(conn).experiences("t1") == (e1,)
    assert "WHERE trajectory_id = %s" in conn.cursor_obj.executed[0][0]


def test_append_rolls_back_on_persistence_failure():
    class FailingCursor(Cursor):
        def execute(self, query, params=()):
            raise RuntimeError("db failure")

    class FailingConnection(Connection):
        def __init__(self):
            self.cursor_obj = FailingCursor()
            self.commits = 0
            self.rollbacks = 0

    conn = FailingConnection()
    with pytest.raises(RuntimeError, match="db failure"):
        PostgresStore(conn).append_experience(exp())
    assert conn.rollbacks == 1

def test_lexical_search_uses_fts_and_preserves_provenance():
    provenance = {"source_ids": ["e1"], "derivation": "test", "schema_version": 1}
    conn = Connection([("m1", 0.75, provenance, "active")])
    result = PostgresStore(conn).lexical_search(
        "ERROR-42", at=NOW, tenant_id="t1", actor="agent",
        lifecycle=("active",), limit=5,
    )
    assert result[0]["object_id"] == "m1"
    assert result[0]["score"] == 0.75
    assert result[0]["provenance"].source_ids == ("e1",)
    sql, params = conn.cursor_obj.executed[0]
    assert "to_tsvector('simple', m.content)" in sql
    assert "ts_rank_cd" in sql
    assert "m.metadata ->> 'tenant_id'" in sql
    assert "m.metadata ->> 'actor'" in sql
    assert "ORDER BY score DESC, m.memory_id ASC" in sql
    assert params[0] == "ERROR-42"
    assert params[-1] == 5


def test_embedding_persistence_records_provider_and_source_metadata():
    from precog.embeddings import DeterministicEmbeddingProvider, build_embedding
    memory = Memory("m-embed", MemoryType.SEMANTIC, "payment failed", ("e1",), NOW,
                    provenance=Provenance(("e1",), "test"))
    embedding = build_embedding(memory, DeterministicEmbeddingProvider(4, "model-a"))
    conn = Connection([("m-embed", list(embedding.vector), "model-a", "1", 4, 1, embedding.source_hash)])
    store = PostgresStore(conn)
    store.put_embedding(embedding)
    loaded = store.embedding("m-embed")
    assert loaded == embedding
    sql, params = conn.cursor_obj.executed[0]
    assert "INSERT INTO memory_embedding" in sql
    assert params[2] == "1"
    assert params[3] == 4


def test_semantic_search_rejects_query_dimension_mismatch():
    conn = Connection()
    assert PostgresStore(conn).semantic_search((1.0, 2.0), model="m", provider_version="1",
                                               dimensions=3) == ()
    assert conn.cursor_obj.executed == []


def test_semantic_search_excludes_stale_source_versions_and_archived():
    conn = Connection([("m1", 0.92, {"source_ids": ["e1"], "derivation": "embedding",
                                     "schema_version": 1}, "active", 1, 1)])
    result = PostgresStore(conn).semantic_search((1.0, 2.0), model="model-a",
                                                 provider_version="1", dimensions=2, limit=5)
    assert result[0]["object_id"] == "m1"
    sql, params = conn.cursor_obj.executed[0]
    assert "e.source_version = m.version" in sql
    assert "e.model = %s" in sql
    assert "e.provider_version = %s" in sql
    assert params[-1] == 5
