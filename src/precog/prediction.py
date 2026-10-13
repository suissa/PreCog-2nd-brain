from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime

from .models import Behavior, Experience, RetrievalEvidence
from .retrieval_repository import RetrievalRepository


@dataclass(frozen=True, slots=True)
class BehaviorPrediction:
    behavior_id: str
    probability: float
    evidence_ids: tuple[str, ...]


class BehaviorPredictor:
    """Deterministic BehaviorID baseline with retrieval-aware evidence weighting."""

    def predict(
        self,
        experiences: tuple[Experience, ...],
        behaviors: tuple[Behavior, ...],
        *,
        retrieval: tuple[RetrievalEvidence, ...] = (),
        limit: int = 5,
    ) -> tuple[BehaviorPrediction, ...]:
        counts = Counter(e.behavior_id for e in experiences if e.behavior_id)
        retrieved_sources = {
            source_id for item in retrieval for source_id in item.provenance.source_ids
        }
        weights = Counter(
            e.behavior_id for e in experiences
            if e.behavior_id and e.id in retrieved_sources
        )
        scores = {
            behavior.id: counts.get(behavior.id, 0) + 0.5 * weights.get(behavior.id, 0)
            for behavior in behaviors
        }
        total = sum(scores.values()) or 1.0
        predictions = []
        for behavior in behaviors:
            score = scores[behavior.id]
            if score <= 0:
                continue
            evidence = tuple(
                e.id for e in experiences
                if e.behavior_id == behavior.id and (not retrieval or e.id in retrieved_sources)
            )[-10:]
            if not evidence:
                evidence = tuple(e.id for e in experiences if e.behavior_id == behavior.id)[-10:]
            predictions.append(BehaviorPrediction(behavior.id, score / total, evidence))
        predictions.sort(key=lambda p: (-p.probability, p.behavior_id))
        return tuple(predictions[:max(0, limit)])

    def predict_from_query(
        self,
        query: str,
        *,
        now: datetime,
        retrieval: RetrievalRepository,
        experiences: tuple[Experience, ...],
        behaviors: tuple[Behavior, ...],
        limit: int = 5,
        retrieval_limit: int = 10,
    ) -> tuple[BehaviorPrediction, ...]:
        evidence = retrieval.retrieve(query, now=now, limit=retrieval_limit)
        return self.predict(experiences, behaviors, retrieval=evidence, limit=limit)
