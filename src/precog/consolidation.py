from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from .models import Experience, Memory, RetrievalEvidence
from .retrieval_repository import RetrievalRepository

if TYPE_CHECKING:
    from .store import InMemoryStore


@dataclass(frozen=True, slots=True)
class ConsolidationProposal:
    id: str
    source_ids: tuple[str, ...]
    observations: tuple[str, ...]
    explanation: tuple[str, ...]
    generalization: str
    candidate_knowledge: tuple[str, ...]
    contradictions: tuple[str, ...]
    confidence: float
    expected_benefit: float
    validation_requirements: tuple[str, ...]


class Consolidator:
    def __init__(self, store: InMemoryStore | None = None) -> None:
        self.store = store

    def propose(self, experiences: tuple[Experience, ...]) -> ConsolidationProposal:
        if not experiences:
            raise ValueError("consolidation requires experience")
        ordered = tuple(sorted(experiences, key=lambda e: (e.occurred_at, e.id)))
        outcomes = tuple(e.outcome for e in ordered if e.outcome)
        observations = tuple(dict.fromkeys(e.event_type for e in ordered))
        explanation = tuple(dict.fromkeys(f"{e.event_type}:{e.outcome}" for e in ordered if e.outcome))
        contradictions = tuple(
            f"conflicting-outcome:{a}:{b}" for a, b in zip(outcomes, outcomes[1:]) if a != b
        )
        confidence = 1.0 if not contradictions else 0.5
        benefit = min(1.0, len(ordered) / 5)
        from .models import Provenance, MemoryLifecycle, MemoryType, stable_id, Memory
        return ConsolidationProposal(
            stable_id("proposal", *(e.id for e in ordered)),
            tuple(e.id for e in ordered),
            observations,
            explanation,
            " ; ".join(observations),
            tuple(f"behavior-pattern:{o}" for o in dict.fromkeys(outcomes)),
            contradictions,
            confidence,
            benefit,
            ("independent evidence", "provenance validation", "contradiction review"),
        )

    def propose_from_retrieval(
        self,
        query: str,
        *,
        now: datetime,
        retrieval: RetrievalRepository,
        experiences: tuple[Experience, ...],
        limit: int = 10,
    ) -> ConsolidationProposal:
        evidence = retrieval.retrieve(query, now=now, limit=limit)
        source_ids = {source_id for item in evidence for source_id in item.provenance.source_ids}
        selected = tuple(e for e in experiences if e.id in source_ids)
        if not selected:
            raise ValueError("retrieval produced no experience-backed evidence")
        return self.propose(selected)

    def validate(self, proposal: ConsolidationProposal, *, independent_sources: int = 1) -> bool:
        return (
            bool(proposal.source_ids)
            and independent_sources >= 1
            and proposal.confidence >= 0.5
            and not proposal.contradictions
        )

    def materialize_memory(self, proposal: ConsolidationProposal, *, now: datetime) -> Memory:
        from .models import Memory, MemoryLifecycle, MemoryType, Provenance, stable_id
        lifecycle = MemoryLifecycle.ACTIVE if self.validate(proposal) else MemoryLifecycle.CANDIDATE
        return Memory(
            stable_id("memory", proposal.id), MemoryType.SEMANTIC, proposal.generalization,
            proposal.source_ids, now, confidence=proposal.confidence,
            salience=proposal.expected_benefit, lifecycle=lifecycle,
            provenance=Provenance(proposal.source_ids, "consolidation"),
        )
