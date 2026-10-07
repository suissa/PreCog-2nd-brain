from datetime import datetime, timedelta, timezone

from precog.models import Memory, MemoryLifecycle, MemoryType, Provenance
from precog.retrieval import LexicalRetriever
from precog.store import InMemoryStore

NOW = datetime(2026, 10, 7, 12, 0, tzinfo=timezone.utc)


def memory(store: InMemoryStore, mid: str, content: str, *, lifecycle=MemoryLifecycle.ACTIVE,
           valid_from=None, valid_to=None, tenant_id="t1", actor="agent") -> Memory:
    store.append_experience(
        __import__("precog.models", fromlist=["Experience"]).Experience(
            f"e-{mid}", "trajectory", NOW, NOW, actor, "capture", {},
            Provenance((f"e-{mid}",), "test"),
        )
    )
    value = Memory(
        mid, MemoryType.SEMANTIC, content, (f"e-{mid}",), NOW,
        valid_from=valid_from, valid_to=valid_to, lifecycle=lifecycle,
        provenance=Provenance((f"e-{mid}",), "test"),
        metadata={"tenant_id": tenant_id, "actor": actor},
    )
    store.put_memory(value)
    return value


def test_exact_identifier_and_phrase_are_searchable():
    store = InMemoryStore()
    first = memory(store, "m-error-42", "payment failed with ERROR-42 after timeout")
    memory(store, "m-other", "successful payment")
    results = LexicalRetriever(store).search("ERROR-42", at=NOW)
    assert results[0].object_id == first.id
    assert results[0].provenance.source_ids == ("e-m-error-42",)
    phrase = LexicalRetriever(store).search("payment failed with ERROR-42", at=NOW)
    assert phrase[0].object_id == first.id
    assert phrase[0].score == 1.0


def test_no_match_returns_empty():
    store = InMemoryStore()
    memory(store, "m1", "customer prefers morning")
    assert LexicalRetriever(store).search("unrelated error", at=NOW) == ()


def test_lifecycle_and_tenant_actor_filters_are_deterministic():
    store = InMemoryStore()
    active = memory(store, "m-active", "customer preference", tenant_id="t1", actor="alice")
    memory(store, "m-archived", "customer preference", lifecycle=MemoryLifecycle.ARCHIVED)
    memory(store, "m-other-tenant", "customer preference", tenant_id="t2", actor="alice")
    results = LexicalRetriever(store).search(
        "customer preference", at=NOW, tenant_id="t1", actor="alice",
        lifecycle={MemoryLifecycle.ACTIVE},
    )
    assert [item.object_id for item in results] == [active.id]


def test_temporal_filter_excludes_future_and_expired_memories():
    store = InMemoryStore()
    current = memory(store, "m-current", "release error", valid_from=NOW - timedelta(days=1))
    memory(store, "m-future", "release error", valid_from=NOW + timedelta(days=1))
    memory(store, "m-expired", "release error", valid_to=NOW - timedelta(seconds=1))
    results = LexicalRetriever(store).search("release error", at=NOW)
    assert [item.object_id for item in results] == [current.id]


def test_semantic_retriever_delegates_query_embedding_to_provider():
    from precog.embeddings import DeterministicEmbeddingProvider
    from precog.retrieval import SemanticRetriever

    class FakeStore:
        def semantic_search(self, vector, **kwargs):
            assert len(vector) == 4
            assert kwargs["model"] == "deterministic"
            return ({
                "object_id": "m1",
                "score": 0.8,
                "provenance": Provenance(("e1",), "test"),
                "lifecycle": MemoryLifecycle.ACTIVE,
                "source_type": "memory",
            },)

    result = SemanticRetriever(FakeStore(), DeterministicEmbeddingProvider(4)).search("payment failed")
    assert result[0].object_id == "m1"
    assert result[0].semantic_score == 0.8
