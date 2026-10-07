from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from .models import Memory, MemoryLifecycle, RetrievalEvidence
from .postgres import PostgresStore
from .store import InMemoryStore

_TOKEN = re.compile(r"[\\w-]+", re.UNICODE)


def _tokens(text: str) -> Counter[str]:
    return Counter(_TOKEN.findall(text.lower()))


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    aa = math.sqrt(sum(x * x for x in a))
    bb = math.sqrt(sum(x * x for x in b))
    if aa == 0 or bb == 0:
        return 0.0
    return max(0.0, min(1.0, sum(x * y for x, y in zip(a, b)) / (aa * bb)))


def _lexical(query: str, content: str) -> float:
    q, d = _tokens(query), _tokens(content)
    if not q or not d:
        return 0.0
    overlap = sum(min(q[t], d[t]) for t in q)
    return min(1.0, overlap / max(1, sum(q.values())))


def _temporal(memory: Memory, now: datetime) -> float:
    if memory.valid_from and now < memory.valid_from:
        return 0.0
    if memory.valid_to and now > memory.valid_to:
        return 0.0
    if not memory.valid_from and not memory.valid_to:
        return 0.5
    return 1.0


class RetrievalRepository(Protocol):
    """Provider-neutral retrieval contract.

    Retrieval returns evidence, never executable authority. Implementations may
    use local state, PostgreSQL, or external ranking providers, but provenance
    and deterministic score ordering remain part of the returned evidence.
    """

    def retrieve(
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
        ...


class InMemoryRetrievalRepository:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def retrieve(
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
        vectors = vectors or {}
        relation_scores = relation_scores or {}
        results: list[RetrievalEvidence] = []
        for memory in self.store.memories():
            if lifecycle and memory.lifecycle not in lifecycle:
                continue
            lexical = _lexical(query, memory.content)
            semantic = (
                _cosine(query_vector, vectors[memory.id])
                if query_vector is not None and memory.id in vectors
                else 0.0
            )
            temporal = _temporal(memory, now)
            relation = max(0.0, min(1.0, relation_scores.get(memory.id, 0.0)))
            score = min(1.0, 0.45 * lexical + 0.30 * semantic + 0.15 * temporal + 0.10 * relation)
            if score <= 0:
                continue
            results.append(
                RetrievalEvidence(
                    memory.id, score, lexical, semantic, temporal, relation,
                    memory.provenance, memory.lifecycle, "memory",
                )
            )
        results.sort(key=lambda x: (-x.score, x.object_id))
        return tuple(results[:max(0, limit)])


class PostgresRetrievalRepository:
    """Retrieval adapter over PostgreSQL's deterministic projection."""

    def __init__(self, store: PostgresStore) -> None:
        self.store = store

    def retrieve(
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
        del query_vector, vectors, relation_scores
        candidates = self.store.search_memory_candidates(query, now=now, limit=limit)
        memories = {memory.id: memory for memory in self.store.memories()}
        results: list[RetrievalEvidence] = []
        for memory_id, lexical, temporal, relation, score in candidates:
            memory = memories.get(memory_id)
            if memory is None:
                continue
            if lifecycle and memory.lifecycle not in lifecycle:
                continue
            results.append(
                RetrievalEvidence(
                    memory.id, score, lexical, 0.0, temporal, relation,
                    memory.provenance, memory.lifecycle, "memory",
                )
            )
        results.sort(key=lambda x: (-x.score, x.object_id))
        return tuple(results[:max(0, limit)])


class HybridRetriever:
    """Stable retrieval facade backed by a provider-neutral repository."""

    def __init__(self, repository: RetrievalRepository | InMemoryStore) -> None:
        if isinstance(repository, InMemoryStore):
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
