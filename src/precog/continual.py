from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ModelCandidate:
    id: str
    version: str
    metric: float
    provenance: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PromotionDecision:
    candidate_id: str
    promoted: bool
    reason: str


class ChampionChallenger:
    """Offline promotion/rollback state machine."""

    def __init__(self, champion: ModelCandidate | None = None) -> None:
        self.champion = champion
        self.history: list[ModelCandidate] = []

    def evaluate(self, challenger: ModelCandidate, *, min_gain: float = 0.01) -> PromotionDecision:
        if not challenger.provenance:
            return PromotionDecision(challenger.id, False, "missing provenance")
        if self.champion is None:
            self.champion = challenger
            self.history.append(challenger)
            return PromotionDecision(challenger.id, True, "initial champion")
        if challenger.metric >= self.champion.metric + min_gain:
            self.history.append(self.champion)
            self.champion = challenger
            return PromotionDecision(challenger.id, True, "challenger exceeds champion threshold")
        return PromotionDecision(challenger.id, False, "insufficient measured gain")

    def rollback(self) -> ModelCandidate:
        if not self.history:
            raise ValueError("no previous champion available")
        self.champion = self.history.pop()
        return self.champion
