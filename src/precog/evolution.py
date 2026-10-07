from __future__ import annotations

from dataclasses import dataclass

from .capability import CapabilityCandidate


@dataclass(frozen=True, slots=True)
class EvolutionDecision:
    candidate_id: str
    approved: bool
    actions: tuple[str, ...]
    reason: str


class Manager:
    def propose(self, candidate: CapabilityCandidate) -> EvolutionDecision:
        return EvolutionDecision(candidate.id, True, ("validate",), "candidate admitted to validation")


class Healer:
    def repair(self, candidate: CapabilityCandidate) -> CapabilityCandidate:
        return CapabilityCandidate(
            candidate.id,
            candidate.kind,
            candidate.description.strip(),
            tuple(dict.fromkeys(candidate.evidence_ids)),
            candidate.expected_gain,
            min(1.0, candidate.risk),
        )


class Judge:
    def decide(self, candidate: CapabilityCandidate, *, min_gain: float = 0.7, max_risk: float = 0.3) -> EvolutionDecision:
        approved = bool(candidate.evidence_ids) and candidate.expected_gain >= min_gain and candidate.risk <= max_risk
        return EvolutionDecision(
            candidate.id,
            approved,
            ("promote",) if approved else ("reject",),
            "measured gain/risk gate",
        )


class CapabilityEvolution:
    def __init__(self) -> None:
        self.manager = Manager()
        self.healer = Healer()
        self.judge = Judge()

    def evaluate(self, candidate: CapabilityCandidate) -> EvolutionDecision:
        admitted = self.manager.propose(candidate)
        if not admitted.approved:
            return admitted
        repaired = self.healer.repair(candidate)
        return self.judge.decide(repaired)
