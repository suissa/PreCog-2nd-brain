from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Protocol, TYPE_CHECKING

from .models import Experience, Knowledge, Memory, MemoryLifecycle, MemoryType, Provenance, RetrievalEvidence, stable_id
from .retrieval_repository import RetrievalRepository

if TYPE_CHECKING:
    from .store import InMemoryStore


class ConsolidationProviderError(RuntimeError):
    """A model adapter failed before any canonical state was changed."""


@dataclass(frozen=True, slots=True)
class EvidenceClaim:
    claim: str
    source_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.claim.strip():
            raise ValueError("claim must be non-empty")
        if not self.source_ids:
            raise ValueError("claim requires evidence source_ids")
        if len(set(self.source_ids)) != len(self.source_ids):
            raise ValueError("claim source_ids must be unique")


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
    evidence: tuple[EvidenceClaim, ...] = ()
    observation_claims: tuple[EvidenceClaim, ...] = ()
    root_cause_analysis: tuple[EvidenceClaim, ...] = ()
    generalization_claim: EvidenceClaim | None = None
    candidate_changes: tuple[EvidenceClaim, ...] = ()
    contradiction_claims: tuple[EvidenceClaim, ...] = ()
    schema_version: int = 1

    def __post_init__(self) -> None:
        if not self.id or not self.source_ids:
            raise ValueError("proposal requires id and source_ids")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("proposal confidence must be between 0 and 1")
        if not 0.0 <= self.expected_benefit <= 1.0:
            raise ValueError("expected_benefit must be between 0 and 1")
        if self.schema_version < 1:
            raise ValueError("schema_version must be >= 1")


@dataclass(frozen=True, slots=True)
class ConsolidationReview:
    proposal_id: str
    decision: str
    reviewed_at: datetime
    memory_id: str | None = None
    knowledge_id: str | None = None

    def __post_init__(self) -> None:
        if self.decision not in {"accepted", "rejected"}:
            raise ValueError("decision must be accepted or rejected")
        if self.reviewed_at.tzinfo is None:
            raise ValueError("reviewed_at must be timezone-aware")


class ConsolidationProposalAdapter(Protocol):
    def generate(self, context: Mapping[str, Any]) -> Mapping[str, Any]: ...


class DeterministicConsolidationAdapter:
    """Provider-free adapter for deterministic tests and local execution."""

    def generate(self, context: Mapping[str, Any]) -> Mapping[str, Any]:
        experiences = tuple(context["experiences"])
        source_ids = tuple(item.id for item in experiences)
        observations = tuple(dict.fromkeys(
            f"{item.event_type}" + (f":{item.outcome}" if item.outcome else "")
            for item in experiences
        ))
        outcomes = tuple(dict.fromkeys(item.outcome for item in experiences if item.outcome))
        contradiction_claims = tuple(
            f"conflicting outcomes observed: {left} versus {right}"
            for left, right in zip(outcomes, outcomes[1:]) if left != right
        )
        return {
            "evidence": [
                {"claim": f"Observed event: {item.event_type}", "source_ids": [item.id]}
                for item in experiences
            ],
            "observations": [
                {"claim": claim, "source_ids": list(source_ids)} for claim in observations
            ],
            "root_cause_analysis": [
                {"claim": f"Observed outcome pattern: {outcome}", "source_ids": list(source_ids)}
                for outcome in outcomes
            ],
            "generalization": {
                "claim": " ; ".join(observations) or "No generalization available",
                "source_ids": list(source_ids),
            },
            "candidate_changes": [
                {"claim": f"behavior-pattern:{outcome}", "source_ids": list(source_ids)}
                for outcome in outcomes
            ],
            "contradictions": [
                {"claim": claim, "source_ids": list(source_ids)}
                for claim in contradiction_claims
            ],
            "confidence": 0.5 if contradiction_claims else 0.8,
            "expected_benefit": min(1.0, len(experiences) / 5),
            "validation_requirements": [
                "independent evidence review", "provenance validation", "contradiction review"
            ],
        }


