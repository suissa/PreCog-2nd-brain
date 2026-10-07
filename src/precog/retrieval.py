from __future__ import annotations

import math
import re
from collections import Counter
from datetime import datetime
from typing import Any, Protocol, Sequence

from .models import Memory, MemoryLifecycle, RetrievalEvidence
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


def _phrase_match(query: str, content: str) -> bool:
    return query.strip().casefold() in content.casefold()


class RetrievalReranker(Protocol):
    """Optional reranker; canonical retrieval never invokes it implicitly."""
    def rerank(self, candidates: tuple[RetrievalEvidence, ...]) -> tuple[RetrievalEvidence, ...]: ...


class LexicalRetriever:
    """Deterministic lexical retrieval over canonical Memory projections."""
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def search(self, query: str, *, at: datetime | None = None,
               tenant_id: str | None = None, actor: str | None = None,
               lifecycle: set[MemoryLifecycle] | None = None,
               limit: int = 10) -> tuple[RetrievalEvidence, ...]:
        if not query.strip() or limit <= 0:
            return ()
        results: list[RetrievalEvidence] = []
        for memory in self.store.memories():
            if not _allowed(memory, at=at, tenant_id=tenant_id, actor=actor, lifecycle=lifecycle):
                continue
            lexical = _lexical(query, " ".join((memory.id, memory.content, *memory.source_ids)))
            if _phrase_match(query, memory.content):
                lexical = 1.0
            if lexical <= 0:
                continue
            temporal = 1.0 if at is not None else 0.5
            results.append(_evidence(memory, lexical=lexical, temporal=temporal))
        return tuple(sorted(results, key=_rank_key)[:limit])


class SemanticRetriever:
    """Provider-neutral semantic retrieval facade over PostgreSQL pgvector."""
    def __init__(self, store: Any, provider: Any) -> None:
        self.store = store
        self.provider = provider

    def search(self, query: str, *, limit: int = 10) -> tuple[RetrievalEvidence, ...]:
        if not query.strip() or limit <= 0:
            return ()
        vector = tuple(float(value) for value in self.provider.embed(query))
        if len(vector) != self.provider.dimensions:
            raise ValueError(
                f"query embedding returned {len(vector)} dimensions; expected {self.provider.dimensions}"
            )
        rows = self.store.semantic_search(vector, model=self.provider.model,
                                           provider_version=self.provider.version,
                                           dimensions=self.provider.dimensions, limit=limit)
        return tuple(RetrievalEvidence(row["object_id"], row["score"], 0.0, row["score"], 0.0, 0.0,
                                       row["provenance"], row["lifecycle"], row["source_type"]) for row in rows)


def _allowed(memory: Memory, *, at: datetime | None, tenant_id: str | None,
             actor: str | None, lifecycle: set[MemoryLifecycle] | None) -> bool:
    if memory.lifecycle is MemoryLifecycle.ARCHIVED:
        return False
    if lifecycle is not None and memory.lifecycle not in lifecycle:
        return False
    if at is not None and not memory.is_valid_at(at):
        return False
    if tenant_id is not None and memory.metadata.get("tenant_id") != tenant_id:
        return False
    if actor is not None and memory.metadata.get("actor") != actor:
        return False
    return True


def _evidence(memory: Memory, *, lexical: float = 0.0, semantic: float = 0.0,
              temporal: float = 0.0, relation: float = 0.0,
              metadata: float = 0.0) -> RetrievalEvidence:
    components = {name: max(0.0, min(1.0, value)) for name, value in
                  (("lexical", lexical), ("semantic", semantic), ("temporal", temporal),
                   ("relation", relation), ("metadata", metadata))}
    weights = {"lexical": 0.45, "semantic": 0.30, "temporal": 0.15,
               "relation": 0.05, "metadata": 0.05}
    score = min(1.0, sum(components[name] * weights[name] for name in weights))
    return RetrievalEvidence(memory.id, score, components["lexical"], components["semantic"],
                             components["temporal"], components["relation"], memory.provenance,
                             memory.lifecycle, "memory", components["metadata"])


def _rank_key(item: RetrievalEvidence) -> tuple[float, str]:
    return (-item.score, item.object_id)


class HybridRetriever:
    """Union candidate sets, preserve component evidence, then deterministically fuse."""
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def search(self, query: str, *, now: datetime | None = None,
               query_vector: Sequence[float] | None = None,
               vectors: dict[str, Sequence[float]] | None = None,
               relation_scores: dict[str, float] | None = None,
               metadata_scores: dict[str, float] | None = None,
               lifecycle: set[MemoryLifecycle] | None = None,
               tenant_id: str | None = None, actor: str | None = None,
               lexical_candidates: Sequence[RetrievalEvidence] | None = None,
               semantic_candidates: Sequence[RetrievalEvidence] | None = None,
               metadata_candidates: Sequence[RetrievalEvidence] | None = None,
               temporal_candidates: Sequence[RetrievalEvidence] | None = None,
               reranker: RetrievalReranker | None = None,
               limit: int = 10) -> tuple[RetrievalEvidence, ...]:
        if not query.strip() or limit <= 0:
            return ()
        memories = {m.id: m for m in self.store.memories()
                    if _allowed(m, at=now, tenant_id=tenant_id, actor=actor, lifecycle=lifecycle)}
        vectors, relation_scores, metadata_scores = vectors or {}, relation_scores or {}, metadata_scores or {}
        candidate_map: dict[str, RetrievalEvidence] = {}

        def add(candidate: RetrievalEvidence) -> None:
            memory = memories.get(candidate.object_id)
            if memory is None:
                return
            current = candidate_map.get(candidate.object_id)
            if current is None:
                candidate_map[candidate.object_id] = candidate
                return
            candidate_map[candidate.object_id] = RetrievalEvidence(
                candidate.object_id, max(current.score, candidate.score),
                max(current.lexical_score, candidate.lexical_score),
                max(current.semantic_score, candidate.semantic_score),
                max(current.temporal_score, candidate.temporal_score),
                max(current.relation_score, candidate.relation_score),
                current.provenance, current.lifecycle, current.source_type,
                max(current.metadata_score, candidate.metadata_score))

        for candidates in (lexical_candidates, semantic_candidates, metadata_candidates, temporal_candidates):
            if candidates is not None:
                for candidate in candidates:
                    add(candidate)

        for memory in memories.values():
            lexical = _lexical(query, memory.content)
            if _phrase_match(query, memory.content):
                lexical = 1.0
            semantic = _cosine(query_vector, vectors[memory.id]) if query_vector is not None and memory.id in vectors else 0.0
            temporal = self._temporal(memory, now) if now is not None else 0.0
            relation = max(0.0, min(1.0, relation_scores.get(memory.id, 0.0)))
            metadata = max(0.0, min(1.0, metadata_scores.get(memory.id, 0.0)))
            if any((lexical, semantic, temporal, relation, metadata)):
                add(_evidence(memory, lexical=lexical, semantic=semantic,
                               temporal=temporal, relation=relation, metadata=metadata))

        canonical = tuple(sorted(candidate_map.values(), key=_rank_key)[:limit])
        if reranker is None:
            return canonical
        reranked = reranker.rerank(canonical)
        allowed_ids = {item.object_id for item in canonical}
        return tuple(item for item in reranked if item.object_id in allowed_ids)[:limit]

    @staticmethod
    def _temporal(memory: Memory, now: datetime) -> float:
        if memory.valid_from and now < memory.valid_from:
            return 0.0
        if memory.valid_to and now >= memory.valid_to:
            return 0.0
        if not memory.valid_from and not memory.valid_to:
            return 0.5
        return 1.0
