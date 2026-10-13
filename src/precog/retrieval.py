from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Sequence
from datetime import datetime

from .embeddings import EmbeddingProvider
from .models import Memory, MemoryLifecycle, RetrievalEvidence
from .retrieval_repository import RetrievalRepository
from .store import InMemoryStore

_TOKEN = re.compile(r"[\w-]+", re.UNICODE)


def _tokens(text: str) -> Counter[str]:
    return Counter(_TOKEN.findall(text.lower()))


def _lexical(query: str, content: str) -> float:
    q, d = _tokens(query), _tokens(content)
    if not q or not d:
        return 0.0
    if query.strip().lower() in content.lower():
        return 1.0
    overlap = sum(min(q[token], d[token]) for token in q)
    return min(1.0, overlap / max(1, sum(q.values())))


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    aa = math.sqrt(sum(x * x for x in a))
    bb = math.sqrt(sum(x * x for x in b))
    if aa == 0 or bb == 0:
        return 0.0
    return max(0.0, min(1.0, sum(x * y for x, y in zip(a, b)) / (aa * bb)))


class LexicalRetriever:
    """Backward-compatible lexical retrieval over canonical in-memory memories."""

    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def search(
        self,
        query: str,
        *,
        at: datetime | None,
        limit: int = 10,
        tenant_id: str | None = None,
        actor: str | None = None,
        lifecycle: set[MemoryLifecycle] | None = None,
    ) -> tuple[RetrievalEvidence, ...]:
        results: list[RetrievalEvidence] = []
        allowed = lifecycle if lifecycle is not None else {MemoryLifecycle.ACTIVE}
        for memory in self.store.memories():
            if memory.lifecycle not in allowed or memory.lifecycle == MemoryLifecycle.ARCHIVED:
                continue
            if at is not None and not memory.is_valid_at(at):
                continue
            if tenant_id is not None and memory.metadata.get("tenant_id") != tenant_id:
                continue
            if actor is not None and memory.metadata.get("actor") != actor:
                continue
            score = _lexical(query, memory.content)
            if score <= 0:
                continue
            results.append(RetrievalEvidence(
                memory.id, score, score, 0.0, 1.0 if at is not None else 0.5,
                0.0, memory.provenance, memory.lifecycle, "memory",
            ))
        results.sort(key=lambda item: (-item.score, item.object_id))
        return tuple(results[:max(0, limit)])


class SemanticRetriever:
    """Provider-neutral semantic search adapter for stores with semantic_search."""

    def __init__(self, store: object, provider: EmbeddingProvider) -> None:
        self.store = store
        self.provider = provider

    def search(self, query: str) -> tuple[RetrievalEvidence, ...]:
        vector = tuple(float(value) for value in self.provider.embed(query))
        search = getattr(self.store, "semantic_search", None)
        if search is None:
            raise TypeError("semantic store must implement semantic_search")
        rows = search(vector, model=self.provider.model)
        return tuple(
            RetrievalEvidence(
                row["object_id"], float(row["score"]), 0.0, float(row["score"]),
                0.0, 0.0, row["provenance"], row["lifecycle"], row["source_type"],
            )
            for row in rows
        )


class HybridRetriever:
    """Stable retrieval facade with compatibility for candidate-based callers."""

    def __init__(self, repository: RetrievalRepository | InMemoryStore) -> None:
        self.store = repository if isinstance(repository, InMemoryStore) else None
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
        lexical_candidates: Sequence[RetrievalEvidence] | None = None,
        semantic_candidates: Sequence[RetrievalEvidence] | None = None,
        metadata_scores: dict[str, float] | None = None,
        reranker: object | None = None,
        tenant_id: str | None = None,
        actor: str | None = None,
    ) -> tuple[RetrievalEvidence, ...]:
        if lexical_candidates is None and semantic_candidates is None and metadata_scores is None and reranker is None and tenant_id is None and actor is None:
            return self.repository.retrieve(
                query, now=now, query_vector=query_vector, vectors=vectors,
                relation_scores=relation_scores, lifecycle=lifecycle, limit=limit,
            )

        if self.store is None:
            raise TypeError("candidate-based compatibility search requires InMemoryStore")
        if lexical_candidates is None and semantic_candidates is None and metadata_scores is None:
            lexical_candidates = LexicalRetriever(self.store).search(
                query, at=now, limit=limit, tenant_id=tenant_id, actor=actor,
                lifecycle=lifecycle,
            )
        memories = {memory.id: memory for memory in self.store.memories()}
        lexical_by_id: dict[str, RetrievalEvidence] = {}
        for item in lexical_candidates or ():
            current = lexical_by_id.get(item.object_id)
            if current is None or item.lexical_score > current.lexical_score:
                lexical_by_id[item.object_id] = item
        semantic_by_id: dict[str, RetrievalEvidence] = {}
        for item in semantic_candidates or ():
            current = semantic_by_id.get(item.object_id)
            if current is None or item.semantic_score > current.semantic_score:
                semantic_by_id[item.object_id] = item
        scores = metadata_scores or {}
        results: list[RetrievalEvidence] = []
        for object_id in sorted(set(lexical_by_id) | set(semantic_by_id) | set(scores)):
            memory = memories.get(object_id)
            if memory is None or memory.lifecycle == MemoryLifecycle.ARCHIVED:
                continue
            if lifecycle is not None and memory.lifecycle not in lifecycle:
                continue
            if not memory.is_valid_at(now):
                continue
            if tenant_id is not None and memory.metadata.get("tenant_id") != tenant_id:
                continue
            if actor is not None and memory.metadata.get("actor") != actor:
                continue
            lexical = lexical_by_id.get(object_id)
            semantic = semantic_by_id.get(object_id)
            lexical_score = lexical.lexical_score if lexical else 0.0
            semantic_score = semantic.semantic_score if semantic else 0.0
            temporal_score = 1.0
            relation_score = max(0.0, min(1.0, (relation_scores or {}).get(object_id, 0.0)))
            metadata_score = max(0.0, min(1.0, scores.get(object_id, 0.0)))
            score = min(1.0, 0.45 * lexical_score + 0.30 * semantic_score
                        + 0.15 * temporal_score + 0.10 * max(relation_score, metadata_score))
            if score <= 0:
                continue
            results.append(RetrievalEvidence(
                object_id, score, lexical_score, semantic_score, temporal_score,
                relation_score, memory.provenance, memory.lifecycle, "memory", metadata_score,
            ))
        results.sort(key=lambda item: (-item.score, item.object_id))
        if reranker is not None:
            rerank = getattr(reranker, "rerank", None)
            if rerank is None:
                raise TypeError("reranker must implement rerank(candidates)")
            results = list(rerank(tuple(results)))
        return tuple(results[:max(0, limit)])
