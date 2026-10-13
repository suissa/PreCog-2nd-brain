from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from .models import Memory, MemoryLifecycle, RetrievalEvidence
from .retrieval_repository import RetrievalRepository
from .store import InMemoryStore

_TOKEN = re.compile(r"[\w-]+", re.UNICODE)


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


def _temporal(memory: Memory, at: datetime) -> float:
    if memory.valid_from and at < memory.valid_from:
        return 0.0
    if memory.valid_to and at >= memory.valid_to:
        return 0.0
    return 1.0


class LexicalRetriever:
    """Deterministic lexical search with provenance and metadata filters."""

    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def search(
        self, query: str, *, at: datetime | None = None, limit: int = 10,
        tenant_id: str | None = None, actor: str | None = None,
        lifecycle: set[MemoryLifecycle] | None = None,
    ) -> tuple[RetrievalEvidence, ...]:
        results: list[RetrievalEvidence] = []
        for memory in self.store.memories():
            if lifecycle is not None and memory.lifecycle not in lifecycle:
                continue
            if tenant_id is not None and memory.metadata.get("tenant_id") != tenant_id:
                continue
            if actor is not None and memory.metadata.get("actor") != actor:
                continue
            temporal = _temporal(memory, at) if at is not None else 1.0
            if temporal <= 0:
                continue
            lexical = _lexical(query, memory.content)
            if lexical <= 0:
                continue
            results.append(RetrievalEvidence(
                memory.id, lexical, lexical, 0.0, temporal, 0.0,
                memory.provenance, memory.lifecycle, "memory",
            ))
        results.sort(key=lambda item: (-item.score, item.object_id))
        return tuple(results[:max(0, limit)])


class SemanticRetriever:
    """Provider-neutral semantic search adapter."""

    def __init__(self, store: Any, provider: Any) -> None:
        self.store = store
        self.provider = provider

    def search(self, query: str, *, limit: int = 10, **filters: Any) -> tuple[RetrievalEvidence, ...]:
        vector = tuple(float(value) for value in self.provider.embed(query))
        raw = self.store.semantic_search(vector, model=self.provider.model, limit=limit, **filters)
        results = []
        for item in raw:
            if isinstance(item, RetrievalEvidence):
                results.append(item)
                continue
            score = float(item.get("score", 0.0))
            results.append(RetrievalEvidence(
                item["object_id"], score, float(item.get("lexical_score", 0.0)),
                score, float(item.get("temporal_score", 0.0)),
                float(item.get("relation_score", 0.0)), item["provenance"],
                item["lifecycle"], item.get("source_type", "memory"),
                float(item.get("metadata_score", 0.0)),
            ))
        results.sort(key=lambda item: (-item.score, item.object_id))
        return tuple(results[:max(0, limit)])


class HybridRetriever:
    """Hybrid retrieval supporting repository-backed and candidate-fusion APIs."""

    def __init__(self, repository: RetrievalRepository | InMemoryStore) -> None:
        self.store = repository if isinstance(repository, InMemoryStore) else None
        if isinstance(repository, InMemoryStore):
            from .retrieval_repository import InMemoryRetrievalRepository
            repository = InMemoryRetrievalRepository(repository)
        self.repository = repository

    def search(
        self, query: str, *, now: datetime | None = None,
        at: datetime | None = None,
        query_vector: Sequence[float] | None = None,
        vectors: dict[str, Sequence[float]] | None = None,
        relation_scores: dict[str, float] | None = None,
        lifecycle: set[MemoryLifecycle] | None = None,
        limit: int = 10,
        lexical_candidates: Sequence[RetrievalEvidence] | None = None,
        semantic_candidates: Sequence[RetrievalEvidence] | None = None,
        metadata_scores: dict[str, float] | None = None,
        reranker: Any | None = None,
    ) -> tuple[RetrievalEvidence, ...]:
        if lexical_candidates is None and semantic_candidates is None and metadata_scores is None and reranker is None:
            if now is None:
                raise TypeError("now is required for repository-backed retrieval")
            return self.repository.retrieve(
                query, now=now, query_vector=query_vector, vectors=vectors,
                relation_scores=relation_scores, lifecycle=lifecycle, limit=limit,
            )
        if self.store is None:
            raise TypeError("candidate fusion requires an InMemoryStore")
        instant = now if now is not None else at
        if lexical_candidates is None:
            lexical_candidates = LexicalRetriever(self.store).search(
                query, at=instant, limit=limit, lifecycle=lifecycle
            )
        by_id: dict[str, RetrievalEvidence] = {}
        memories = {memory.id: memory for memory in self.store.memories()}
        for candidate in (*lexical_candidates, *(semantic_candidates or ())):
            memory = memories.get(candidate.object_id)
            if memory is None or (lifecycle is not None and memory.lifecycle not in lifecycle):
                continue
            if instant is not None and _temporal(memory, instant) <= 0:
                continue
            prior = by_id.get(candidate.object_id)
            lexical = max(candidate.lexical_score, prior.lexical_score if prior else 0.0)
            semantic = max(candidate.semantic_score, prior.semantic_score if prior else 0.0)
            temporal = max(candidate.temporal_score, prior.temporal_score if prior else 0.0)
            relation = max(candidate.relation_score, prior.relation_score if prior else 0.0)
            metadata = max(candidate.metadata_score, prior.metadata_score if prior else 0.0)
            metadata = max(metadata, (metadata_scores or {}).get(candidate.object_id, 0.0))
            score = min(1.0, 0.45 * lexical + 0.30 * semantic + 0.15 * temporal + 0.10 * relation)
            if metadata:
                score = min(1.0, score + 0.10 * metadata)
            by_id[candidate.object_id] = RetrievalEvidence(
                candidate.object_id, score, lexical, semantic, temporal, relation,
                memory.provenance, memory.lifecycle, "memory", metadata,
            )
        results = sorted(by_id.values(), key=lambda item: (-item.score, item.object_id))
        if reranker is not None:
            reranked = tuple(reranker.rerank(tuple(results)))
            valid_ids = {item.object_id for item in results}
            if {item.object_id for item in reranked} == valid_ids:
                results = list(reranked)
        return tuple(results[:max(0, limit)])
