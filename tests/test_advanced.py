from datetime import datetime, timezone

from precog.capability import CapabilityCandidate
from precog.continual import ChampionChallenger, ModelCandidate
from precog.evolution import CapabilityEvolution
from precog.models import Behavior, Experience, Provenance, Knowledge
from precog.next_action import BestNextActionSelector
from precog.prediction import BehaviorPrediction
from precog.ranker import JevRankerAdapter
from precog.relations import RelationGraph
from precog.store import InMemoryStore

NOW = datetime.now(timezone.utc)


def test_relation_graph_projects_temporal_edges() -> None:
    from precog.models import Relation, RelationType
    store = InMemoryStore()
    e1 = Experience("e1", "t1", NOW, NOW, "a", "event", {}, Provenance(("e1",), "capture"))
    e2 = Experience("e2", "t1", NOW, NOW, "a", "event", {}, Provenance(("e2",), "capture"))
    store.append_experience(e1)
    store.append_experience(e2)
    store.put_relation(Relation("r1", "e1", "e2", RelationType.FOLLOWS, 1.0, NOW, provenance=Provenance(("e1", "e2"), "relation")))
    assert RelationGraph(store).project() == (("e1", "follows", "e2"),)


def test_jev_adapter_is_provider_neutral() -> None:
    predictions = (BehaviorPrediction("b1", 0.2, ("e1",)),)
    assert JevRankerAdapter().rerank(predictions, "ctx") == predictions


def test_best_next_action_uses_prediction_without_authorizing_it() -> None:
    predictions = (BehaviorPrediction("b1", 0.9, ("e1",)),)
    behaviors = (Behavior("b1", "book", (), (), ("book",), "booked"),)
    selected = BestNextActionSelector().select(predictions, behaviors)
    assert selected is not None
    assert selected.action == "book"


def test_capability_evolution_gate() -> None:
    candidate = CapabilityCandidate("c1", "skill", "learn booking", ("k1",), 0.9, 0.1)
    decision = CapabilityEvolution().evaluate(candidate)
    assert decision.approved


def test_champion_challenger_promotes_and_rolls_back() -> None:
    controller = ChampionChallenger()
    first = ModelCandidate("m1", "1", 0.80, ("eval-1",))
    second = ModelCandidate("m2", "2", 0.85, ("eval-2",))
    assert controller.evaluate(first).promoted
    assert controller.evaluate(second).promoted
    assert controller.rollback().id == "m1"


def test_knowledge_candidate_keeps_evidence() -> None:
    knowledge = Knowledge(
        "k1", "customers prefer morning", "booking",
        ("e1",), 0.9, "validated", 1, NOW,
        provenance=Provenance(("e1",), "consolidation"),
    )
    from precog.capability import CapabilityValidator
    candidate = CapabilityValidator().propose(knowledge)
    assert candidate.evidence_ids == ("e1",)
