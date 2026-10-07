from __future__ import annotations

import math
import re
from collections import Counter
from datetime import datetime
from typing import Any, Sequence

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


class LexicalRetriever:
    """Deterministic lexical retrieval over canonical Memory projections."""

    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def search(
        self,
        query: str,
        *,
        at: datetime | None = None,
        tenant_id: str | None = None,
        actor: str | None = None,
        lifecycle: set[MemoryLifecycle] | None = None,
        limit: int = 10,
    ) -> tuple[RetrievalEvidence, ...]:
        if not query.strip() or limit <= 0:
            return ()
        now = at
        results: list[RetrievalEvidence] = []
        for memory in self.store.memories():
            if lifecycle is not None and memory.lifecycle not in lifecycle:
                continue
            metadata: dict[str, Any] = dict(memory.metadata)
            if tenant_id is not None and metadata.get("tenant_id") != tenant_id:
                continue
            if actor is not None and metadata.get("actor") != actor:
                continue
            if now is not None and not memory.is_valid_at(now):
                continue
            lexical = _lexical(query, " ".join((memory.id, memory.content, *memory.source_ids)))
            if _phrase_match(query, memory.content):
                lexical = 1.0
            if lexical <= 0:
                continue
            temporal = 1.0 if now is not None else 0.5
            results.append(RetrievalEvidence(
                memory.id, lexical, lexical, 0.0, temporal, 0.0,
                memory.provenance, memory.lifecycle, "memory",
            ))
        results.sort(key=lambda item: (-item.score, item.object_id))
        return tuple(results[:limit])


class HybridRetriever:
    """Lexical + vector + temporal + relation-aware deterministic retrieval."""

    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

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
        vectors = vectors or {}
        relation_scores = relation_scores or {}
        results: list[RetrievalEvidence] = []
        for memory in self.store.memories():
            if lifecycle and memory.lifecycle not in lifecycle:
                continue
            lexical = _lexical(query, memory.content)
            semantic = _cosine(query_vector, vectors[memory.id]) if query_vector is not None and memory.id in vectors else 0.0
            temporal = self._temporal(memory, now)
            relation = max(0.0, min(1.0, relation_scores.get(memory.id, 0.0)))
            score = min(1.0, 0.45 * lexical + 0.30 * semantic + 0.15 * temporal + 0.10 * relation)
            if score <= 0:
                continue
            results.append(RetrievalEvidence(
                memory.id, score, lexical, semantic, temporal, relation,
                memory.provenance, memory.lifecycle, "memory",
            ))
        results.sort(key=lambda x: (-x.score, x.object_id))
        return tuple(results[:max(0, limit)])

    @staticmethod
    def _temporal(memory: Memory, now: datetime) -> float:
        if memory.valid_from and now < memory.valid_from:
            return 0.0
        if memory.valid_to and now >= memory.valid_to:
            return 0.0
        if not memory.valid_from and not memory.valid_to:
            return 0.5
        return 1.0
