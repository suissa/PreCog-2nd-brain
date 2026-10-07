from __future__ import annotations

from dataclasses import dataclass

from .models import Behavior
from .prediction import BehaviorPrediction


@dataclass(frozen=True, slots=True)
class BestNextAction:
    behavior_id: str
    action: str
    confidence: float
    rationale: tuple[str, ...]


class BestNextActionSelector:
    """Separates predictive ranking from executable authority."""

    def select(
        self,
        predictions: tuple[BehaviorPrediction, ...],
        behaviors: tuple[Behavior, ...],
    ) -> BestNextAction | None:
        by_id = {b.id: b for b in behaviors}
        for prediction in predictions:
            behavior = by_id.get(prediction.behavior_id)
            if behavior and behavior.actions:
                return BestNextAction(
                    behavior.id,
                    behavior.actions[0],
                    prediction.probability,
                    prediction.evidence_ids,
                )
        return None
