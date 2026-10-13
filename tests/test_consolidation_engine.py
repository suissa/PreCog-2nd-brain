from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

import pytest

from precog.consolidation import (
    ConsolidationEngine,
    ConsolidationProviderError,
    DeterministicConsolidationAdapter,
)
from precog.models import (
    Experience, Memory, MemoryLifecycle, MemoryType, Provenance,
)
from precog.store import InMemoryStore


NOW = datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)


def seed_store() -> tuple[InMemoryStore, tuple[Experience, ...]]:
    store = InMemoryStore()
    items = tuple(
        Experience(
            f"e{i}", "trajectory-1", NOW, NOW, "actor", event,
            {"step": i}, Provenance((f"e{i}",), "capture"), outcome="succeeded",
        )
        for i, event in enumerate(("request_received", "task_completed"), start=1)
    )
    for item in items:
        store.append_experience(item)
    return store, items


class StaticAdapter:
    def __init__(self, response: Any = None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error

    def generate(self, context: Mapping[str, Any]) -> Mapping[str, Any]:
        if self.error:
            raise self.error
        return self.response


def valid_response(source_ids: tuple[str, ...]) -> dict[str, Any]:
    ids = list(source_ids)
    return {
        "evidence": [{"claim": "Two events observed", "source_ids": ids}],
        "observations": [{"claim": "The task completed", "source_ids": ids}],
        "root_cause_analysis": [{"claim": "Completion followed request receipt", "source_ids": ids}],
        "generalization": {"claim": "Requests can complete after receipt", "source_ids": ids},
        "candidate_changes": [{"claim": "Retain this workflow pattern", "source_ids": ids}],
        "contradictions": [],
        "confidence": 0.9,
        "expected_benefit": 0.7,
        "validation_requirements": ["review evidence", "validate provenance"],
    }


def test_proposal_contains_all_required_sections_and_claim_evidence() -> None:
    store, experiences = seed_store()
    proposal = ConsolidationEngine(store).propose(experiences)

    assert proposal.evidence
    assert proposal.observation_claims
    assert proposal.root_cause_analysis
    assert proposal.generalization_claim is not None
    assert proposal.candidate_changes
    assert proposal.validation_requirements
    assert all(set(claim.source_ids) <= set(proposal.source_ids) for claim in proposal.evidence)


def test_rejection_does_not_change_canonical_memory_or_knowledge() -> None:
    store, experiences = seed_store()
    store.put_memory(Memory(
        "existing-memory", MemoryType.SEMANTIC, "existing", ("e1",), NOW,
        lifecycle=MemoryLifecycle.ACTIVE,
        provenance=Provenance(("e1",), "test"),
    ))
    before_memories = store.memories(include_archived=True)
    before_knowledge = store.knowledge()
    engine = ConsolidationEngine(store)
    proposal = engine.propose(experiences)

    review = engine.review(proposal.id, accepted=False, reviewed_at=NOW)

    assert review.decision == "rejected"
    assert review.memory_id is None and review.knowledge_id is None
    assert store.memories(include_archived=True) == before_memories
    assert store.knowledge() == before_knowledge


def test_acceptance_materializes_versioned_memory_and_knowledge_idempotently() -> None:
    store, experiences = seed_store()
    engine = ConsolidationEngine(store, StaticAdapter(valid_response(tuple(e.id for e in experiences))))
    proposal = engine.propose(experiences)

    review = engine.review(proposal.id, accepted=True, reviewed_at=NOW)
    replay = engine.review(proposal.id, accepted=True, reviewed_at=NOW)

    assert review == replay
    assert review.memory_id and review.knowledge_id
    memory = next(item for item in store.memories() if item.id == review.memory_id)
    knowledge = next(item for item in store.knowledge() if item.id == review.knowledge_id)
    assert memory.lifecycle is MemoryLifecycle.ACTIVE
    assert memory.version == 1
    assert memory.provenance.source_ids == tuple(e.id for e in experiences)
    assert knowledge.version == 1
    assert knowledge.status == "active"
    assert knowledge.evidence_ids == tuple(e.id for e in experiences)


def test_rejecting_a_proposal_cannot_be_reversed_to_acceptance() -> None:
    store, experiences = seed_store()
    engine = ConsolidationEngine(store)
    proposal = engine.propose(experiences)
    engine.review(proposal.id, accepted=False, reviewed_at=NOW)

    with pytest.raises(ValueError, match="different decision"):
        engine.review(proposal.id, accepted=True, reviewed_at=NOW)


def test_malformed_proposal_is_rejected_before_persistence() -> None:
    store, experiences = seed_store()
    malformed = valid_response(tuple(e.id for e in experiences))
    malformed["generalization"] = {"claim": "unsupported claim", "source_ids": ["not-an-experience"]}
    engine = ConsolidationEngine(store, StaticAdapter(malformed))

    with pytest.raises(ValueError, match="outside the selected trajectory"):
        engine.propose(experiences)
    assert store.memories(include_archived=True) == ()
    assert store.knowledge() == ()


def test_missing_evidence_is_rejected() -> None:
    store, experiences = seed_store()
    malformed = valid_response(tuple(e.id for e in experiences))
    malformed["evidence"] = []
    engine = ConsolidationEngine(store, StaticAdapter(malformed))

    with pytest.raises(ValueError, match="requires evidence"):
        engine.propose(experiences)
    assert store.memories(include_archived=True) == ()


def test_provider_failure_does_not_mutate_canonical_state() -> None:
    store, experiences = seed_store()
    before = store.rebuildable_snapshot()
    engine = ConsolidationEngine(store, StaticAdapter(error=TimeoutError("provider timeout")))

    with pytest.raises(ConsolidationProviderError, match="canonical state unchanged"):
        engine.propose(experiences)

    assert store.rebuildable_snapshot() == before
    assert store.memories(include_archived=True) == ()
    assert store.knowledge() == ()


def test_legacy_materialization_cannot_activate_unreviewed_proposal() -> None:
    store, experiences = seed_store()
    proposal = ConsolidationEngine(store).propose(experiences)
    memory = __import__("precog.consolidation", fromlist=["Consolidator"]).Consolidator().materialize_memory(
        proposal, now=NOW
    )
    assert memory.lifecycle is MemoryLifecycle.CANDIDATE
