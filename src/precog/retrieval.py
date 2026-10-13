from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from .models import MemoryLifecycle, RetrievalEvidence
from .retrieval_repository import RetrievalRepository
from .store import InMemoryStore


class HybridRetriever:
    """Stable retrieval facade backed by a provider-neutral repository."""

    def __init__(self, repository: RetrievalRepository | InMemoryStore) -> None:
        if isinstance(repository, InMemoryStore):
            from .retrieval_repository import InMemoryRetrievalRepository
            repository = InMemoryRetrievalRepository(repository)
        self.repository = repository

    def search(
        self,
        query: str,
        *,
        now: datetime,
        query_vector: Sequence[float] | None = None,
        vectors: dict[str, Sequence[float]] | None = None,
        relation_scores: dict[str, float] | None = None,
        lifecycle: set[MemoryLifecycle] | None = None,
        limit: int = 10,
    ) -> tuple[RetrievalEvidence, ...]:
        return self.repository.retrieve(
            query,
            now=now,
            query_vector=query_vector,
            vectors=vectors,
            relation_scores=relation_scores,
            lifecycle=lifecycle,
            limit=limit,
        )
