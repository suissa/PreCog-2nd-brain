from __future__ import annotations

from dataclasses import dataclass

from .models import Behavior, RetrievalEvidence
from .prediction import BehaviorPrediction


@dataclass(frozen=True, slots=True)
class BestNextAction:
    behavior_id: str
    action: str
    confidence: float
    rationale: tuple[str, ...]


class BestNextActionSelector:
    """Converts prediction into a proposed action without authorizing execution."""

    def select(
        self,
        predictions: tuple[BehaviorPrediction, ...],
        behaviors: tuple[Behavior, ...],
        *,
        retrieval: tuple[RetrievalEvidence, ...] = (),
    ) -> BestNextAction | None:
        by_id = {b.id: b for b in behaviors}
        retrieved_ids = tuple(item.object_id for item in retrieval)
        for prediction in predictions:
            behavior = by_id.get(prediction.behavior_id)
            if behavior and behavior.actions:
                rationale = prediction.evidence_ids + retrieved_ids
                return BestNextAction(
                    behavior.id,
                    behavior.actions[0],
                    prediction.probability,
                    tuple(dict.fromkeys(rationale)),
                )
        return None

    def select_from_query(
        self,
        query: str,
        *,
        predictions: tuple[BehaviorPrediction, ...],
        behaviors: tuple[Behavior, ...],
        retrieval: tuple[RetrievalEvidence, ...],
    ) -> BestNextAction | None:
        del query
        return self.select(predictions, behaviors, retrieval=retrieval)
