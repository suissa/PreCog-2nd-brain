from datetime import datetime, timedelta, timezone

import pytest

from precog.models import Memory, MemoryLifecycle, MemoryType, Provenance
from precog.store import InMemoryStore

NOW = datetime(2026, 10, 7, 12, 0, tzinfo=timezone.utc)


def make_memory(store: InMemoryStore, memory_id: str, content: str, *, valid_from=None, valid_to=None):
    store.append_experience(
        __import__("precog.models", fromlist=["Experience"]).Experience(
            f"e-{memory_id}", "t1", NOW, NOW, "actor", "fact",
            {"content": content},
            Provenance((f"e-{memory_id}",), "capture"),
        )
    )
    memory = Memory(
        memory_id, MemoryType.SEMANTIC, content, (f"e-{memory_id}",), NOW,
        valid_from=valid_from, valid_to=valid_to,
        lifecycle=MemoryLifecycle.ACTIVE,
        provenance=Provenance((f"e-{memory_id}",), "test"),
    )
    store.put_memory(memory)
    return memory


def test_temporal_queries_distinguish_current_historical_and_future():
    store = InMemoryStore()
    historical = make_memory(store, "m-h", "old", valid_from=NOW - timedelta(days=2), valid_to=NOW - timedelta(days=1))
    current = make_memory(store, "m-c", "current", valid_from=NOW - timedelta(days=1))
    future = make_memory(store, "m-f", "future", valid_from=NOW + timedelta(days=1))

    assert {m.id for m in store.memories_at(NOW)} == {"m-c"}
    assert {m.id for m in store.historical_memories(NOW)} == {"m-h"}
    assert current.id in {m.id for m in store.current_memories()}
    assert future.id not in {m.id for m in store.memories_at(NOW)}


def test_supersession_closes_old_fact_without_deleting_history():
    store = InMemoryStore()
    old = make_memory(store, "m-old", "old")
    new = make_memory(store, "m-new", "new", valid_from=NOW + timedelta(hours=1))

    relation = store.record_supersession(
        old.id, new.id, at=NOW + timedelta(hours=1),
        provenance=Provenance(("e-m-new",), "supersession"), confidence=0.95,
    )

    assert relation.relation_type.value == "supersedes"
    assert store._memories[old.id].valid_to == NOW + timedelta(hours=1)
    assert store.memory_history(old.id)[-1].valid_to == NOW + timedelta(hours=1)
    assert old.id not in {m.id for m in store.current_memories()}
    assert new.id in {m.id for m in store.current_memories()}


def test_contradiction_preserves_both_claims_and_provenance():
    store = InMemoryStore()
    left = make_memory(store, "m-left", "customer prefers morning")
    right = make_memory(store, "m-right", "customer prefers evening")

    provenance = Provenance(("e-m-left", "e-m-right"), "contradiction-detection")
    relation = store.record_contradiction(
        left.id, right.id, at=NOW, provenance=provenance, confidence=0.8,
    )

    assert left.id in {m.id for m in store.current_memories()}
    assert right.id in {m.id for m in store.current_memories()}
    assert {m.id for m in store.current_consistent_memories()} == set()
    assert relation.provenance == provenance
    assert relation.confidence == 0.8
    assert {r.id for r in store.contradictions(left.id)} == {relation.id}


def test_invalid_memory_interval_is_rejected():
    with pytest.raises(ValueError, match="invalid memory temporal interval"):
        Memory(
            "m-invalid", MemoryType.SEMANTIC, "invalid", ("e-invalid",), NOW,
            valid_from=NOW, valid_to=NOW - timedelta(seconds=1),
            provenance=Provenance(("e-invalid",), "test"),
        )