class Consolidator:
    """Legacy deterministic proposal builder; never persists or activates proposals."""

    def __init__(self, store: InMemoryStore | None = None) -> None:
        self.store = store

    def propose(self, experiences: tuple[Experience, ...]) -> ConsolidationProposal:
        if not experiences:
            raise ValueError("consolidation requires experience")
        ordered = tuple(sorted(experiences, key=lambda e: (e.occurred_at, e.id)))
        raw = DeterministicConsolidationAdapter().generate({"experiences": ordered})
        return _parse_proposal(raw, tuple(e.id for e in ordered))

    def propose_from_retrieval(
        self, query: str, *, now: datetime, retrieval: RetrievalRepository,
        experiences: tuple[Experience, ...], limit: int = 10,
    ) -> ConsolidationProposal:
        evidence = retrieval.retrieve(query, now=now, limit=limit)
        source_ids = {source_id for item in evidence for source_id in item.provenance.source_ids}
        selected = tuple(e for e in experiences if e.id in source_ids)
        if not selected:
            raise ValueError("retrieval produced no experience-backed evidence")
        return self.propose(selected)

    def validate(self, proposal: ConsolidationProposal, *, independent_sources: int = 1) -> bool:
        return bool(proposal.source_ids) and independent_sources >= 1 and proposal.confidence >= 0.5 and not proposal.contradictions and _claims_have_evidence(proposal)

    def materialize_memory(self, proposal: ConsolidationProposal, *, now: datetime) -> Memory:
        """Compatibility API always creates a candidate, never an active memory."""
        return Memory(
            stable_id("memory", proposal.id), MemoryType.SEMANTIC, proposal.generalization,
            proposal.source_ids, now, confidence=proposal.confidence,
            salience=proposal.expected_benefit, lifecycle=MemoryLifecycle.CANDIDATE,
            provenance=Provenance(proposal.source_ids, "consolidation"),
        )


class ConsolidationEngine:
    """Owns source selection, proposal validation, review and accepted materialization."""

    def __init__(self, store: InMemoryStore, adapter: ConsolidationProposalAdapter | None = None) -> None:
        self.store = store
        self.adapter = adapter or DeterministicConsolidationAdapter()
        self._proposals: dict[str, ConsolidationProposal] = {}
        self._reviews: dict[str, ConsolidationReview] = {}

    def propose_trajectory(self, trajectory_id: str) -> ConsolidationProposal:
        experiences = tuple(self.store.experiences(trajectory_id))
        if not experiences:
            raise ValueError("trajectory has no experience to consolidate")
        return self.propose(experiences)

    def propose(self, experiences: tuple[Experience, ...]) -> ConsolidationProposal:
        if not experiences:
            raise ValueError("consolidation requires experience")
        ordered = tuple(sorted(experiences, key=lambda e: (e.occurred_at, e.id)))
        known = {item.id for item in self.store.experiences()}
        if any(item.id not in known for item in ordered):
            raise ValueError("proposal sources must exist in canonical experience")
        try:
            raw = self.adapter.generate({
                "experiences": ordered, "source_ids": tuple(item.id for item in ordered),
                "schema_version": 1,
            })
        except Exception as exc:
            raise ConsolidationProviderError("proposal provider failed; canonical state unchanged") from exc
        if not isinstance(raw, Mapping):
            raise ValueError("proposal response must be an object")
        proposal = _parse_proposal(raw, tuple(item.id for item in ordered))
        existing = self._proposals.get(proposal.id)
        if existing is not None and existing != proposal:
            raise ValueError("proposal id collision with different content")
        self._proposals[proposal.id] = proposal
        return proposal

    def get_proposal(self, proposal_id: str) -> ConsolidationProposal:
        try:
            return self._proposals[proposal_id]
        except KeyError as exc:
            raise KeyError(f"unknown proposal: {proposal_id}") from exc

    def review(self, proposal_id: str, *, accepted: bool, reviewed_at: datetime) -> ConsolidationReview:
        if reviewed_at.tzinfo is None:
            raise ValueError("reviewed_at must be timezone-aware")
        proposal = self.get_proposal(proposal_id)
        decision = "accepted" if accepted else "rejected"
        existing = self._reviews.get(proposal_id)
        if existing is not None:
            if existing.decision != decision:
                raise ValueError("proposal has already been reviewed with a different decision")
            return existing
        if accepted and not self.validate(proposal):
            raise ValueError("proposal failed evidence or contradiction validation")
        if not accepted:
            review = ConsolidationReview(proposal_id, decision, reviewed_at)
            self._reviews[proposal_id] = review
            return review

        memory_id, knowledge_id = stable_id("memory", proposal.id), stable_id("knowledge", proposal.id)
        provenance = Provenance(proposal.source_ids, f"consolidation:{proposal.id}")
        memory = Memory(
            memory_id, MemoryType.SEMANTIC, proposal.generalization, proposal.source_ids,
            reviewed_at, confidence=proposal.confidence, salience=proposal.expected_benefit,
            lifecycle=MemoryLifecycle.ACTIVE, provenance=provenance, version=1,
            metadata={"proposal_id": proposal.id, "proposal_schema_version": proposal.schema_version},
        )
        knowledge = Knowledge(
            knowledge_id, proposal.generalization, "derived", proposal.source_ids,
            proposal.confidence, "active", 1, reviewed_at, valid_from=reviewed_at,
            provenance=provenance,
        )
        self.store.put_memory(memory)
        self.store.put_knowledge(knowledge)
        review = ConsolidationReview(proposal_id, decision, reviewed_at, memory_id, knowledge_id)
        self._reviews[proposal_id] = review
        return review

    def validate(self, proposal: ConsolidationProposal) -> bool:
        known = {item.id for item in self.store.experiences()}
        return (
            bool(proposal.source_ids) and set(proposal.source_ids).issubset(known)
            and proposal.confidence >= 0.5 and not proposal.contradictions
            and _claims_have_evidence(proposal)
        )

    def reviews(self) -> tuple[ConsolidationReview, ...]:
        return tuple(self._reviews[key] for key in sorted(self._reviews))


