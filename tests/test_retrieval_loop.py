from datetime import datetime, timezone

from precog.models import Behavior, Experience, Provenance, RetrievalEvidence, MemoryLifecycle
from precog.next_action import BestNextActionSelector
from precog.prediction import BehaviorPrediction, BehaviorPredictor
from precog.retrieval_repository import InMemoryRetrievalRepository
from precog.store import InMemoryStore

NOW = datetime.now(timezone.utc)


def exp(i: str, behavior: str) -> Experience:
    return Experience(
        i, "t1", NOW, NOW, "agent", "action", {},
        Provenance((i,), "capture"), behavior_id=behavior,
    )


def test_prediction_can_be_driven_by_retrieved_evidence() -> None:
    store = InMemoryStore()
    e1 = exp("e1", "b1")
    e2 = exp("e2", "b2")
    store.append_experience(e1)
    store.append_experience(e2)
    from precog.models import Memory, MemoryType
    store.put_memory(Memory(
        "m1", MemoryType.SEMANTIC, "booking morning",
        ("e1",), NOW, lifecycle=MemoryLifecycle.ACTIVE,
        provenance=Provenance(("e1",), "consolidation"),
    ))
    repository = InMemoryRetrievalRepository(store)
    evidence = repository.retrieve("booking morning", now=NOW)
    predictions = BehaviorPredictor().predict(
        (e1, e2), (Behavior("b1","book",(),(),("book",),"booked"),
                   Behavior("b2","cancel",(),(),("cancel",),"cancelled")),
        retrieval=evidence,
    )
    assert predictions[0].behavior_id == "b1"
    assert "e1" in predictions[0].evidence_ids


def test_next_action_retains_retrieval_evidence_in_rationale() -> None:
    prediction = BehaviorPrediction(
        "b1", 0.9, ("e1",)
    )
    evidence = RetrievalEvidence(
        "m1", 0.8, 0.8, 0.0, 0.5, 0.0,
        Provenance(("e1",), "retrieval"), MemoryLifecycle.ACTIVE, "memory",
    )
    selected = BestNextActionSelector().select(
        (prediction,), (Behavior("b1","book",(),(),("book",),"booked"),),
        retrieval=(evidence,),
    )
    assert selected is not None
    assert selected.action == "book"
    assert selected.rationale == ("e1", "m1")
