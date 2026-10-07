from __future__ import annotations

from dataclasses import dataclass

from .models import Knowledge


@dataclass(frozen=True, slots=True)
class CapabilityCandidate:
    id: str
    kind: str
    description: str
    evidence_ids: tuple[str, ...]
    expected_gain: float
    risk: float


class CapabilityValidator:
    """Deterministic Manager/Healer/Judge-style gate."""

    def propose(self, knowledge: Knowledge, *, kind: str = "skill") -> CapabilityCandidate:
        gain = max(0.0, min(1.0, knowledge.confidence))
        return CapabilityCandidate(
            id=f"capability:{knowledge.id}:{kind}",
            kind=kind,
            description=knowledge.statement,
            evidence_ids=knowledge.evidence_ids,
            expected_gain=gain,
            risk=1.0 - gain,
        )

    def validate(
        self,
        candidate: CapabilityCandidate,
        *,
        min_gain: float = 0.7,
        max_risk: float = 0.3,
    ) -> bool:
        return (
            bool(candidate.evidence_ids)
            and candidate.expected_gain >= min_gain
            and candidate.risk <= max_risk
        )
