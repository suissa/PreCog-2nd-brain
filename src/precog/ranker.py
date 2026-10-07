from __future__ import annotations

from typing import Protocol, Sequence

from .prediction import BehaviorPrediction


class BehaviorRanker(Protocol):
    def rank(self, behavior_ids: Sequence[str], context: str) -> Sequence[tuple[str, float]]: ...


class JevRankerAdapter:
    """Adapter boundary for Jev/remote rankers; no provider is canonical."""

    def __init__(self, ranker: BehaviorRanker | None = None) -> None:
        self.ranker = ranker

    def rerank(
        self,
        predictions: tuple[BehaviorPrediction, ...],
        context: str,
    ) -> tuple[BehaviorPrediction, ...]:
        if self.ranker is None:
            return predictions
        scores = dict(self.ranker.rank([p.behavior_id for p in predictions], context))
        ranked = tuple(
            BehaviorPrediction(p.behavior_id, max(0.0, min(1.0, scores.get(p.behavior_id, p.probability))), p.evidence_ids)
            for p in predictions
        )
        return tuple(sorted(ranked, key=lambda p: (-p.probability, p.behavior_id)))