def _parse_claims(raw: Any, *, field_name: str, allowed_sources: set[str]) -> tuple[EvidenceClaim, ...]:
    if not isinstance(raw, (list, tuple)):
        raise ValueError(f"{field_name} must be a list")
    claims: list[EvidenceClaim] = []
    for item in raw:
        if not isinstance(item, Mapping):
            raise ValueError(f"{field_name} entries must be objects")
        claim, source_ids = item.get("claim"), item.get("source_ids")
        if not isinstance(claim, str) or not claim.strip():
            raise ValueError(f"{field_name} claim must be non-empty")
        if not isinstance(source_ids, (list, tuple)) or not source_ids:
            raise ValueError(f"{field_name} claim requires source_ids")
        if not all(isinstance(source_id, str) and source_id for source_id in source_ids):
            raise ValueError(f"{field_name} source_ids must be non-empty strings")
        if not set(source_ids).issubset(allowed_sources):
            raise ValueError(f"{field_name} references evidence outside the selected trajectory")
        claims.append(EvidenceClaim(claim.strip(), tuple(dict.fromkeys(source_ids))))
    return tuple(claims)


def _parse_proposal(raw: Mapping[str, Any], selected_source_ids: tuple[str, ...]) -> ConsolidationProposal:
    allowed_sources = set(selected_source_ids)
    source_ids = raw.get("source_ids", selected_source_ids)
    if not isinstance(source_ids, (list, tuple)) or not source_ids:
        raise ValueError("proposal source_ids must be a non-empty list")
    if not all(isinstance(item, str) and item for item in source_ids):
        raise ValueError("proposal source_ids must be non-empty strings")
    source_ids_tuple = tuple(dict.fromkeys(source_ids))
    if not set(source_ids_tuple).issubset(allowed_sources):
        raise ValueError("proposal references evidence outside the selected trajectory")

    evidence = _parse_claims(raw.get("evidence"), field_name="evidence", allowed_sources=allowed_sources)
    observations = _parse_claims(raw.get("observations"), field_name="observations", allowed_sources=allowed_sources)
    root_cause = _parse_claims(raw.get("root_cause_analysis"), field_name="root_cause_analysis", allowed_sources=allowed_sources)
    generalization_claims = _parse_claims([raw.get("generalization")], field_name="generalization", allowed_sources=allowed_sources)
    candidate_changes = _parse_claims(raw.get("candidate_changes"), field_name="candidate_changes", allowed_sources=allowed_sources)
    contradictions = _parse_claims(raw.get("contradictions"), field_name="contradictions", allowed_sources=allowed_sources)
    confidence, benefit = raw.get("confidence"), raw.get("expected_benefit")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        raise ValueError("confidence must be a number between 0 and 1")
    if isinstance(benefit, bool) or not isinstance(benefit, (int, float)) or not 0 <= benefit <= 1:
        raise ValueError("expected_benefit must be a number between 0 and 1")
    requirements = raw.get("validation_requirements")
    if not isinstance(requirements, (list, tuple)) or not requirements or not all(isinstance(x, str) and x.strip() for x in requirements):
        raise ValueError("validation_requirements must be a non-empty list of strings")
    if not evidence:
        raise ValueError("proposal requires evidence claims")

    canonical = json.dumps(raw, sort_keys=True, default=str, separators=(",", ":"))
    proposal_id = stable_id("proposal", *source_ids_tuple, canonical)
    return ConsolidationProposal(
        proposal_id, source_ids_tuple, tuple(x.claim for x in observations),
        tuple(x.claim for x in root_cause), generalization_claims[0].claim,
        tuple(x.claim for x in candidate_changes), tuple(x.claim for x in contradictions),
        float(confidence), float(benefit), tuple(x.strip() for x in requirements),
        evidence, observations, root_cause, generalization_claims[0],
        candidate_changes, contradictions,
    )


def _claims_have_evidence(proposal: ConsolidationProposal) -> bool:
    claims = (*proposal.evidence, *proposal.observation_claims, *proposal.root_cause_analysis,
              *proposal.candidate_changes, *proposal.contradiction_claims)
    if proposal.generalization_claim is not None:
        claims = (*claims, proposal.generalization_claim)
    return bool(proposal.evidence) and all(
        bool(item.source_ids) and set(item.source_ids).issubset(set(proposal.source_ids))
        for item in claims
    )
