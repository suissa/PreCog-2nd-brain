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


def test_hybrid_candidate_union_deduplicates_and_exposes_components():
    from precog.retrieval import HybridRetriever
    store = InMemoryStore()
    first = memory(store, "m-a", "payment failure")
    second = memory(store, "m-b", "payment success")
    lexical = LexicalRetriever(store).search("payment", at=NOW)
    duplicate = lexical[0]
    result = HybridRetriever(store).search(
        "payment", now=NOW,
        lexical_candidates=(duplicate,),
        semantic_candidates=(
            type(duplicate)(
                first.id, 0.8, 0.0, 0.8, 0.0, 0.0,
                first.provenance, first.lifecycle, "memory"
            ),
            type(duplicate)(
                second.id, 0.8, 0.0, 0.8, 0.0, 0.0,
                second.provenance, second.lifecycle, "memory"
            ),
            duplicate,
        ),
        metadata_scores={first.id: 0.9},
    )
    ids = [item.object_id for item in result]
    assert set(ids) == {first.id, second.id}
    first_result = next(item for item in result if item.object_id == first.id)
    assert first_result.lexical_score > 0
    assert first_result.semantic_score > 0
    assert first_result.metadata_score == 0.9
    assert len(ids) == len(set(ids))


def test_hybrid_temporal_and_lifecycle_filters_run_before_union():
    from precog.retrieval import HybridRetriever
    store = InMemoryStore()
    current = memory(store, "m-current", "release error", valid_from=NOW - timedelta(days=1))
    future = memory(store, "m-future", "release error", valid_from=NOW + timedelta(days=1))
    archived = memory(store, "m-archived", "release error", lifecycle=MemoryLifecycle.ARCHIVED)
    candidates = tuple(
        LexicalRetriever(store).search("release error", at=None, limit=10)
    )
    result = HybridRetriever(store).search(
        "release error", now=NOW, lexical_candidates=candidates
    )
    assert [item.object_id for item in result] == [current.id]
    assert future.id not in {item.object_id for item in result}
    assert archived.id not in {item.object_id for item in result}


def test_hybrid_deterministic_tie_breaks_by_object_id():
    from precog.retrieval import HybridRetriever
    store = InMemoryStore()
    a = memory(store, "m-a", "same")
    b = memory(store, "m-b", "same")
    result1 = HybridRetriever(store).search("same", now=NOW)
    result2 = HybridRetriever(store).search("same", now=NOW)
    assert [x.object_id for x in result1] == [x.object_id for x in result2]
    assert [x.object_id for x in result1] == sorted([a.id, b.id])


def test_hybrid_vector_only_is_supported():
    from precog.retrieval import HybridRetriever
    store = InMemoryStore()
    first = memory(store, "m-a", "unrelated")
    memory(store, "m-b", "other")
    result = HybridRetriever(store).search(
        "vector query", now=NOW,
        query_vector=(1.0, 0.0),
        vectors={first.id: (1.0, 0.0)}
    )
    assert [item.object_id for item in result] == [first.id]
    assert result[0].semantic_score == 1.0


def test_optional_reranker_is_not_canonical():
    from precog.retrieval import HybridRetriever
    store = InMemoryStore()
    memory(store, "m-a", "alpha")
    memory(store, "m-b", "alpha")
    retriever = HybridRetriever(store)
    canonical = retriever.search("alpha", now=NOW)
    class Reverse:
        def rerank(self, candidates):
            return tuple(reversed(candidates))
    reranked = retriever.search("alpha", now=NOW, reranker=Reverse())
    assert [x.object_id for x in canonical] != [x.object_id for x in reranked]
    assert {x.object_id for x in canonical} == {x.object_id for x in reranked}
