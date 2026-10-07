from __future__ import annotations

from dataclasses import dataclass
from .models import Experience, Memory


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    sample_count: int
    coverage: float
    provenance_rate: float
    behavioral_utility: float
    passed: bool


class Evaluator:
    """Offline evaluation with deterministic promotion thresholds."""

    def evaluate(self, experiences: tuple[Experience, ...], memories: tuple[Memory, ...]) -> EvaluationReport:
        n = len(experiences)
        if n == 0:
            return EvaluationReport(0, 0.0, 1.0, 0.0, False)
        ids = {e.id for e in experiences}
        covered = {s for m in memories for s in m.source_ids}
        coverage = len(covered & ids) / n
        provenance = (
            sum(1 for m in memories if m.source_ids and m.provenance.source_ids) / len(memories)
            if memories else 0.0
        )
        utility = min(1.0, len(memories) / max(1, len({e.trajectory_id for e in experiences})))
        passed = coverage >= 0.8 and provenance >= 1.0 and utility >= 0.5
        return EvaluationReport(n, coverage, provenance, utility, passed)
