from datetime import datetime, timezone

from precog.models import Memory, MemoryLifecycle, MemoryType, Provenance
from precog.retrieval_repository import (
    InMemoryRetrievalRepository,
    PostgresRetrievalRepository,
)
from precog.store import InMemoryStore


NOW = datetime.now(timezone.utc)


def memory(memory_id: str, content: str) -> Memory:
    return Memory(
        memory_id,
        MemoryType.SEMANTIC,
        content,
        ("e1",),
        NOW,
        confidence=1.0,
        salience=0.5,
        lifecycle=MemoryLifecycle.ACTIVE,
        provenance=Provenance(("e1",), "test"),
    )


def test_in_memory_retrieval_repository_contract() -> None:
    store = InMemoryStore()
    store.put_memory(memory("m1", "customer prefers morning"))
    result = InMemoryRetrievalRepository(store).retrieve("customer morning", now=NOW)
    assert result[0].object_id == "m1"
    assert result[0].source_type == "memory"


class StubPostgresStore:
    def __init__(self) -> None:
        self._memory = memory("m1", "customer prefers morning")

    def search_memory_candidates(self, query: str, *, now: datetime, limit: int = 10):
        assert query == "customer morning"
        assert now == NOW
        return (("m1", 0.8, 1.0, 0.5, 0.71),)

    def memories(self, include_archived: bool = False):
        return (self._memory,)


def test_postgres_retrieval_repository_maps_database_evidence() -> None:
    result = PostgresRetrievalRepository(StubPostgresStore()).retrieve(
        "customer morning", now=NOW
    )
    assert result == (
        result[0],
    )
    assert result[0].object_id == "m1"
    assert result[0].lexical_score == 0.8
    assert result[0].semantic_score == 0.0
    assert result[0].score == 0.71


def test_postgres_repository_respects_lifecycle_filter() -> None:
    result = PostgresRetrievalRepository(StubPostgresStore()).retrieve(
        "customer morning", now=NOW, lifecycle={MemoryLifecycle.ARCHIVED}
    )
    assert result == ()
