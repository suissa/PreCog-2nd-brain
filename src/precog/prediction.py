from __future__ import annotations

from dataclasses import dataclass
from collections import Counter

from .models import Behavior, Experience


@dataclass(frozen=True, slots=True)
class BehaviorPrediction:
    behavior_id: str
    probability: float
    evidence_ids: tuple[str, ...]


class BehaviorPredictor:
    """Deterministic BehaviorID baseline.

    Prediction proposes a ranked behavior; it does not authorize execution.
    """

    def predict(
        self,
        experiences: tuple[Experience, ...],
        behaviors: tuple[Behavior, ...],
        *,
        limit: int = 5,
    ) -> tuple[BehaviorPrediction, ...]:
        counts = Counter(e.behavior_id for e in experiences if e.behavior_id)
        total = sum(counts.values()) or 1
        predictions = []
        for behavior in behaviors:
            count = counts.get(behavior.id, 0)
            if count == 0:
                continue
            evidence = tuple(e.id for e in experiences if e.behavior_id == behavior.id)[-10:]
            predictions.append(BehaviorPrediction(behavior.id, count / total, evidence))
        predictions.sort(key=lambda p: (-p.probability, p.behavior_id))
        return tuple(predictions[:max(0, limit)])
